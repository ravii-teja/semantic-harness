"""Procedural memory — compile verified workflows, enforce environment & schema invariants, and explain reuse."""
from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json
import os
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from semantic_harness.memory.turbo_quant import (
    QuantizedVector,
    TurboQuantVectorIndex,
)


class ReuseStatus(str, Enum):
    """Explainable status for procedural memory reuse decisions."""
    REUSED = "reused"
    CACHE_MISS = "cache_miss"
    UNRELIABLE = "unreliable"
    SCHEMA_MISMATCH = "schema_mismatch"
    TOOL_VERSION_MISMATCH = "tool_version_mismatch"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    LOW_SIMILARITY = "low_similarity"


@dataclass
class ReuseExplanation:
    """Detailed audit trace for why a compiled procedure was reused or rejected."""
    status: ReuseStatus
    intent: str
    procedure_id: str | None = None
    similarity_score: float = 0.0
    matched_intent: str | None = None
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    rejection_reason: str | None = None

    @property
    def is_reused(self) -> bool:
        return self.status == ReuseStatus.REUSED


@dataclass
class ProcedurePrecondition:
    """Preconditions and environment invariants required to safely reuse a procedure."""
    schema_fingerprint: str | None = None
    tool_signatures: dict[str, str] = field(default_factory=dict)
    env_keys: list[str] = field(default_factory=list)
    min_confidence: float = 0.8
    min_success_count: int = 3

    def matches(
        self,
        schema_fingerprint: str | None = None,
        tool_signatures: dict[str, str] | None = None,
        available_env: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """Verify if current execution context matches preconditions."""
        if self.schema_fingerprint and schema_fingerprint:
            if self.schema_fingerprint != schema_fingerprint:
                return False, f"Schema fingerprint mismatch: expected {self.schema_fingerprint}, got {schema_fingerprint}"
        
        if self.tool_signatures and tool_signatures is not None:
            for tool_name, expected_sig in self.tool_signatures.items():
                if tool_name not in tool_signatures:
                    return False, f"Required tool '{tool_name}' missing from execution environment"
                if tool_signatures[tool_name] != expected_sig:
                    return False, f"Tool signature altered for '{tool_name}'"

        if self.env_keys and available_env is not None:
            for k in self.env_keys:
                if k not in available_env:
                    return False, f"Required environment variable or dependency '{k}' missing"

        return True, None


@dataclass
class CompiledProcedure:
    """A verified, parameterized, and guarded execution trajectory."""
    intent_hash: str
    intent_text: str
    trajectory: Any  # The compiled execution steps or verified result
    parameters: dict[str, Any] = field(default_factory=dict)
    preconditions: ProcedurePrecondition = field(default_factory=ProcedurePrecondition)
    success_count: int = 0
    failure_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    quantized_vector: QuantizedVector | None = None
    similarity: float = 1.0  # 1.0 for exact, or cosine score for fuzzy

    @property
    def procedure(self) -> Any:
        """Backward-compatibility alias."""
        return self.trajectory

    @procedure.setter
    def procedure(self, value: Any) -> None:
        self.trajectory = value

    @property
    def hit_count(self) -> int:
        """Total execution hits (successes + failures)."""
        return self.success_count + self.failure_count

    @property
    def confidence(self) -> float:
        """Confidence score based on success/failure ratio."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def is_reliable(self) -> bool:
        """Checks if procedure meets minimum reliability requirements."""
        return (
            self.confidence >= self.preconditions.min_confidence
            and self.success_count >= self.preconditions.min_success_count
        )


# Backward-compatible alias for existing code
CachedProcedure = CompiledProcedure


class BaseProceduralStorage(ABC):
    """Abstract interface for procedural memory storage backends."""

    @abstractmethod
    def save_procedure(self, intent_hash: str, data: dict[str, Any]) -> None:
        """Persist or update a procedure record."""
        pass

    @abstractmethod
    def get_procedure(self, intent_hash: str) -> dict[str, Any] | None:
        """Fetch a procedure record by intent hash."""
        pass

    @abstractmethod
    def list_procedures(self) -> dict[str, dict[str, Any]]:
        """List all procedure records."""
        pass

    @abstractmethod
    def delete_procedure(self, intent_hash: str) -> bool:
        """Delete a procedure record."""
        pass


class DiskProceduralStorage(BaseProceduralStorage):
    """Atomic local disk persistence using temporary files and os.replace."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath

    def save_procedure(self, intent_hash: str, data: dict[str, Any]) -> None:
        all_procs = self.list_procedures()
        all_procs[intent_hash] = data
        self._flush(all_procs)

    def get_procedure(self, intent_hash: str) -> dict[str, Any] | None:
        all_procs = self.list_procedures()
        return all_procs.get(intent_hash)

    def list_procedures(self) -> dict[str, dict[str, Any]]:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, list):
                return {item.get("intent_hash", f"h_{i}"): item for i, item in enumerate(raw)}
            elif isinstance(raw, dict):
                return raw
            return {}
        except Exception:
            return {}

    def delete_procedure(self, intent_hash: str) -> bool:
        all_procs = self.list_procedures()
        if intent_hash in all_procs:
            del all_procs[intent_hash]
            self._flush(all_procs)
            return True
        return False

    def _flush(self, all_procs: dict[str, dict[str, Any]]) -> None:
        dirname = os.path.dirname(os.path.abspath(self.filepath))
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        tmp = f"{self.filepath}.tmp"
        data_list = list(all_procs.values())
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data_list, f, indent=2)
        os.replace(tmp, self.filepath)


class RedisProceduralStorage(BaseProceduralStorage):
    """Distributed Redis-backed procedural cache storage for Kubernetes clusters."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        key_prefix: str = "semantic_harness:proc:",
    ) -> None:
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._client: Any = None
        self._in_memory_replica: dict[str, dict[str, Any]] = {}

        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True)
            self._client.ping()
        except Exception:
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def save_procedure(self, intent_hash: str, data: dict[str, Any]) -> None:
        self._in_memory_replica[intent_hash] = data
        if self._client is not None:
            try:
                key = f"{self.key_prefix}{intent_hash}"
                self._client.set(key, json.dumps(data))
            except Exception:
                pass

    def get_procedure(self, intent_hash: str) -> dict[str, Any] | None:
        if self._client is not None:
            try:
                key = f"{self.key_prefix}{intent_hash}"
                val = self._client.get(key)
                if val:
                    return json.loads(val)
            except Exception:
                pass
        return self._in_memory_replica.get(intent_hash)

    def list_procedures(self) -> dict[str, dict[str, Any]]:
        res = dict(self._in_memory_replica)
        if self._client is not None:
            try:
                keys = self._client.keys(f"{self.key_prefix}*")
                for k in keys:
                    val = self._client.get(k)
                    if val:
                        h = k[len(self.key_prefix):]
                        res[h] = json.loads(val)
            except Exception:
                pass
        return res

    def delete_procedure(self, intent_hash: str) -> bool:
        existed = intent_hash in self._in_memory_replica
        self._in_memory_replica.pop(intent_hash, None)
        if self._client is not None:
            try:
                key = f"{self.key_prefix}{intent_hash}"
                deleted = self._client.delete(key)
                return deleted > 0 or existed
            except Exception:
                pass
        return existed


class ProceduralMemory:
    """
    Caches verified step-by-step workflows with TurboQuant / PolarQuant vector acceleration.

    THIS IS THE KEY DIFFERENTIATOR. When a small model encounters the same or semantically
    similar intent repeatedly, instead of burning tokens reasoning about it again,
    we return the cached verified result directly.

    Features:
    - O(1) Exact SHA-256 Intent Matching.
    - Sub-microsecond Fuzzy Semantic Matching via PolarQuant Compressed Vectors.
    - Automatic reliability confidence scoring and invalidation.

    Usage:
        proc = ProceduralMemory()

        # Cache after verified success:
        proc.cache("format CSV to JSON", procedure={"steps": [...]})
        proc.record_success("format CSV to JSON")
        proc.record_success("format CSV to JSON")
        proc.record_success("format CSV to JSON")

        # Exact or fuzzy lookup:
        hit = proc.lookup("please format this CSV data to JSON")
        if hit and hit.is_reliable:
            return hit.procedure  # Skips LLM inference entirely!
    """

    def __init__(
        self,
        vector_dim: int = 64,
        enable_fuzzy_search: bool = True,
        persist_path: str | None = None,
        storage: BaseProceduralStorage | None = None,
        redis_url: str | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._cache: dict[str, CachedProcedure] = {}
        self.enable_fuzzy_search = enable_fuzzy_search
        self._vector_index = TurboQuantVectorIndex(dim=vector_dim)
        self.persist_path = persist_path

        if storage is not None:
            self.storage: BaseProceduralStorage | None = storage
        elif redis_url:
            self.storage = RedisProceduralStorage(redis_url=redis_url)
        elif persist_path:
            self.storage = DiskProceduralStorage(filepath=persist_path)
        else:
            self.storage = None

        if self.storage is not None:
            self._sync_from_storage()
        elif persist_path and os.path.exists(persist_path):
            self.load(persist_path)

    @staticmethod
    def _proc_to_dict(proc: CompiledProcedure) -> dict[str, Any]:
        return {
            "intent_hash": proc.intent_hash,
            "intent_text": proc.intent_text,
            "trajectory": proc.trajectory,
            "parameters": proc.parameters,
            "preconditions": {
                "schema_fingerprint": proc.preconditions.schema_fingerprint,
                "tool_signatures": proc.preconditions.tool_signatures,
                "env_keys": proc.preconditions.env_keys,
                "min_confidence": proc.preconditions.min_confidence,
                "min_success_count": proc.preconditions.min_success_count,
            },
            "success_count": proc.success_count,
            "failure_count": proc.failure_count,
            "created_at": proc.created_at,
            "last_used": proc.last_used,
        }

    def _sync_from_storage(self) -> int:
        """Sync local memory cache from the underlying storage backend."""
        if not self.storage:
            return 0
        with self._lock:
            stored = self.storage.list_procedures()
            count = 0
            for item in stored.values():
                h = item["intent_hash"]
                pre_dict = item.get("preconditions", {})
                pre = ProcedurePrecondition(
                    schema_fingerprint=pre_dict.get("schema_fingerprint"),
                    tool_signatures=pre_dict.get("tool_signatures", {}),
                    env_keys=pre_dict.get("env_keys", []),
                    min_confidence=pre_dict.get("min_confidence", 0.8),
                    min_success_count=pre_dict.get("min_success_count", 3),
                )
                proc = CompiledProcedure(
                    intent_hash=h,
                    intent_text=item.get("intent_text", ""),
                    trajectory=item.get("trajectory"),
                    parameters=item.get("parameters"),
                    preconditions=pre,
                    success_count=item.get("success_count", 0),
                    failure_count=item.get("failure_count", 0),
                    created_at=item.get("created_at", time.time()),
                    last_used=item.get("last_used", time.time()),
                )
                self._cache[h] = proc
                if self.enable_fuzzy_search:
                    self._vector_index.add(key=h, intent_text=proc.intent_text, procedure=proc.trajectory, metadata={"proc": proc})
                count += 1
            return count

    @staticmethod
    def _hash_intent(intent: str) -> str:
        """Normalize and hash an intent string."""
        normalized = intent.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def compile(
        self,
        intent: str,
        trajectory: Any,
        parameters: dict[str, Any] | None = None,
        schema_fingerprint: str | None = None,
        tool_signatures: dict[str, str] | None = None,
        env_keys: list[str] | None = None,
        embedding: Sequence[float] | None = None,
        confidence: float = 1.0,
        min_confidence: float = 0.8,
        min_success_count: int = 3,
    ) -> CompiledProcedure:
        """
        Compile an execution trajectory into procedural memory with explicit safety invariants.

        Args:
            intent: Natural language task or goal description.
            trajectory: Sequence of tool actions, code blocks, or structured output.
            parameters: Extracted variables allowing parameterized replay.
            schema_fingerprint: Deterministic hash of target Pydantic schema or type.
            tool_signatures: Map of {tool_name: version_or_signature} required.
            env_keys: Specific environment variables or packages needed.
            embedding: Optional precomputed vector embedding.
            confidence: Initial confidence score.
            min_confidence: Threshold required before procedure is marked reliable.
            min_success_count: Minimum successful runs before auto-reuse is allowed.
        """
        h = self._hash_intent(intent)
        normalized_intent = intent.strip().lower()

        preconditions = ProcedurePrecondition(
            schema_fingerprint=schema_fingerprint,
            tool_signatures=tool_signatures or {},
            env_keys=env_keys or [],
            min_confidence=min_confidence,
            min_success_count=min_success_count,
        )

        proc = CompiledProcedure(
            intent_hash=h,
            intent_text=normalized_intent,
            trajectory=trajectory,
            parameters=parameters or {},
            preconditions=preconditions,
        )

        with self._lock:
            self._cache[h] = proc

            if self.enable_fuzzy_search:
                self._vector_index.add(
                    key=h,
                    intent_text=normalized_intent,
                    procedure=trajectory,
                    vector=embedding,
                    confidence=confidence,
                )

            if self.storage:
                self.storage.save_procedure(h, self._proc_to_dict(proc))
            elif self.persist_path:
                self.save(self.persist_path)

        return proc

    def cache(
        self,
        intent: str,
        procedure: Any,
        embedding: Sequence[float] | None = None,
        confidence: float = 1.0,
        schema_fingerprint: str | None = None,
        tool_signatures: dict[str, str] | None = None,
        env_keys: list[str] | None = None,
    ) -> CompiledProcedure:
        """Backward-compatible cache method delegating to compile()."""
        return self.compile(
            intent=intent,
            trajectory=procedure,
            embedding=embedding,
            confidence=confidence,
            schema_fingerprint=schema_fingerprint,
            tool_signatures=tool_signatures,
            env_keys=env_keys,
        )

    def explain_lookup(
        self,
        intent: str,
        schema_fingerprint: str | None = None,
        tool_signatures: dict[str, str] | None = None,
        available_env: dict[str, Any] | None = None,
        embedding: Sequence[float] | None = None,
        similarity_threshold: float = 0.5,
        require_reliable: bool = True,
    ) -> tuple[CompiledProcedure | None, ReuseExplanation]:
        """
        Look up a procedure with an explainable audit trace detailing why it was reused or rejected.
        """
        h = self._hash_intent(intent)
        candidate: CompiledProcedure | None = None
        sim_score = 1.0
        matched_intent = None

        with self._lock:
            candidate = self._cache.get(h)
            if candidate:
                matched_intent = candidate.intent_text
            elif self.enable_fuzzy_search and len(self._vector_index) > 0:
                query = embedding if embedding is not None else intent
                matches = self._vector_index.search(
                    query=query,
                    top_k=1,
                    min_similarity=similarity_threshold,
                )
                if matches:
                    top_match = matches[0]
                    candidate = self._cache.get(top_match.key)
                    if candidate:
                        sim_score = top_match.similarity
                        matched_intent = candidate.intent_text

        if not candidate:
            explanation = ReuseExplanation(
                status=ReuseStatus.CACHE_MISS,
                intent=intent,
                rejection_reason="No matching procedure found in cache or vector index.",
            )
            return None, explanation

        # Reliability check
        if require_reliable and not candidate.is_reliable:
            explanation = ReuseExplanation(
                status=ReuseStatus.UNRELIABLE,
                intent=intent,
                procedure_id=candidate.intent_hash,
                similarity_score=sim_score,
                matched_intent=matched_intent,
                confidence=candidate.confidence,
                rejection_reason=f"Procedure has not reached reliability threshold (successes={candidate.success_count}/{candidate.preconditions.min_success_count}, confidence={candidate.confidence:.2f}).",
            )
            return None, explanation

        # Precondition / Environment invariant check
        valid_preconds, precond_error = candidate.preconditions.matches(
            schema_fingerprint=schema_fingerprint,
            tool_signatures=tool_signatures,
            available_env=available_env,
        )
        if not valid_preconds:
            status = ReuseStatus.ENVIRONMENT_MISMATCH
            if "Schema fingerprint mismatch" in (precond_error or ""):
                status = ReuseStatus.SCHEMA_MISMATCH
            elif "tool" in (precond_error or "").lower():
                status = ReuseStatus.TOOL_VERSION_MISMATCH

            explanation = ReuseExplanation(
                status=status,
                intent=intent,
                procedure_id=candidate.intent_hash,
                similarity_score=sim_score,
                matched_intent=matched_intent,
                confidence=candidate.confidence,
                rejection_reason=precond_error,
            )
            return None, explanation

        # Reused successfully
        candidate.last_used = time.time()
        candidate.similarity = sim_score
        explanation = ReuseExplanation(
            status=ReuseStatus.REUSED,
            intent=intent,
            procedure_id=candidate.intent_hash,
            similarity_score=sim_score,
            matched_intent=matched_intent,
            confidence=candidate.confidence,
            reasons=[
                "Exact or semantic intent match",
                "Reliability thresholds satisfied",
                "Preconditions, tool signatures, and schema invariants validated",
            ],
        )
        return candidate, explanation

    def lookup(
        self,
        intent: str,
        embedding: Sequence[float] | None = None,
        similarity_threshold: float = 0.5,
        schema_fingerprint: str | None = None,
        tool_signatures: dict[str, str] | None = None,
        available_env: dict[str, Any] | None = None,
        require_reliable: bool = False,
    ) -> CompiledProcedure | None:
        """
        Look up a cached procedure by exact hash or approximate TurboQuant vector similarity.
        """
        proc, _ = self.explain_lookup(
            intent=intent,
            schema_fingerprint=schema_fingerprint,
            tool_signatures=tool_signatures,
            available_env=available_env,
            embedding=embedding,
            similarity_threshold=similarity_threshold,
            require_reliable=require_reliable,
        )
        return proc

    def record_success(self, intent: str) -> None:
        """Record that a cached procedure succeeded."""
        with self._lock:
            h = self._hash_intent(intent)
            if h in self._cache:
                self._cache[h].success_count += 1
                if self.storage:
                    self.storage.save_procedure(h, self._proc_to_dict(self._cache[h]))
                elif self.persist_path:
                    self.save(self.persist_path)

    def record_failure(self, intent: str) -> None:
        """Record that a cached procedure failed. Auto-invalidate if unreliable."""
        with self._lock:
            h = self._hash_intent(intent)
            if h in self._cache:
                self._cache[h].failure_count += 1
                # Auto-invalidate if confidence drops below 50%
                if self._cache[h].confidence < 0.5 and self._cache[h].failure_count >= 3:
                    del self._cache[h]
                    if self.enable_fuzzy_search:
                        self._vector_index.remove(h)
                    if self.storage:
                        self.storage.delete_procedure(h)
                else:
                    if self.storage:
                        self.storage.save_procedure(h, self._proc_to_dict(self._cache[h]))
                if self.persist_path:
                    self.save(self.persist_path)

    def save(self, filepath: str | None = None) -> None:
        """Serialize all compiled procedures to disk (JSON)."""
        target = filepath or self.persist_path
        if not target:
            raise ValueError("No filepath specified and persist_path is not set.")

        with self._lock:
            data = []
            for proc in self._cache.values():
                item = {
                    "intent_hash": proc.intent_hash,
                    "intent_text": proc.intent_text,
                    "trajectory": proc.trajectory,
                    "parameters": proc.parameters,
                    "preconditions": {
                        "schema_fingerprint": proc.preconditions.schema_fingerprint,
                        "tool_signatures": proc.preconditions.tool_signatures,
                        "env_keys": proc.preconditions.env_keys,
                        "min_confidence": proc.preconditions.min_confidence,
                        "min_success_count": proc.preconditions.min_success_count,
                    },
                    "success_count": proc.success_count,
                    "failure_count": proc.failure_count,
                    "created_at": proc.created_at,
                    "last_used": proc.last_used,
                }
                data.append(item)

            dirname = os.path.dirname(os.path.abspath(target))
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            tmp_target = f"{target}.tmp"
            with open(tmp_target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_target, target)

    def load(self, filepath: str | None = None) -> int:
        """Load compiled procedures from disk (JSON). Returns number of procedures loaded."""
        target = filepath or self.persist_path
        if not target or not os.path.exists(target):
            return 0

        with self._lock:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)

            loaded_count = 0
            for item in data:
                precond_dict = item.get("preconditions", {})
                preconds = ProcedurePrecondition(
                    schema_fingerprint=precond_dict.get("schema_fingerprint"),
                    tool_signatures=precond_dict.get("tool_signatures", {}),
                    env_keys=precond_dict.get("env_keys", []),
                    min_confidence=precond_dict.get("min_confidence", 0.8),
                    min_success_count=precond_dict.get("min_success_count", 3),
                )
                proc = CompiledProcedure(
                    intent_hash=item["intent_hash"],
                    intent_text=item["intent_text"],
                    trajectory=item["trajectory"],
                    parameters=item.get("parameters", {}),
                    preconditions=preconds,
                    success_count=item.get("success_count", 0),
                    failure_count=item.get("failure_count", 0),
                    created_at=item.get("created_at", time.time()),
                    last_used=item.get("last_used", time.time()),
                )
                self._cache[proc.intent_hash] = proc
                if self.enable_fuzzy_search:
                    self._vector_index.add(
                        key=proc.intent_hash,
                        intent_text=proc.intent_text,
                        procedure=proc.trajectory,
                        confidence=proc.confidence if proc.confidence > 0 else 1.0,
                    )
                loaded_count += 1
            return loaded_count

    def get_all(self) -> list[CachedProcedure]:
        """List all cached procedures."""
        with self._lock:
            return list(self._cache.values())

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def to_mermaid(self, title: str = "Semantic Procedural Memory Graph") -> str:
        """Render current procedural memory graph as a Mermaid diagram."""
        from semantic_harness.visualization.graph import ProceduralGraphVisualizer
        return ProceduralGraphVisualizer.to_mermaid(self.get_all(), title=title)

    def to_interactive_html(
        self,
        title: str = "Semantic Procedural Memory Knowledge Graph",
        height: str = "600px",
    ) -> str:
        """Render current procedural memory graph as an interactive HTML page."""
        from semantic_harness.visualization.graph import ProceduralGraphVisualizer
        return ProceduralGraphVisualizer.to_interactive_html(
            self.get_all(), title=title, height=height
        )


# Canonical research alias for 100% nomenclature consistency
SemanticProceduralMemory = ProceduralMemory

