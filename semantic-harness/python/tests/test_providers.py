"""Tests for LLM provider adapters and provider factory."""
import pytest
from semantic_harness.providers import (
    BaseProvider,
    ProviderResponse,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    HuggingFaceProvider,
    MLXProvider,
    get_provider,
)


class TestProviderFactory:
    def test_get_openai_provider(self):
        p = get_provider("gpt-4o-mini", api_key="sk-test")
        assert isinstance(p, OpenAIProvider)

    def test_get_anthropic_provider(self):
        p = get_provider("claude-sonnet-4-6", api_key="sk-ant-test")
        assert isinstance(p, AnthropicProvider)

    def test_get_ollama_provider(self):
        p = get_provider("qwen2.5:0.5b")
        assert isinstance(p, OllamaProvider)
        assert p.base_url == "http://localhost:11434"

    def test_get_ollama_prefix_provider(self):
        p = get_provider("ollama/llama3.2")
        assert isinstance(p, OllamaProvider)

    def test_get_huggingface_provider(self):
        p = get_provider("hf/meta-llama/Llama-3.2-1B-Instruct", api_key="hf_test")
        assert isinstance(p, HuggingFaceProvider)
        assert p.api_key == "hf_test"

    def test_get_mlx_provider(self):
        p = get_provider("mlx/Qwen2.5-0.5B-Instruct-4bit")
        assert isinstance(p, MLXProvider)

    def test_get_metal_prefix_provider(self):
        p = get_provider("metal/mlx-community/Llama-3.2-1B")
        assert isinstance(p, MLXProvider)


class TestProviderResponse:
    def test_response_dataclass(self):
        resp = ProviderResponse(
            content='{"result": "ok"}',
            model="test-model",
            input_tokens=15,
            output_tokens=5,
            raw={"id": "test_1"},
        )
        assert resp.content == '{"result": "ok"}'
        assert resp.model == "test-model"
        assert resp.input_tokens == 15
        assert resp.output_tokens == 5
        assert resp.raw["id"] == "test_1"


class TestHuggingFaceProviderPromptFormatting:
    def test_format_messages(self):
        hf = HuggingFaceProvider(api_key="mock_key")
        messages = [
            {"role": "system", "content": "You are a JSON assistant."},
            {"role": "user", "content": "Hello"},
        ]
        prompt = hf._format_messages_to_prompt(messages)
        assert "<|im_start|>system\nYou are a JSON assistant.<|im_end|>" in prompt
        assert "<|im_start|>user\nHello<|im_end|>" in prompt
        assert "<|im_start|>assistant\n" in prompt
