"""Context assembler — inspired by NOOA's static/dynamic/event-history split."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ContextBlock:
    """A named block of context content."""

    def __init__(self, key: str, content: str | Callable[..., str], static: bool = True):
        self.key = key
        self._content = content
        self.static = static
        self._cached: str | None = None

    def render(self, locals_: dict[str, Any] | None = None) -> str:
        if self.static:
            if self._cached is None:
                self._cached = self._content if isinstance(self._content, str) else self._content()
            return self._cached
        # Dynamic: call each turn
        if callable(self._content):
            return self._content(**(locals_ or {}))
        return str(self._content)


class ContextAssembler:
    """
    Assembles the LLM prompt from three regions:

    1. Static blocks — stable across turns (system prompt, tool schemas). KV-cache reusable.
    2. Dynamic blocks — re-evaluated each turn (memory recall, live state previews).
    3. Event history — append-only log rendered from the EventBus.

    This split maximizes KV-cache reuse for the static prefix.
    """

    def __init__(self):
        self._static: dict[str, ContextBlock] = {}
        self._dynamic: dict[str, ContextBlock] = {}

    def set_static(self, key: str, content: str):
        """Add a static context block (evaluated once, cached)."""
        self._static[key] = ContextBlock(key, content, static=True)

    def set_dynamic(self, key: str, fn: Callable[..., str]):
        """Add a dynamic context block (callable, re-evaluated each turn)."""
        self._dynamic[key] = ContextBlock(key, fn, static=False)

    def remove(self, key: str):
        """Remove a context block."""
        self._static.pop(key, None)
        self._dynamic.pop(key, None)

    def render(self, event_history: str = "", locals_: dict[str, Any] | None = None) -> str:
        """Render the full prompt context."""
        sections: list[str] = []

        # Static (KV-cache stable)
        for block in self._static.values():
            rendered = block.render()
            if rendered:
                sections.append(f"<{block.key}>\n{rendered}\n</{block.key}>")

        # Dynamic (re-evaluated)
        for block in self._dynamic.values():
            try:
                rendered = block.render(locals_)
                if rendered:
                    sections.append(f"<{block.key}>\n{rendered}\n</{block.key}>")
            except Exception as e:
                sections.append(f"<{block.key}>\n[Error rendering: {e}]\n</{block.key}>")

        # Event history (append-only)
        if event_history:
            sections.append(event_history)

        return "\n\n".join(sections)
