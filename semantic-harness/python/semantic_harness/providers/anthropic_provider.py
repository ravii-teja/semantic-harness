from __future__ import annotations
from typing import Any
from semantic_harness.providers.base import BaseProvider, ProviderResponse


class AnthropicProvider(BaseProvider):
    """Anthropic provider adapter. Requires: pip install semantic-harness[anthropic]"""

    def __init__(self, api_key: str | None = None, **kwargs: Any):
        self.api_key = api_key
        self._kwargs = kwargs
        self._client_instance = None
        self._async_client_instance = None

    @property
    def _client(self):
        if self._client_instance is None:
            try:
                import anthropic as _anthropic
            except ImportError:
                raise ImportError(
                    "Anthropic provider requires: pip install semantic-harness[anthropic]"
                )
            self._client_instance = _anthropic.Anthropic(api_key=self.api_key, **self._kwargs)
        return self._client_instance

    @property
    def _async_client(self):
        if self._async_client_instance is None:
            try:
                import anthropic as _anthropic
            except ImportError:
                raise ImportError(
                    "Anthropic provider requires: pip install semantic-harness[anthropic]"
                )
            self._async_client_instance = _anthropic.AsyncAnthropic(api_key=self.api_key, **self._kwargs)
        return self._async_client_instance

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        system = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                filtered.append(m)

        resp = await self._async_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=filtered,  # type: ignore
            **kwargs,
        )
        return ProviderResponse(
            content=resp.content[0].text if resp.content else "",
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            raw=resp.model_dump(),
        )

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        system = ""
        filtered = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                filtered.append(m)

        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=filtered,  # type: ignore
            **kwargs,
        )
        return ProviderResponse(
            content=resp.content[0].text if resp.content else "",
            model=resp.model,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            raw=resp.model_dump(),
        )
