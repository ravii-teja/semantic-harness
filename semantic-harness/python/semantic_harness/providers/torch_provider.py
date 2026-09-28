"""
PyTorch and HuggingFace Transformers native in-process model provider.

Runs local quantized and full-precision weights directly in VRAM/RAM
on NVIDIA CUDA, Apple Silicon Metal (MPS), or CPU without external server daemons.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from semantic_harness.providers.base import BaseProvider, ProviderResponse


class TorchProvider(BaseProvider):
    """
    In-process local LLM execution via PyTorch and HuggingFace Transformers.

    Supports direct device mapping (CUDA, MPS, CPU), automatic half-precision (bfloat16/float16),
    and in-memory weight reuse across turns.
    """

    def __init__(
        self,
        model_name_or_path: str = "Qwen/Qwen2.5-0.5B-Instruct",
        device: str = "auto",
        torch_dtype: str = "auto",
        trust_remote_code: bool = True,
        load_in_4bit: bool = False,
        load_in_8bit: bool = False,
        torch_compile: bool = False,
        **kwargs: Any,
    ) -> None:
        self.model_name_or_path: str = model_name_or_path
        self.device_setting: str = device
        self.torch_dtype_setting: str = torch_dtype
        self.trust_remote_code: bool = trust_remote_code
        self.load_in_4bit: bool = load_in_4bit
        self.load_in_8bit: bool = load_in_8bit
        self.torch_compile: bool = torch_compile
        self.kwargs: Dict[str, Any] = kwargs
        self._model: Any = None
        self._tokenizer: Any = None
        self._device: Optional[str] = None

    def _resolve_device(self) -> str:
        """Resolve device target (cuda, mps, cpu)."""
        if self.device_setting != "auto":
            return self.device_setting

        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        except ImportError:
            return "cpu"

    def _ensure_loaded(self) -> None:
        """Lazy-load the tokenizer and model into GPU/CPU memory."""
        if self._model is not None and self._tokenizer is not None:
            return

        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "PyTorch and Transformers are required for TorchProvider.\n"
                "Install them with: pip install 'semantic-harness[torch]'"
            ) from exc

        self._device = self._resolve_device()
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name_or_path,
            trust_remote_code=self.trust_remote_code,
            **self.kwargs,
        )

        dtype: Any = "auto"
        if self.torch_dtype_setting == "bfloat16":
            dtype = torch.bfloat16
        elif self.torch_dtype_setting == "float16":
            dtype = torch.float16
        elif self.torch_dtype_setting == "float32":
            dtype = torch.float32

        model_kwargs = dict(self.kwargs)
        device_map_setting = self._device if self._device != "cpu" else None

        if self.load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16 if dtype == "auto" else dtype,
                    bnb_4bit_quant_type="nf4",
                )
                device_map_setting = "auto"
            except ImportError:
                pass
        elif self.load_in_8bit:
            try:
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                device_map_setting = "auto"
            except ImportError:
                pass

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name_or_path,
            torch_dtype=dtype,
            device_map=device_map_setting,
            trust_remote_code=self.trust_remote_code,
            **model_kwargs,
        )
        if (self._device == "cpu" or self._device == "mps") and not (self.load_in_4bit or self.load_in_8bit):
            try:
                self._model = self._model.to(self._device)
            except Exception:
                pass

        if self.torch_compile and hasattr(torch, "compile"):
            try:
                self._model = torch.compile(self._model)
            except Exception:
                pass

    def _format_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Format messages using tokenizer chat template or fallback prompt."""
        if hasattr(self._tokenizer, "apply_chat_template") and self._tokenizer.chat_template:
            try:
                formatted = self._tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                if isinstance(formatted, str):
                    return formatted
            except Exception:
                pass

        # Fallback text formatting
        lines: List[str] = []
        for m in messages:
            role = m.get("role", "user").capitalize()
            content = m.get("content", "")
            lines.append(f"{role}: {content}")
        lines.append("Assistant: ")
        return "\n".join(lines)

    def complete_sync(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Synchronously complete chat messages using PyTorch."""
        self._ensure_loaded()
        import torch

        prompt = self._format_prompt(messages)
        inputs = self._tokenizer(prompt, return_tensors="pt")
        if self._device:
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

        input_tokens = int(inputs["input_ids"].shape[-1])

        gen_kwargs: Dict[str, Any] = {
            "max_new_tokens": max_tokens,
            "pad_token_id": self._tokenizer.eos_token_id or self._tokenizer.pad_token_id,
        }
        if temperature > 0.0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temperature
        else:
            gen_kwargs["do_sample"] = False

        with torch.no_grad():
            outputs = self._model.generate(**inputs, **gen_kwargs)

        new_tokens = outputs[0][input_tokens:]
        output_tokens = len(new_tokens)
        content = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        return ProviderResponse(
            content=content,
            model=model or self.model_name_or_path,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw={"device": self._device},
        )

    async def complete(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Asynchronously complete chat messages by running execution in background thread."""
        return await asyncio.to_thread(
            self.complete_sync,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )
