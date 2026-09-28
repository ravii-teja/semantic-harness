"""
Tests for PyTorch & TensorFlow deep acceleration capabilities:
- HardwareDetector framework discovery (PyTorch, TensorFlow, MPS, CUDA, ROCm)
- PolarQuantizer batched tensor operations (FWHT, sign rotation, similarity batching)
- TurboQuantVectorIndex accelerated search
- TorchProvider initialization, device resolution, and factory dispatch
"""

import math
import pytest
from unittest.mock import MagicMock, patch

from semantic_harness import (
    HardwareDetector,
    PolarQuantizer,
    TurboQuantVectorIndex,
    TorchProvider,
    get_provider,
)
from semantic_harness.memory.turbo_quant import _torch_fwht, _fast_walsh_hadamard_transform


# ---------------------------------------------------------------------------
# 1. Framework Discovery in HardwareDetector
# ---------------------------------------------------------------------------

def test_hardware_detector_framework_discovery():
    """Verify detect_frameworks identifies torch and tensorflow structures."""
    frameworks = HardwareDetector.detect_frameworks()
    assert "torch" in frameworks
    assert "tensorflow" in frameworks
    assert isinstance(frameworks["torch"]["available"], bool)
    assert isinstance(frameworks["tensorflow"]["available"], bool)

    profile = HardwareDetector.detect()
    assert "tensor_frameworks" in profile.metadata
    assert profile.metadata["tensor_frameworks"] == frameworks


def test_hardware_detector_mock_cuda_and_mps():
    """Verify hardware profile identifies CUDA and MPS when torch is mocked."""
    mock_torch = MagicMock()
    mock_torch.__version__ = "2.5.0"
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.device_count.return_value = 2
    mock_torch.cuda.get_device_name.return_value = "NVIDIA H100 80GB HBM3"
    props = MagicMock()
    props.total_memory = 80 * (1024**3)
    mock_torch.cuda.get_device_properties.return_value = props
    mock_torch.backends.mps.is_available.return_value = False
    mock_torch.version.hip = None

    with patch.dict("sys.modules", {"torch": mock_torch}):
        profile = HardwareDetector._detect_cuda()
        assert profile is not None
        assert profile.accelerator.value == "cuda"
        assert "NVIDIA H100" in profile.device_name
        assert profile.total_memory_gb == 80.0
        assert profile.recommended_model == "qwen2.5-coder:3b"


# ---------------------------------------------------------------------------
# 2. PolarQuantizer Batched Tensor & Fallback Operations
# ---------------------------------------------------------------------------

def test_torch_fwht_numerical_equivalence():
    """Verify _torch_fwht produces identical outputs to recursive FWHT."""
    try:
        import torch
    except ImportError:
        pytest.skip("PyTorch not installed in test environment")

    # Test on power of 2 vector
    dim = 8
    vec = [float(i + 1) for i in range(dim)]
    expected = _fast_walsh_hadamard_transform(vec)

    t_in = torch.tensor([vec], dtype=torch.float32)
    t_out = _torch_fwht(t_in).squeeze(0).tolist()

    assert len(t_out) == dim
    for a, b in zip(expected, t_out):
        assert abs(a - b) < 1e-5


def test_polar_quantizer_batch_and_similarity_batch():
    """Verify quantize_batch and similarity_batch operate correctly."""
    quantizer = PolarQuantizer(dim=16, seed=123)
    vectors = [
        [float(i) for i in range(16)],
        [float(15 - i) for i in range(16)],
        [1.0] * 16,
    ]

    # Quantize batch
    batch_q = quantizer.quantize_batch(vectors)
    assert len(batch_q) == 3

    # Verify individual quantization matches batch results
    for i, vec in enumerate(vectors):
        single_q = quantizer.quantize(vec)
        assert batch_q[i].dim == single_q.dim
        assert batch_q[i].padded_dim == single_q.padded_dim
        assert abs(batch_q[i].norm - single_q.norm) < 1e-4

    # Similarity batch
    query_q = batch_q[0]
    sims = PolarQuantizer.similarity_batch(query_q, batch_q)
    assert len(sims) == 3
    # Self-similarity should be ~1.0
    assert sims[0] > 0.95


# ---------------------------------------------------------------------------
# 3. TurboQuantVectorIndex Vectorized Search
# ---------------------------------------------------------------------------

def test_turbo_quant_vector_index_search():
    """Verify TurboQuantVectorIndex search works with batched similarity evaluation."""
    index = TurboQuantVectorIndex(dim=16, seed=42)
    index.add("k1", "analyze sales trends", {"step": 1})
    index.add("k2", "summarize customer feedback", {"step": 2})
    index.add("k3", "calculate quarterly revenue", {"step": 3})

    assert len(index) == 3

    results = index.search("sales quarterly revenue analysis", top_k=2, min_similarity=0.1)
    assert len(results) > 0
    assert results[0].similarity >= results[-1].similarity


# ---------------------------------------------------------------------------
# 4. TorchProvider & Provider Factory Routing
# ---------------------------------------------------------------------------

def test_torch_provider_factory_routing():
    """Verify factory routes torch/ and cuda/ prefixes to TorchProvider."""
    provider = get_provider("torch/Qwen/Qwen2.5-0.5B-Instruct")
    assert isinstance(provider, TorchProvider)
    assert provider.model_name_or_path == "Qwen/Qwen2.5-0.5B-Instruct"

    provider_cuda = get_provider("cuda/meta-llama/Llama-3.2-1B-Instruct")
    assert isinstance(provider_cuda, TorchProvider)
    assert provider_cuda.model_name_or_path == "meta-llama/Llama-3.2-1B-Instruct"


def test_torch_provider_device_resolution():
    """Verify TorchProvider resolves auto device target correctly."""
    provider = TorchProvider("test-model", device="auto")
    dev = provider._resolve_device()
    assert dev in ("cuda", "mps", "cpu")

    provider_explicit = TorchProvider("test-model", device="cpu")
    assert provider_explicit._resolve_device() == "cpu"
