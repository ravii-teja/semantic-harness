"""
Unit and integration tests for P1-P3 roadmap features:
- P1: Multi-model empirical benchmark execution & stats
- P2: Distributed procedural cache storage (Disk & Redis) and TorchProvider 4/8-bit quantization
- P3: Turn-key observability web dashboard and TurboQuant ultra-dense matrix search
"""

import json
import os
import tempfile
import urllib.request
import pytest
import numpy as np

from semantic_harness.memory.procedural import (
    ProceduralMemory,
    DiskProceduralStorage,
    RedisProceduralStorage,
    CompiledProcedure,
)
from semantic_harness.providers.torch_provider import TorchProvider
from semantic_harness.visualization.dashboard import (
    generate_dashboard_html,
    serve_dashboard,
)
from semantic_harness.memory.turbo_quant import (
    PolarQuantizer,
    TurboQuantVectorIndex,
)
from semantic_harness.memory.graph import GraphMemory
from semantic_harness.telemetry.metrics import get_metrics_collector


def test_disk_and_redis_procedural_storage():
    """Verify DiskProceduralStorage and RedisProceduralStorage backends."""
    with tempfile.TemporaryDirectory() as tmpdir:
        disk_path = os.path.join(tmpdir, "proc_store.json")
        disk_storage = DiskProceduralStorage(filepath=disk_path)

        # 1. Test Disk Storage
        disk_storage.save_procedure("test_hash_1", {"intent_hash": "test_hash_1", "intent_text": "run pipeline"})
        assert disk_storage.get_procedure("test_hash_1")["intent_text"] == "run pipeline"
        assert "test_hash_1" in disk_storage.list_procedures()

        # 2. Test ProceduralMemory with Disk Storage
        proc_mem = ProceduralMemory(storage=disk_storage)
        proc_mem.compile("invoice task", trajectory={"status": "ok"}, min_success_count=1)
        proc_mem.record_success("invoice task")

        # Reload in a new instance sharing the storage
        proc_mem2 = ProceduralMemory(storage=disk_storage)
        hit = proc_mem2.lookup("invoice task", require_reliable=False)
        assert hit is not None
        assert hit.trajectory == {"status": "ok"}
        assert hit.success_count == 1

        # 3. Test Redis Storage (graceful degradation / in-memory replica)
        redis_storage = RedisProceduralStorage(redis_url="redis://localhost:6379/15")
        redis_storage.save_procedure("h_redis", {"intent_hash": "h_redis", "intent_text": "redis task"})
        assert redis_storage.get_procedure("h_redis")["intent_text"] == "redis task"
        assert "h_redis" in redis_storage.list_procedures()
        assert redis_storage.delete_procedure("h_redis") is True


def test_torch_provider_quantization_flags():
    """Verify TorchProvider accepts 4-bit, 8-bit, and compile flags."""
    p_4bit = TorchProvider(
        model_name_or_path="Qwen/Qwen2.5-0.5B-Instruct",
        load_in_4bit=True,
        torch_compile=True,
    )
    assert p_4bit.load_in_4bit is True
    assert p_4bit.torch_compile is True
    assert p_4bit.load_in_8bit is False

    p_8bit = TorchProvider(
        model_name_or_path="Qwen/Qwen2.5-0.5B-Instruct",
        load_in_8bit=True,
    )
    assert p_8bit.load_in_8bit is True
    assert p_8bit.load_in_4bit is False


def test_observability_dashboard_html_generation():
    """Verify generate_dashboard_html creates responsive dark-mode HTML."""
    collector = get_metrics_collector()
    collector.reset()
    collector.record_step("calc_tax", 0.025, status="success")
    collector.record_cache_hit("calc_tax")
    collector.record_tokens("qwen", 120, 30, cost_usd=0.0001)

    graph = GraphMemory()
    graph.add_entity("EntityA", "Company")
    graph.add_entity("EntityB", "Product")
    graph.add_triplet("EntityA", "manufactures", "EntityB")

    proc = ProceduralMemory()
    proc.compile("extract invoice", trajectory={"inv": 1}, min_success_count=1)
    proc.record_success("extract invoice")

    html = generate_dashboard_html(metrics=collector, graph=graph, procedural=proc)
    assert "<!DOCTYPE html>" in html
    assert "⚡ Semantic Harness Enterprise Dashboard" in html
    assert "EntityA" in html
    assert "extract invoice" in html
    assert "calc_tax" in html


def test_observability_dashboard_server():
    """Verify DashboardServer binds to port, serves metrics, and stops."""
    import socket
    # Find free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()

    server = serve_dashboard(port=port, host="127.0.0.1", open_browser=False)
    try:
        # 1. Fetch dashboard HTML
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            content = resp.read().decode("utf-8")
            assert "<title>" in content

        # 2. Fetch Prometheus exposition
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics") as resp:
            prom_content = resp.read().decode("utf-8")
            assert "semantic_harness" in prom_content

        # 3. Fetch API JSON summary
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/data") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert "step_calls_total" in data
    finally:
        server.stop()


def test_turbo_quant_ultra_dense_similarity_matrix():
    """Verify TurboQuant similarity_dense_matrix and vector search scaling."""
    quantizer = PolarQuantizer(dim=32, seed=42)
    q1 = quantizer.quantize([1.0] * 32)

    # Create 500 candidate vectors
    candidates = [quantizer.quantize([1.0 if (i % 2 == 0) else -1.0] * 32) for i in range(500)]
    matrix = np.array([list(c.packed_bits) for c in candidates], dtype=np.uint8)

    sims = PolarQuantizer.similarity_dense_matrix(q1, matrix)
    assert len(sims) == 500
    assert isinstance(sims, np.ndarray)
    assert np.all(sims >= -1.0) and np.all(sims <= 1.0)

    # Test TurboQuantVectorIndex scaling with matrix cache
    index = TurboQuantVectorIndex(dim=32)
    for i in range(128):
        index.add(f"k_{i}", f"intent number {i}", procedure={"step": i})

    results = index.search("intent number 10", top_k=5)
    assert len(results) > 0
    assert results[0].similarity >= 0.70
