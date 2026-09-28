"""Tests for the semantic-harness core modules."""
from pydantic import BaseModel

from semantic_harness.core.context import ContextAssembler
from semantic_harness.core.events import Event, EventBus, EventType
from semantic_harness.guard.guards import RepeatToolGuard, StepBudgetGuard
from semantic_harness.memory.long_term import LongTermMemory
from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.memory.short_term import ShortTermMemory
from semantic_harness.middleware import SemanticLayer
from semantic_harness.semantics.budget import ContextBudget
from semantic_harness.semantics.c2c import C2CValidator

# --- Event Bus ---

class TestEventBus:
    def test_emit_and_query(self):
        bus = EventBus()
        bus.emit(Event(EventType.TURN_START, data="hello", source="test"))
        events = bus.query(event_type=EventType.TURN_START)
        assert len(events) == 1
        assert events[0].data == "hello"

    def test_listener(self):
        bus = EventBus()
        captured = []
        bus.on(EventType.AGENT_RESPONSE, lambda e: captured.append(e.data))
        bus.emit(Event(EventType.AGENT_RESPONSE, data="response_data", source="test"))
        assert captured == ["response_data"]

    def test_query_with_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.emit(Event(EventType.STEP_START, data=i, source="test"))
        assert len(bus.query(EventType.STEP_START, limit=3)) == 3

    def test_render_history(self):
        bus = EventBus()
        bus.emit(Event(EventType.TURN_START, data="task", source="loop"))
        rendered = bus.render_history()
        assert "Event History" in rendered
        assert "turn/start" in rendered


# --- Context Assembler ---

class TestContextAssembler:
    def test_static_block(self):
        ctx = ContextAssembler()
        ctx.set_static("system", "You are a helper.")
        rendered = ctx.render()
        assert "You are a helper." in rendered

    def test_dynamic_block(self):
        ctx = ContextAssembler()
        ctx.set_dynamic("time", lambda: "Current time: 12:00")
        rendered = ctx.render()
        assert "Current time: 12:00" in rendered

    def test_remove(self):
        ctx = ContextAssembler()
        ctx.set_static("x", "value")
        ctx.remove("x")
        rendered = ctx.render()
        assert "value" not in rendered


# --- Short-Term Memory ---

class TestShortTermMemory:
    def test_add_and_get(self):
        mem = ShortTermMemory(max_items=5)
        mem.add("Hello", role="user")
        messages = mem.get_messages()
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"

    def test_bounded(self):
        mem = ShortTermMemory(max_items=3)
        for i in range(5):
            mem.add(f"msg-{i}")
        assert mem.size == 3

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("test")
        mem.clear()
        assert mem.size == 0


# --- Long-Term Memory ---

class TestLongTermMemory:
    def test_remember_and_recall(self):
        mem = LongTermMemory(":memory:")
        mem.remember("fact1", "The sky is blue", importance=0.9)
        mem.remember("fact2", "Water is wet", importance=0.5)
        recalled = mem.recall(k=2)
        assert len(recalled) == 2
        assert recalled[0].content == "The sky is blue"  # Higher importance

    def test_search(self):
        mem = LongTermMemory(":memory:")
        mem.remember("f1", "Python is great for ML")
        mem.remember("f2", "Rust is great for performance")
        results = mem.search("Python")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_forget(self):
        mem = LongTermMemory(":memory:")
        mem.remember("f1", "temporary")
        mem.forget("f1")
        assert mem.count() == 0

    def test_count(self):
        mem = LongTermMemory(":memory:")
        mem.remember("a", "alpha")
        mem.remember("b", "beta")
        assert mem.count() == 2


# --- Procedural Memory ---

class TestProceduralMemory:
    def test_cache_and_lookup(self):
        proc = ProceduralMemory()
        proc.cache("format csv", {"steps": ["parse", "transform"]})
        hit = proc.lookup("format csv")
        assert hit is not None
        assert hit.procedure == {"steps": ["parse", "transform"]}

    def test_confidence(self):
        proc = ProceduralMemory()
        proc.cache("task", "result")
        for _ in range(5):
            proc.record_success("task")
        hit = proc.lookup("task")
        assert hit.is_reliable  # 5 successes, 0 failures

    def test_auto_invalidation(self):
        proc = ProceduralMemory()
        proc.cache("bad_task", "result")
        for _ in range(4):
            proc.record_failure("bad_task")
        assert proc.lookup("bad_task") is None  # Auto-removed

    def test_case_insensitive(self):
        proc = ProceduralMemory()
        proc.cache("Format CSV", "result")
        hit = proc.lookup("format csv")
        assert hit is not None

    def test_explain_lookup_and_schema_guard(self):
        proc = ProceduralMemory()
        proc.compile(
            intent="extract user",
            trajectory={"user_id": 1, "name": "Ada"},
            schema_fingerprint="fp_schema_v1",
            min_confidence=0.8,
            min_success_count=2,
        )
        # Not yet reliable
        _, exp_unreliable = proc.explain_lookup("extract user", schema_fingerprint="fp_schema_v1", require_reliable=True)
        assert exp_unreliable.status.value == "unreliable"

        # Record 2 successes to make it reliable
        proc.record_success("extract user")
        proc.record_success("extract user")

        # Now reliable with matching schema
        hit, exp_reused = proc.explain_lookup("extract user", schema_fingerprint="fp_schema_v1", require_reliable=True)
        assert exp_reused.is_reused
        assert hit is not None
        assert hit.trajectory == {"user_id": 1, "name": "Ada"}

        # Attempt reuse with drifted schema -> REJECTED
        hit_drift, exp_drift = proc.explain_lookup("extract user", schema_fingerprint="fp_schema_v2_altered", require_reliable=True)
        assert hit_drift is None
        assert exp_drift.status.value == "schema_mismatch"
        assert "Schema fingerprint mismatch" in (exp_drift.rejection_reason or "")

    def test_tool_version_precondition_guard(self):
        proc = ProceduralMemory()
        proc.compile(
            intent="query database",
            trajectory=["sql_query('SELECT * FROM users')"],
            tool_signatures={"sql_query": "v1.2.0"},
            min_success_count=1,
        )
        proc.record_success("query database")

        # Matching tool signature
        hit, exp = proc.explain_lookup("query database", tool_signatures={"sql_query": "v1.2.0"})
        assert exp.is_reused
        assert hit is not None

        # Altered tool signature -> REJECTED
        hit_mismatch, exp_mismatch = proc.explain_lookup("query database", tool_signatures={"sql_query": "v2.0.0"})
        assert hit_mismatch is None
        assert exp_mismatch.status.value == "tool_version_mismatch"


# --- C2C Validator ---

class ReportSchema(BaseModel):
    title: str
    findings: list[str]
    confidence: float


class TestC2CValidator:
    def test_valid_data(self):
        v = C2CValidator()
        result = v.validate(
            {"title": "Report", "findings": ["finding1"], "confidence": 0.9},
            ReportSchema,
        )
        assert result.valid
        assert result.data.title == "Report"

    def test_invalid_data(self):
        v = C2CValidator()
        result = v.validate(
            {"title": "Report"},  # Missing required fields
            ReportSchema,
        )
        assert not result.valid
        assert len(result.errors) > 0
        assert "retry_prompt" in result.model_dump()

    def test_retry_prompt_is_actionable(self):
        v = C2CValidator()
        result = v.validate({"title": 123}, ReportSchema)
        assert "Please fix" in result.retry_prompt or "Please regenerate" in result.retry_prompt

    def test_stats(self):
        v = C2CValidator()
        v.validate({"title": "R", "findings": [], "confidence": 0.5}, ReportSchema)
        v.validate({"bad": True}, ReportSchema)
        assert v.stats["validations"] == 2
        assert v.stats["successes"] == 1
        assert v.stats["failures"] == 1


# --- Context Budget ---

class TestContextBudget:
    def test_estimate(self):
        budget = ContextBudget(max_tokens=100)
        assert budget.estimate_tokens("a" * 400) == 100

    def test_fits(self):
        budget = ContextBudget(max_tokens=100)
        assert budget.fits("short")
        assert not budget.fits("a" * 500)

    def test_pressure(self):
        budget = ContextBudget(max_tokens=100)
        assert budget.pressure(80) == 0.8
        assert budget.pressure(120) == 1.0


# --- Semantic Layer Middleware ---

class ItemSchema(BaseModel):
    name: str
    value: int


class TestSemanticLayer:
    def test_step_decorator_passthrough(self):
        layer = SemanticLayer()

        @layer.step()
        def my_fn(x):
            return x * 2

        assert my_fn(5) == 10

    def test_step_with_validation(self):
        layer = SemanticLayer()

        @layer.step(validates=ItemSchema)
        def my_fn():
            return {"name": "test", "value": 42}

        result = my_fn()
        assert isinstance(result, ItemSchema)
        assert result.name == "test"

    def test_step_with_cache(self):
        layer = SemanticLayer()
        call_count = 0

        @layer.step(cache=True)
        def expensive_fn(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        expensive_fn(5)
        expensive_fn(5)  # Should not increment call_count after 3 successes
        assert call_count == 2  # Needs 3 successes to be "reliable"

        # Manually make it reliable
        layer.procedural.record_success(f"expensive_fn:('5',):{str(sorted({}.items()))}")
        layer.procedural.record_success(f"expensive_fn:('5',):{str(sorted({}.items()))}")

    def test_stats(self):
        layer = SemanticLayer()

        @layer.step()
        def fn():
            return 1

        fn()
        assert layer.stats["steps"]["fn"]["calls"] == 1


# --- Guards ---

class TestGuards:
    def test_repeat_guard(self):
        bus = EventBus()
        RepeatToolGuard(bus, threshold=2)
        warnings = []
        bus.on(EventType.GUARD_REPEAT_WARNING, lambda e: warnings.append(e))

        bus.emit(Event(EventType.TOOL_CALL, data={"name": "search"}, source="test"))
        assert len(warnings) == 0
        bus.emit(Event(EventType.TOOL_CALL, data={"name": "search"}, source="test"))
        assert len(warnings) == 1

    def test_budget_guard(self):
        bus = EventBus()
        StepBudgetGuard(bus, max_steps=2)
        exceeded = []
        bus.on(EventType.GUARD_BUDGET_EXCEEDED, lambda e: exceeded.append(e))

        bus.emit(Event(EventType.TURN_START, data="task", source="test"))
        bus.emit(Event(EventType.STEP_START, data=0, source="test"))
        assert len(exceeded) == 0
        bus.emit(Event(EventType.STEP_START, data=1, source="test"))
        assert len(exceeded) == 1
