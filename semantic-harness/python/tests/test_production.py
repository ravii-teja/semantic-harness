"""
Production-readiness validation tests for Semantic Harness:
- Transparent async/await @step execution and cache reuse
- Multi-process procedural cache durability and atomic file persistence
- Thread safety and re-entrant locking for ProceduralMemory and TokenomicsTracker
- Prometheus metrics collector and exposition
- OpenTelemetry-compatible tracing infrastructure
- Operator CLI commands
"""

import asyncio
import concurrent.futures
import json
import os
import tempfile
import pytest
from pydantic import BaseModel

from semantic_harness import (
    SemanticLayer,
    ProceduralMemory,
    TokenomicsTracker,
    MetricsCollector,
    SemanticTracer,
)
from semantic_harness.cli import main as cli_main


# ---------------------------------------------------------------------------
# 1. Transparent Async/Await @step & Cache Reuse
# ---------------------------------------------------------------------------

class UserOutput(BaseModel):
    user_id: int
    name: str


@pytest.mark.asyncio
async def test_async_step_execution_and_cache_hit():
    """Verify async coroutines decorated with @layer.step execute and hit cache."""
    layer = SemanticLayer()
    execution_counter = 0

    @layer.step(cache=True, validates=UserOutput)
    async def fetch_user(uid: int):
        nonlocal execution_counter
        execution_counter += 1
        await asyncio.sleep(0.01)
        return {"user_id": uid, "name": f"User_{uid}"}

    # 1. Cold execution
    res1 = await fetch_user(42)
    assert res1 == UserOutput(user_id=42, name="User_42")
    assert execution_counter == 1
    assert layer.stats["steps"]["fetch_user"]["calls"] == 1
    assert layer.stats["steps"]["fetch_user"]["cache_hits"] == 0

    # 2. Warm cache hit (should return compiled procedure without invoking coroutine)
    res2 = await fetch_user(42)
    assert res2 == UserOutput(user_id=42, name="User_42")
    assert execution_counter == 1
    assert layer.stats["steps"]["fetch_user"]["calls"] == 2
    assert layer.stats["steps"]["fetch_user"]["cache_hits"] == 1


@pytest.mark.asyncio
async def test_async_step_validation_retry():
    """Verify retry logic on async coroutines when output fails validation."""
    layer = SemanticLayer()
    attempt = 0

    @layer.step(cache=True, validates=UserOutput, max_retries=2)
    async def flaky_user():
        nonlocal attempt
        attempt += 1
        await asyncio.sleep(0.01)
        if attempt == 1:
            # Missing user_id -> schema invalid
            return {"name": "Flaky"}
        return {"user_id": 100, "name": "Recovered"}

    res = await flaky_user()
    assert res == UserOutput(user_id=100, name="Recovered")
    assert attempt == 2


# ---------------------------------------------------------------------------
# 2. Procedural Cache Durability & Multi-Process Persistence
# ---------------------------------------------------------------------------

def test_procedural_memory_atomic_persistence():
    """Verify procedural memory saves, loads, and auto-persists to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "cache.json")

        # Instance 1: write procedures
        mem1 = ProceduralMemory(persist_path=cache_file)
        mem1.compile(
            intent="query_sales",
            trajectory={"sql": "SELECT sum(amount) FROM sales"},
            schema_fingerprint="fp_123",
            min_success_count=1,
        )
        mem1.record_success("query_sales")

        assert os.path.exists(cache_file)
        assert mem1.size == 1

        # Instance 2: loaded from the same path
        mem2 = ProceduralMemory(persist_path=cache_file)
        assert mem2.size == 1
        proc, explanation = mem2.explain_lookup("query_sales", schema_fingerprint="fp_123")
        assert proc is not None
        assert explanation.is_reused is True
        assert proc.procedure == {"sql": "SELECT sum(amount) FROM sales"}


def test_procedural_memory_explicit_save_load():
    """Verify explicit save and load methods."""
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "exported.json")
        mem = ProceduralMemory()
        mem.compile("intent_a", {"result": "ok"})
        mem.save(save_path)

        mem_new = ProceduralMemory()
        assert mem_new.size == 0
        mem_new.load(save_path)
        assert mem_new.size == 1
        assert any(p.intent_text == "intent_a" for p in mem_new.get_all())


# ---------------------------------------------------------------------------
# 3. Thread Safety & Re-entrant Locking
# ---------------------------------------------------------------------------

def test_procedural_memory_concurrent_writes():
    """Verify ProceduralMemory is thread-safe under concurrent compiles and lookups."""
    memory = ProceduralMemory()

    def worker(worker_id: int):
        for i in range(25):
            intent = f"intent_{worker_id}_{i}"
            memory.compile(intent, {"val": i}, min_success_count=1)
            memory.record_success(intent)
            res, _ = memory.explain_lookup(intent)
            assert res is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, w) for w in range(8)]
        concurrent.futures.wait(futures)
        for f in futures:
            assert f.exception() is None

    assert memory.size == 200


def test_tokenomics_tracker_concurrent_writes():
    """Verify TokenomicsTracker is thread-safe under concurrent records."""
    tracker = TokenomicsTracker()

    def worker(worker_id: int):
        for i in range(50):
            tracker.record_turn(
                turn_id=f"turn_{worker_id}_{i}",
                model_name="gpt-4o",
                prompt_tokens=10,
                completion_tokens=5,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(worker, w) for w in range(6)]
        concurrent.futures.wait(futures)
        for f in futures:
            assert f.exception() is None

    assert tracker.total_prompt_tokens == 3000
    assert tracker.total_completion_tokens == 1500
    assert tracker.total_turns == 300


# ---------------------------------------------------------------------------
# 4. Enterprise Observability (Prometheus & OpenTelemetry)
# ---------------------------------------------------------------------------

def test_prometheus_metrics_export():
    """Verify Prometheus text exposition format."""
    collector = MetricsCollector()
    collector.record_step("synthesize_query", duration_sec=0.045, status="success")
    collector.record_step("synthesize_query", duration_sec=0.055, status="success")
    collector.record_cache_hit("synthesize_query")
    collector.record_tokens("claude-3-5-sonnet", prompt_tokens=150, completion_tokens=50, cost_usd=0.001)
    collector.set_cache_size(12)

    output = collector.export_prometheus()
    assert "# TYPE semantic_harness_step_calls_total counter" in output
    assert 'semantic_harness_step_calls_total{step="synthesize_query",status="success"} 2' in output
    assert 'semantic_harness_cache_hits_total{step="synthesize_query"} 1' in output
    assert "semantic_harness_step_duration_seconds" in output
    assert 'semantic_harness_tokens_total{model="claude-3-5-sonnet",type="prompt"} 150' in output
    assert "semantic_harness_procedural_cache_size 12" in output


def test_opentelemetry_tracing():
    """Verify OpenTelemetry tracer span hierarchy and event recording."""
    tracer = SemanticTracer(service_name="test-pipeline")

    with tracer.span("parent_turn", attributes={"agent.id": "agt_01"}) as parent:
        parent.add_event("start_reasoning")
        with tracer.span("sub_tool_call", attributes={"tool.name": "calculator"}) as child:
            child.set_attribute("tool.result", 42)

    spans = tracer.get_spans()
    assert len(spans) == 2
    parent_span = next(s for s in spans if s.name == "parent_turn")
    child_span = next(s for s in spans if s.name == "sub_tool_call")

    assert child_span.parent_id == parent_span.span_id
    assert child_span.trace_id == parent_span.trace_id
    assert child_span.status == "OK"
    assert child_span.duration_seconds >= 0.0
    assert child_span.attributes["tool.result"] == 42

    json_export = tracer.export_json()
    parsed = json.loads(json_export)
    assert len(parsed) == 2


# ---------------------------------------------------------------------------
# 5. Operator CLI Verification
# ---------------------------------------------------------------------------

def test_cli_version_and_hardware(capsys):
    """Verify CLI basic commands execute with 0 exit code."""
    # Hardware detection
    code = cli_main(["hardware"])
    assert code == 0
    out = capsys.readouterr().out
    assert "Semantic Harness Hardware Profile" in out

    # Metrics
    code = cli_main(["metrics"])
    assert code == 0


def test_cli_cache_inspect_and_export(capsys):
    """Verify CLI cache inspect and export operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "cli_cache.json")
        mem = ProceduralMemory(persist_path=cache_file)
        mem.compile("cli_test_intent", {"action": "execute"}, schema_fingerprint="fp_abc")

        # Inspect
        code = cli_main(["cache", "inspect", cache_file])
        assert code == 0
        out = capsys.readouterr().out
        assert "Total compiled procedures: 1" in out
        assert "cli_test_intent" in out

        # Export
        code = cli_main(["cache", "export", cache_file])
        assert code == 0
        out = capsys.readouterr().out
        assert "cli_test_intent" in out
        assert "execute" in out
