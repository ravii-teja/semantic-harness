from __future__ import annotations
from typing import Any
import httpx
from semantic_harness.providers.base import BaseProvider, ProviderResponse


class OllamaProvider(BaseProvider):
    """Ollama local SLM provider. No extra install needed — uses httpx."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "qwen2.5:0.5b",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return ProviderResponse(
                content=data["message"]["content"],
                model=model,
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                raw=data,
            )

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str = "qwen2.5:0.5b",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return ProviderResponse(
                content=data["message"]["content"],
                model=model,
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                raw=data,
            )
