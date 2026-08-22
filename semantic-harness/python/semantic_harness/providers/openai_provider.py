from __future__ import annotations
from typing import Any
from semantic_harness.providers.base import BaseProvider, ProviderResponse


class OpenAIProvider(BaseProvider):
    """OpenAI provider adapter. Requires: pip install semantic-harness[openai]"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **kwargs: Any):
        self.api_key = api_key
        self.base_url = base_url
        self._kwargs = kwargs
        self._client_instance = None
        self._async_client_instance = None

    @property
    def _client(self):
        if self._client_instance is None:
            try:
                import openai as _openai
            except ImportError:
                raise ImportError(
                    "OpenAI provider requires: pip install semantic-harness[openai]"
                )
            self._client_instance = _openai.OpenAI(
                api_key=self.api_key, base_url=self.base_url, **self._kwargs
            )
        return self._client_instance

    @property
    def _async_client(self):
        if self._async_client_instance is None:
            try:
                import openai as _openai
            except ImportError:
                raise ImportError(
                    "OpenAI provider requires: pip install semantic-harness[openai]"
                )
            self._async_client_instance = _openai.AsyncOpenAI(
                api_key=self.api_key, base_url=self.base_url, **self._kwargs
            )
        return self._async_client_instance

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o-mini",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        resp = await self._async_client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return ProviderResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            raw=resp.model_dump(),
        )

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str = "gpt-4o-mini",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        resp = self._client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
        return ProviderResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            raw=resp.model_dump(),
        )
