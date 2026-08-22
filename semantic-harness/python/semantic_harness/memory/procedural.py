"""Procedural memory — cache verified workflows to skip LLM calls."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


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
    Caches verified step-by-step workflows.

    THIS IS THE KEY DIFFERENTIATOR. When a small model encounters the same
    semantic intent repeatedly, instead of burning tokens reasoning about it
    again, we return the cached verified result directly.

    This is how a 0.5GB model can match a 70B model on repetitive tasks.

    Usage:
        proc = ProceduralMemory()

        # After a successful workflow:
        proc.cache("format CSV to JSON", procedure={"steps": [...]})
        proc.record_success("format CSV to JSON")

        # On next encounter:
        hit = proc.lookup("format CSV to JSON")
        if hit and hit.is_reliable:
            return hit.procedure  # Skip the LLM entirely!
    """

    def __init__(self):
        self._cache: dict[str, CachedProcedure] = {}

    @staticmethod
    def _hash_intent(intent: str) -> str:
        """Normalize and hash an intent string."""
        normalized = intent.strip().lower()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def cache(self, intent: str, procedure: Any):
        """Cache a workflow for a given intent."""
        h = self._hash_intent(intent)
        if h in self._cache:
            self._cache[h].procedure = procedure
            self._cache[h].last_used = time.time()
        else:
            self._cache[h] = CachedProcedure(
                intent_hash=h,
                intent_text=intent.strip().lower(),
                procedure=procedure,
            )

    def lookup(self, intent: str) -> CachedProcedure | None:
        """Look up a cached procedure by intent."""
        h = self._hash_intent(intent)
        proc = self._cache.get(h)
        if proc:
            proc.last_used = time.time()
        return proc

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

    def get_all(self) -> list[CachedProcedure]:
        """List all cached procedures."""
        return list(self._cache.values())

    @property
    def size(self) -> int:
        return len(self._cache)
