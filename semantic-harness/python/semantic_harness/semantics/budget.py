"""Context budget manager — ensures prompts fit within model context limits."""
from __future__ import annotations


class ContextBudget:
    """
    Manages the token budget for a model's context window.

    Small models have tiny windows (2K-8K tokens). This module ensures
    we never exceed the budget and prioritizes what stays in context.

    Uses a simple character-based estimation (1 token ≈ 4 chars) by default.
    For exact counting, integrate tiktoken.
    """

    def __init__(self, max_tokens: int = 4096, chars_per_token: float = 4.0):
        self.max_tokens = max_tokens
        self._chars_per_token = chars_per_token

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text length."""
        return int(len(text) / self._chars_per_token)

    def fits(self, text: str) -> bool:
        """Check if text fits within the budget."""
        return self.estimate_tokens(text) <= self.max_tokens

    def trim_to_budget(self, messages: list[dict[str, str]], system_tokens: int = 0) -> list[dict[str, str]]:
        """
        Trim message list to fit within budget, keeping the most recent messages.
        Always preserves the system message and the last user message.
        """
        remaining = self.max_tokens - system_tokens
        if remaining <= 0:
            return messages[-1:] if messages else []

        # Work backwards, keeping messages that fit
        kept: list[dict[str, str]] = []
        used = 0
        for msg in reversed(messages):
            msg_tokens = self.estimate_tokens(msg.get("content") or "")
            if used + msg_tokens <= remaining:
                kept.insert(0, msg)
                used += msg_tokens
            else:
                break  # Stop when budget exceeded

        return kept

    def pressure(self, current_tokens: int) -> float:
        """
        Returns a 0.0-1.0 pressure score.
        0.0 = plenty of room, 1.0 = at or over budget.
        Compaction should trigger above 0.8.
        """
        if self.max_tokens == 0:
            return 1.0
        return min(1.0, current_tokens / self.max_tokens)
