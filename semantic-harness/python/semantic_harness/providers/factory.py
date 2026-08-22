from __future__ import annotations
from typing import Any
from semantic_harness.providers.base import BaseProvider


def get_provider(model: str, **kwargs: Any) -> BaseProvider:
    """
    Auto-selects provider from model string.

    Examples:
        get_provider("gpt-4o-mini")                        -> OpenAIProvider
        get_provider("claude-sonnet-4-6")                  -> AnthropicProvider
        get_provider("qwen2.5:0.5b")                       -> OllamaProvider
        get_provider("ollama/llama3.2")                    -> OllamaProvider
        get_provider("hf/meta-llama/Llama-3.2-1B-Instruct") -> HuggingFaceProvider
        get_provider("huggingface/mistralai/Mistral-7B")   -> HuggingFaceProvider
        get_provider("mlx/Qwen2.5-0.5B-Instruct-4bit")      -> MLXProvider
        get_provider("metal/mlx-community/Llama-3.2-1B")    -> MLXProvider
    """
    m = model.lower()
    if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3"):
        from semantic_harness.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    elif m.startswith("claude"):
        from semantic_harness.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(**kwargs)
    elif m.startswith("hf/") or m.startswith("huggingface/"):
        from semantic_harness.providers.huggingface_provider import HuggingFaceProvider
        return HuggingFaceProvider(**kwargs)
    elif m.startswith("mlx/") or m.startswith("metal/"):
        from semantic_harness.providers.mlx_provider import MLXProvider
        return MLXProvider(**kwargs)
    elif ":" in m or m.startswith("ollama/") or m.startswith("qwen") or m.startswith("llama") or m.startswith("smol"):
        from semantic_harness.providers.ollama_provider import OllamaProvider
        base_url = kwargs.pop("base_url", "http://localhost:11434")
        return OllamaProvider(base_url=base_url)
    else:
        # Default to OpenAI-compatible
        from semantic_harness.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
