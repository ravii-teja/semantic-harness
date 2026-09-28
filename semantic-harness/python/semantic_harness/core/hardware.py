"""Hardware auto-detection and accelerator optimization engine.

Detects Apple Silicon Metal (MLX), NVIDIA CUDA GPUs, or host CPU with SIMD
capabilities, memory/VRAM availability, and recommends the fastest execution engine.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AcceleratorType(str, Enum):
    METAL = "metal"  # Apple Silicon M-series (MLX / Metal)
    CUDA = "cuda"    # NVIDIA CUDA GPU
    ROCM = "rocm"    # AMD ROCm GPU
    CPU = "cpu"      # Generic CPU (x86_64, arm64, AVX)


@dataclass
class HardwareProfile:
    """Hardware profile describing host accelerator, memory, and engine recommendations."""
    accelerator: AcceleratorType
    device_name: str
    total_memory_gb: float
    available_memory_gb: float
    cpu_cores: int
    recommended_model: str
    recommended_provider: str
    metadata: dict[str, Any]

    def summary(self) -> str:
        return (
            f"Accelerator: {self.accelerator.value.upper()} ({self.device_name}) | "
            f"RAM/VRAM: {self.available_memory_gb:.1f}GB / {self.total_memory_gb:.1f}GB | "
            f"Cores: {self.cpu_cores} | Recommended: {self.recommended_model} ({self.recommended_provider})"
        )


class HardwareDetector:
    """Detects available hardware acceleration and returns optimal model configurations."""

    @staticmethod
    def detect() -> HardwareProfile:
        # 1. Check for Apple Silicon Metal (macOS arm64)
        if sys.platform == "darwin" and platform.machine() == "arm64":
            profile = HardwareDetector._detect_apple_silicon()
            if profile:
                return profile

        # 2. Check for NVIDIA CUDA
        cuda_profile = HardwareDetector._detect_cuda()
        if cuda_profile:
            return cuda_profile

        # 3. Fallback to CPU
        return HardwareDetector._detect_cpu()

    @staticmethod
    def detect_frameworks() -> dict[str, Any]:
        """Detect installed deep learning tensor frameworks and their accelerator status."""
        frameworks: dict[str, Any] = {
            "torch": {"available": False, "version": None, "cuda": False, "mps": False, "rocm": False},
            "tensorflow": {"available": False, "version": None, "gpu": False, "gpu_count": 0},
        }

        # Inspect PyTorch
        try:
            import torch
            frameworks["torch"]["available"] = True
            frameworks["torch"]["version"] = torch.__version__
            frameworks["torch"]["cuda"] = bool(torch.cuda.is_available())
            frameworks["torch"]["cuda_count"] = torch.cuda.device_count() if torch.cuda.is_available() else 0
            # Apple Silicon MPS (Metal Performance Shaders)
            frameworks["torch"]["mps"] = bool(
                hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
            )
            # AMD ROCm HIP
            frameworks["torch"]["rocm"] = bool(getattr(torch.version, "hip", None) is not None)
        except Exception:
            pass

        # Inspect TensorFlow
        try:
            import tensorflow as tf  # noqa: F401
            frameworks["tensorflow"]["available"] = True
            frameworks["tensorflow"]["version"] = getattr(tf, "__version__", None)
            gpus = tf.config.list_physical_devices("GPU")
            frameworks["tensorflow"]["gpu"] = len(gpus) > 0
            frameworks["tensorflow"]["gpu_count"] = len(gpus)
        except Exception:
            pass

        return frameworks

    @staticmethod
    def _detect_apple_silicon() -> HardwareProfile | None:
        try:
            # Check unified memory using sysctl
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
            total_bytes = int(out)
            total_gb = total_bytes / (1024**3)
        except Exception:
            total_gb = 16.0

        cpu_cores = os.cpu_count() or 8
        frameworks = HardwareDetector.detect_frameworks()

        # Check if MLX is available
        has_mlx = False
        try:
            import mlx.core as mx  # noqa: F401
            has_mlx = True
        except ImportError:
            has_mlx = False

        if has_mlx:
            recommended_model = (
                "mlx/Qwen2.5-0.5B-Instruct-4bit" if total_gb < 16 else "mlx/Qwen2.5-Coder-3B-Instruct-4bit"
            )
            recommended_provider = "mlx"
        elif frameworks["torch"]["mps"]:
            recommended_model = "qwen2.5:0.5b" if total_gb < 16 else "qwen2.5-coder:3b"
            recommended_provider = "torch"
        else:
            recommended_model = "qwen2.5:0.5b" if total_gb < 16 else "qwen2.5-coder:3b"
            recommended_provider = "ollama"

        return HardwareProfile(
            accelerator=AcceleratorType.METAL,
            device_name=f"Apple Silicon ({platform.processor() or 'M-Series'})",
            total_memory_gb=round(total_gb, 2),
            available_memory_gb=round(total_gb * 0.75, 2),  # Estimated unified memory headroom
            cpu_cores=cpu_cores,
            recommended_model=recommended_model,
            recommended_provider=recommended_provider,
            metadata={
                "apple_silicon": True,
                "mlx_installed": has_mlx,
                "torch_mps": frameworks["torch"]["mps"],
                "tensor_frameworks": frameworks,
            },
        )

    @staticmethod
    def _detect_cuda() -> HardwareProfile | None:
        frameworks = HardwareDetector.detect_frameworks()

        # Try PyTorch CUDA / ROCm if available
        try:
            import torch
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                device_name = torch.cuda.get_device_name(0)
                vram_bytes = torch.cuda.get_device_properties(0).total_memory
                total_vram_gb = vram_bytes / (1024**3)

                is_rocm = frameworks["torch"]["rocm"]
                accel_type = AcceleratorType.ROCM if is_rocm else AcceleratorType.CUDA
                rec_model = "qwen2.5-coder:3b" if total_vram_gb >= 6.0 else "qwen2.5:0.5b"
                return HardwareProfile(
                    accelerator=accel_type,
                    device_name=f"{device_name} (x{device_count})",
                    total_memory_gb=round(total_vram_gb, 2),
                    available_memory_gb=round(total_vram_gb * 0.85, 2),
                    cpu_cores=os.cpu_count() or 4,
                    recommended_model=rec_model,
                    recommended_provider="ollama",
                    metadata={
                        "cuda_device_count": device_count,
                        "torch_cuda": True,
                        "is_rocm": is_rocm,
                        "tensor_frameworks": frameworks,
                    },
                )
        except Exception:
            pass

        # Try nvidia-smi command if torch is not installed
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            if out:
                lines = out.split("\n")
                first_gpu = lines[0].split(",")
                name = first_gpu[0].strip()
                vram_mb = float(first_gpu[1].strip())
                vram_gb = vram_mb / 1024.0

                rec_model = "qwen2.5-coder:3b" if vram_gb >= 6.0 else "qwen2.5:0.5b"
                return HardwareProfile(
                    accelerator=AcceleratorType.CUDA,
                    device_name=name,
                    total_memory_gb=round(vram_gb, 2),
                    available_memory_gb=round(vram_gb * 0.85, 2),
                    cpu_cores=os.cpu_count() or 4,
                    recommended_model=rec_model,
                    recommended_provider="ollama",
                    metadata={
                        "cuda_devices": len(lines),
                        "nvidia_smi": True,
                        "tensor_frameworks": frameworks,
                    },
                )
        except Exception:
            pass

        return None

    @staticmethod
    def _detect_cpu() -> HardwareProfile:
        total_ram_gb = 8.0
        avail_ram_gb = 4.0
        try:
            import psutil
            total_ram_gb = psutil.virtual_memory().total / (1024**3)
            avail_ram_gb = psutil.virtual_memory().available / (1024**3)
        except (ImportError, Exception):
            # Fallback for Linux /proc/meminfo or macOS sysctl
            try:
                if sys.platform == "darwin":
                    out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], timeout=1).decode().strip()
                    total_ram_gb = int(out) / (1024**3)
                    avail_ram_gb = total_ram_gb * 0.5
                elif os.path.exists("/proc/meminfo"):
                    with open("/proc/meminfo") as f:
                        for line in f:
                            if line.startswith("MemTotal:"):
                                kb = int(line.split()[1])
                                total_ram_gb = kb / (1024**2)
                            elif line.startswith("MemAvailable:"):
                                kb = int(line.split()[1])
                                avail_ram_gb = kb / (1024**2)
            except Exception:
                pass

        cpu_cores = os.cpu_count() or 4
        frameworks = HardwareDetector.detect_frameworks()

        # For CPU execution, recommend compact 0.5B or 1B models to keep latency low
        recommended_model = "qwen2.5:0.5b" if avail_ram_gb < 8.0 else "llama3.2:1b"

        return HardwareProfile(
            accelerator=AcceleratorType.CPU,
            device_name=f"Host CPU ({platform.machine()})",
            total_memory_gb=round(total_ram_gb, 2),
            available_memory_gb=round(avail_ram_gb, 2),
            cpu_cores=cpu_cores,
            recommended_model=recommended_model,
            recommended_provider="ollama",
            metadata={
                "platform": sys.platform,
                "machine": platform.machine(),
                "tensor_frameworks": frameworks,
            },
        )


def get_default_local_model() -> str:
    """Helper to detect host hardware and return the optimal model identifier."""
    profile = HardwareDetector.detect()
    return profile.recommended_model
