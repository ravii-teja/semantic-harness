from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract base for all LLM provider adapters."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Asynchronously complete chat messages."""
        ...

    @abstractmethod
    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Synchronously complete chat messages."""
        ...

    async def complete_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ):
        """Asynchronously stream token chunks. Yields token string chunks."""
        # Default fallback to complete if streaming not explicitly implemented
        resp = await self.complete(messages, model=model, max_tokens=max_tokens, temperature=temperature, **kwargs)
        yield resp.content

