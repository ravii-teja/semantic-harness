from __future__ import annotations
import sys
import asyncio
from typing import Any
from semantic_harness.providers.base import BaseProvider, ProviderResponse


class MLXProvider(BaseProvider):
    """
    Apple Silicon Metal MLX hardware-accelerated on-device provider.
    Runs 4-bit / 8-bit quantized models natively on Apple M1/M2/M3/M4 unified memory.

    Requires:
        pip install semantic-harness[mlx]  (or: pip install mlx mlx-lm)
    """

    _loaded_models: dict[str, tuple[Any, Any]] = {}

    def __init__(self, **kwargs: Any):
        if sys.platform != "darwin":
            # Inform user if not running on macOS
            pass
        self._kwargs = kwargs

    def _load_model(self, model_name: str):
        """Loads and caches the MLX model and tokenizer in memory."""
        clean_model = model_name
        if clean_model.startswith("mlx/") or clean_model.startswith("metal/"):
            clean_model = clean_model.split("/", 1)[1]

        if clean_model not in self._loaded_models:
            try:
                import mlx_lm
            except ImportError:
                raise ImportError(
                    "MLX Metal provider requires: pip install semantic-harness[mlx] "
                    "(or: pip install mlx mlx-lm on macOS Apple Silicon)"
                )
            model, tokenizer = mlx_lm.load(clean_model)
            self._loaded_models[clean_model] = (model, tokenizer)

        return self._loaded_models[clean_model]

    def _format_chat(self, tokenizer: Any, messages: list[dict[str, str]]) -> str:
        """Applies chat template if available or falls back to prompt format."""
        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            try:
                return tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
            except Exception:
                pass

        # Fallback format
        lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            lines.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        lines.append("<|im_start|>assistant\n")
        return "\n".join(lines)

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        # Run synchronous MLX generation in background worker thread to avoid blocking asyncio loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.complete_sync(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            ),
        )

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str = "mlx-community/Qwen2.5-0.5B-Instruct-4bit",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        clean_model = model
        if clean_model.startswith("mlx/") or clean_model.startswith("metal/"):
            clean_model = clean_model.split("/", 1)[1]

        try:
            import mlx_lm
        except ImportError:
            raise ImportError(
                "MLX Metal provider requires: pip install semantic-harness[mlx] "
                "(or: pip install mlx mlx-lm on macOS Apple Silicon)"
            )

        mlx_model, tokenizer = self._load_model(clean_model)
        prompt = self._format_chat(tokenizer, messages)

        temp_val = temperature if temperature > 0 else 0.0
        response_text = mlx_lm.generate(
            model=mlx_model,
            tokenizer=tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            temp=temp_val,
            verbose=False,
            **kwargs,
        )

        return ProviderResponse(
            content=response_text.strip(),
            model=model,
            input_tokens=len(prompt.split()),
            output_tokens=len(response_text.split()),
            raw={"model": clean_model, "framework": "apple-mlx-metal"},
        )
