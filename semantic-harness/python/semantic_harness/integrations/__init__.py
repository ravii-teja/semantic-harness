"""Third-party framework and web backend integrations."""
from __future__ import annotations

from semantic_harness.integrations.fastapi import (
    SemanticHarnessMiddleware,
    procedural_route,
)

__all__ = [
    "SemanticHarnessMiddleware",
    "procedural_route",
]
