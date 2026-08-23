"""Procedural memory — cache verified workflows with TurboQuant quantized vector search."""
from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from semantic_harness.memory.turbo_quant import (
    QuantizedVector,
    TurboQuantVectorIndex,
)


@dataclass
class CachedProcedure:
    """A verified workflow pattern."""
    intent_hash: str
    intent_text: str
    procedure: Any
    success_count: int = 0
    failure_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    quantized_vector: QuantizedVector | None = None
    similarity: float = 1.0  # 1.0 for exact match, or cosine score for fuzzy match

    @property
    def confidence(self) -> float:
        """Confidence score based on success/failure ratio."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def is_reliable(self) -> bool:
        """A procedure is reliable if it has >80% success rate and 3+ successes."""
        return self.confidence >= 0.8 and self.success_count >= 3


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

    def __init__(self, vector_dim: int = 64, enable_fuzzy_search: bool = True):
        self._cache: dict[str, CachedProcedure] = {}
        self.enable_fuzzy_search = enable_fuzzy_search
        self._vector_index = TurboQuantVectorIndex(dim=vector_dim)

    @staticmethod
    def _hash_intent(intent: str) -> str:
        """Normalize and hash an intent string."""
        normalized = intent.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def cache(
        self,
        intent: str,
        procedure: Any,
        embedding: Sequence[float] | None = None,
        confidence: float = 1.0,
    ):
        """Cache a workflow for a given intent (both in hash table and compressed vector index)."""
        h = self._hash_intent(intent)
        normalized_intent = intent.strip().lower()

        if h in self._cache:
            self._cache[h].procedure = procedure
            self._cache[h].last_used = time.time()
        else:
            self._cache[h] = CachedProcedure(
                intent_hash=h,
                intent_text=normalized_intent,
                procedure=procedure,
            )

        # Index in TurboQuant PolarQuant Vector Engine
        if self.enable_fuzzy_search:
            self._vector_index.add(
                key=h,
                intent_text=normalized_intent,
                procedure=procedure,
                vector=embedding,
                confidence=confidence,
            )

    def lookup(
        self,
        intent: str,
        embedding: Sequence[float] | None = None,
        similarity_threshold: float = 0.5,
    ) -> CachedProcedure | None:
        """
        Look up a cached procedure by exact hash or approximate TurboQuant vector similarity.

        The default threshold (0.5) is calibrated for the built-in
        SemanticFeatureEmbedder, whose paraphrase similarities typically land
        in the 0.55-0.75 range while unrelated intents score near zero or
        negative. Pass a custom `embedding` for higher-fidelity matching.
        """
        # 1. Fast path: Exact SHA-256 match
        h = self._hash_intent(intent)
        proc = self._cache.get(h)
        if proc:
            proc.last_used = time.time()
            proc.similarity = 1.0
            return proc

        # 2. Fuzzy Semantic Search via PolarQuant Compressed Vectors
        if self.enable_fuzzy_search and len(self._vector_index) > 0:
            query = embedding if embedding is not None else intent
            matches = self._vector_index.search(
                query=query,
                top_k=1,
                min_similarity=similarity_threshold,
            )
            if matches:
                top_match = matches[0]
                matched_proc = self._cache.get(top_match.key)
                if matched_proc:
                    matched_proc.last_used = time.time()
                    matched_proc.similarity = top_match.similarity
                    return matched_proc

        return None

    def record_success(self, intent: str):
        """Record that a cached procedure succeeded."""
        h = self._hash_intent(intent)
        if h in self._cache:
            self._cache[h].success_count += 1

    def record_failure(self, intent: str):
        """Record that a cached procedure failed. Auto-invalidate if unreliable."""
        h = self._hash_intent(intent)
        if h in self._cache:
            self._cache[h].failure_count += 1
            # Auto-invalidate if confidence drops below 50%
            if self._cache[h].confidence < 0.5 and self._cache[h].failure_count >= 3:
                del self._cache[h]
                if self.enable_fuzzy_search:
                    self._vector_index.remove(h)

    def get_all(self) -> list[CachedProcedure]:
        """List all cached procedures."""
        return list(self._cache.values())

    @property
    def size(self) -> int:
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

