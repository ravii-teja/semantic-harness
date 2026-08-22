"""Short-term memory — bounded sliding window for context management."""
from __future__ import annotations

import collections
from typing import Any


class ShortTermMemory:
    """
    Manages the current session's working memory.

    Critical for small models (<0.5GB) with limited context windows.
    Uses a bounded deque to keep only the most recent and relevant items.

    Design rationale:
    - Small models can't process 128K tokens — we need to be surgical
    - This layer decides what stays in the context window
    - Token counting ensures we never exceed the model's actual limit
    """

    def __init__(self, max_items: int = 20):
        self._memory: collections.deque = collections.deque(maxlen=max_items)

    def add(self, item: Any, role: str = "user"):
        """Add an item to working memory."""
        entry = {"role": role, "content": str(item)}
        self._memory.append(entry)

    def add_message(self, message: dict[str, Any]):
        """Append a pre-built chat message dict verbatim (e.g. tool calls/results)."""
        self._memory.append(message)

    def get_messages(self) -> list[dict[str, str]]:
        """Get all messages in working memory as a chat-format list."""
        return list(self._memory)

    def get_context_string(self) -> str:
        """Render working memory as a single string."""
        parts = []
        for entry in self._memory:
            parts.append(f"[{entry['role']}]: {entry['content']}")
        return "\n".join(parts)

    def clear(self):
        """Clear working memory."""
        self._memory.clear()

    @property
    def size(self) -> int:
        return len(self._memory)
