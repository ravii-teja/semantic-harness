from __future__ import annotations
import os
from typing import Any
import httpx
from semantic_harness.providers.base import BaseProvider, ProviderResponse


class HuggingFaceProvider(BaseProvider):
    """
    Hugging Face Inference API & Dedicated Endpoint Provider adapter.
    Requires: HF_TOKEN environment variable or api_key parameter.
    Optional: pip install semantic-harness[huggingface]
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ):
        self.api_key = api_key or os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        self.base_url = (base_url or "https://api-inference.huggingface.co/models").rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _format_messages_to_prompt(self, messages: list[dict[str, str]]) -> str:
        """Convert chat messages list to standard chat template string."""
        prompt_parts = []
        for m in messages:
            role = m.get("role", "user").upper()
            content = m.get("content", "")
            prompt_parts.append(f"<|im_start|>{role.lower()}\n{content}<|im_end|>")
        prompt_parts.append("<|im_start|>assistant\n")
        return "\n".join(prompt_parts)

    def _get_model_url(self, model: str) -> str:
        clean_model = model
        if clean_model.startswith("hf/") or clean_model.startswith("huggingface/"):
            clean_model = clean_model.split("/", 1)[1]
        if self.base_url.endswith("/models"):
            return f"{self.base_url}/{clean_model}"
        return self.base_url

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "meta-llama/Llama-3.2-1B-Instruct",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        url = self._get_model_url(model)
        prompt = self._format_messages_to_prompt(messages)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": max(temperature, 0.01) if temperature > 0 else 0.0,
                "return_full_text": False,
                **kwargs,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                content = data[0]["generated_text"]
            elif isinstance(data, dict) and "generated_text" in data:
                content = data["generated_text"]
            elif isinstance(data, dict) and "choices" in data:
                content = data["choices"][0]["message"]["content"]
            else:
                content = str(data)

            return ProviderResponse(
                content=content,
                model=model,
                input_tokens=len(prompt.split()),
                output_tokens=len(content.split()),
                raw=data if isinstance(data, dict) else {"data": data},
            )

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str = "meta-llama/Llama-3.2-1B-Instruct",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        url = self._get_model_url(model)
        prompt = self._format_messages_to_prompt(messages)
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": max(temperature, 0.01) if temperature > 0 else 0.0,
                "return_full_text": False,
                **kwargs,
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                content = data[0]["generated_text"]
            elif isinstance(data, dict) and "generated_text" in data:
                content = data["generated_text"]
            elif isinstance(data, dict) and "choices" in data:
                content = data["choices"][0]["message"]["content"]
            else:
                content = str(data)

            return ProviderResponse(
                content=content,
                model=model,
                input_tokens=len(prompt.split()),
                output_tokens=len(content.split()),
                raw=data if isinstance(data, dict) else {"data": data},
            )
