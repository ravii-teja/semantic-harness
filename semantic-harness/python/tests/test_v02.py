"""Tests for v0.2.0 features: tools, structured output, CodeAct, persistence."""
import json
import types

import pytest
from pydantic import BaseModel

import semantic_harness.core.loop as loop_module
from semantic_harness import (
    Agent,
    AgentConfig,
    Event,
    EventBus,
    EventType,
    JSONLSessionLog,
    PythonREPL,
    ToolRegistry,
    extract_code,
    extract_json,
    function_to_schema,
    tool,
)
from semantic_harness.execution.codeact import CodeActStrategy

# --- helpers -------------------------------------------------------------

class ItemSchema(BaseModel):
    name: str
    value: int


def fake_response(content=None, tool_calls=None):
    msg = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


# --- extract_json --------------------------------------------------------

class TestExtractJson:
    def test_plain_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_in_code_fence(self):
        text = 'Here you go:\n```json\n{"name": "x", "value": 2}\n```\nDone!'
        assert extract_json(text) == {"name": "x", "value": 2}

    def test_json_embedded_in_prose(self):
        assert extract_json('The answer is {"ok": true} as requested.') == {"ok": True}

    def test_rejects_non_object(self):
        with pytest.raises(ValueError):
            extract_json("[1, 2, 3]")

    def test_raises_when_nothing_found(self):
        with pytest.raises(ValueError):
            extract_json("no structured data here")


# --- failure poisoning regression (Phase 1.1) ----------------------------

class TestNoFailurePoisoning:
    def test_llm_error_not_cached_as_success(self, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("api down")

        monkeypatch.setattr(loop_module.litellm, "completion", boom)
        agent = Agent(AgentConfig(ltm_db_path=":memory:", procedural_cache=True))
        result = agent.run("unique task xyz")

        assert "Error:" in result
        # The failed task must NOT be cached as a verified procedure
        assert agent.procedural.lookup("unique task xyz") is None
        # And a STEP_ERROR event must have been emitted
        errors = agent.events.query(EventType.STEP_ERROR)
        assert len(errors) == 1

    def test_error_records_failure(self, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("down")

        monkeypatch.setattr(loop_module.litellm, "completion", boom)
        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        agent.procedural.cache("task q", "old")
        agent.procedural.record_success("task q")

        agent.run("task q")

        cached = agent.procedural.lookup("task q")
        assert cached is not None and cached.failure_count == 1


# --- structured output + multi-step retry (Phase 2) ----------------------

class TestStructuredOutput:
    def test_valid_first_try(self, monkeypatch):
        responses = iter([
            fake_response('```json\n{"name": "widget", "value": 7}\n```'),
        ])
        monkeypatch.setattr(loop_module.litellm, "completion", lambda *a, **k: next(responses))

        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        result = agent.run("make item", output_schema=ItemSchema)

        assert isinstance(result, ItemSchema)
        assert result.name == "widget" and result.value == 7

    def test_retry_after_invalid_output(self, monkeypatch):
        responses = iter([
            fake_response('{"name": "widget"}'),                # missing value
            fake_response('{"name": "widget", "value": 3}'),   # corrected
        ])
        monkeypatch.setattr(loop_module.litellm, "completion", lambda *a, **k: next(responses))

        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        result = agent.run("make item", output_schema=ItemSchema)

        assert isinstance(result, ItemSchema)
        validations = agent.events.query(EventType.SEMANTIC_VALIDATE_OUTPUT)
        assert len(validations) == 2
        assert validations[0].data["valid"] is False
        assert validations[1].data["valid"] is True

    def test_exhausted_steps_raises(self, monkeypatch):
        monkeypatch.setattr(
            loop_module.litellm, "completion",
            lambda *a, **k: fake_response("garbage"),
        )
        agent = Agent(AgentConfig(ltm_db_path=":memory:", max_steps=2))
        with pytest.raises(ValueError, match="schema-valid"):
            agent.run("impossible", output_schema=ItemSchema)

    def test_task_seeded_once(self, monkeypatch):
        """The task must appear exactly once in conversation history."""
        captured = {}

        def capture_completion(model, messages, **kwargs):
            captured["messages"] = messages
            return fake_response('{"name": "n", "value": 1}')

        monkeypatch.setattr(loop_module.litellm, "completion", capture_completion)
        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        agent.run("the task", output_schema=ItemSchema)

        user_msgs = [m for m in captured["messages"] if m["role"] == "user"]
        assert [m["content"] for m in user_msgs] == ["the task"]


# --- tool calling (Phase 3) ----------------------------------------------

class MyToolAgent(Agent):
    """Tool test agent."""

    def lookup(self, q: str) -> str:
        """Look up a query."""
        return f"result:{q}"


class TestTools:
    def test_schema_generation_types(self):
        def fn(a: str, b: int = 5, c: float | None = None):
            """Do the thing."""
            return a

        schema = function_to_schema(fn)["function"]
        assert schema["name"] == "fn"
        assert schema["description"] == "Do the thing."
        params = schema["parameters"]
        assert params["required"] == ["a"]
        assert params["properties"]["b"]["default"] == 5
        assert params["properties"]["c"] == {"anyOf": [{"type": "number"}, {}]} or \
               params["properties"]["c"] == {"type": "number"}

    def test_registry_auto_registers_documented_methods(self):
        agent = MyToolAgent(AgentConfig(ltm_db_path=":memory:"))
        assert "lookup" in agent.tools.names()
        # run/arun must never be exposed to the LLM
        assert "run" not in agent.tools.names()
        assert "arun" not in agent.tools.names()

    def test_registry_execute_success_and_errors(self):
        reg = ToolRegistry()
        reg.register(lambda x: x * 2, name="double")  # type: ignore[assignment]
        assert json.loads(reg.execute("double", '{"x": 4}')) == 8
        assert reg.execute("missing", "{}").startswith("Error:")
        assert reg.execute("double", "not-json").startswith("Error:")

    def test_tool_decorator_marks_function(self):
        @tool(name="custom_name")
        def my_fn(x):
            """Docstring."""
            return x

        assert my_fn._is_tool is True
        assert my_fn._tool_name == "custom_name"

    def test_loop_dispatches_tool_calls(self, monkeypatch):
        call_count = {"n": 0}

        def scripted(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                tc = types.SimpleNamespace(
                    id="call_1",
                    function=types.SimpleNamespace(
                        name="lookup", arguments='{"q": "hello"}'
                    ),
                )
                return fake_response(tool_calls=[tc])
            return fake_response("final answer")

        monkeypatch.setattr(loop_module.litellm, "completion", scripted)
        agent = MyToolAgent(AgentConfig(ltm_db_path=":memory:"))
        result = agent.run("use the tool")

        assert result == "final answer"
        assert call_count["n"] == 2

        calls = agent.events.query(EventType.TOOL_CALL)
        results = agent.events.query(EventType.TOOL_RESULT)
        assert len(calls) == 1 and calls[0].data["name"] == "lookup"
        assert len(results) == 1 and results[0].data["output"] == "result:hello"

    def test_tools_passed_to_llm(self, monkeypatch):
        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)
            return fake_response("done")

        monkeypatch.setattr(loop_module.litellm, "completion", lambda model, messages, **kw: capture(**kw))
        agent = MyToolAgent(AgentConfig(ltm_db_path=":memory:"))
        agent.run("anything")

        tool_names = [t["function"]["name"] for t in captured.get("tools", [])]
        assert "lookup" in tool_names

    def test_enable_tools_false_omits_tools(self, monkeypatch):
        captured = {}

        def capture(**kwargs):
            captured.update(kwargs)
            return fake_response("done")

        monkeypatch.setattr(loop_module.litellm, "completion", lambda model, messages, **kw: capture(**kw))
        agent = MyToolAgent(AgentConfig(ltm_db_path=":memory:", enable_tools=False))
        agent.run("anything")
        assert "tools" not in captured


# --- REPL (Phase 4) ------------------------------------------------------

class TestPythonREPL:
    def test_state_persists_across_executions(self):
        repl = PythonREPL()
        assert repl.execute("x = 21 * 2").success
        assert repl.execute("x").value == 42

    def test_trailing_expression_captured(self):
        repl = PythonREPL(locals={"items": [1, 2, 3]})
        res = repl.execute("sum(items)")
        assert res.success and res.value == 6

    def test_print_captured(self):
        repl = PythonREPL()
        res = repl.execute("print('hello', 'world')")
        assert res.success and res.output == "hello world\n"

    def test_error_captured(self):
        repl = PythonREPL()
        res = repl.execute("1 / 0")
        assert not res.success
        assert "ZeroDivisionError" in res.error

    def test_timeout(self):
        repl = PythonREPL(default_timeout=0.3)
        res = repl.execute("while True: pass")
        assert not res.success
        assert "timed out" in res.error

    def test_open_blocked_by_default(self):
        repl = PythonREPL()
        res = repl.execute("open('somefile')")
        assert not res.success
        assert "NameError" in res.error

    def test_unrestricted_mode_allows_import_builtins(self):
        repl = PythonREPL(restrict_builtins=False)
        res = repl.execute("'abc' in dir(__builtins__) or True")
        assert res.success

    def test_locals_exposed(self):
        sentinel = object()
        repl = PythonREPL(locals={"thing": sentinel})
        assert repl.execute("thing").value is sentinel


class TestExtractCode:
    def test_python_fence(self):
        assert extract_code("text\n```python\ny = 1\n```\nmore") == "y = 1"

    def test_no_fence_returns_none(self):
        assert extract_code("just words") is None


class FakeCodeLLM:
    """Scripted litellm replacement driven by a response list."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, model, messages, **kwargs):
        self.calls.append(list(messages))
        return fake_response(self.responses.pop(0))


class TestCodeAct:
    def test_code_then_final(self, monkeypatch):
        llm = FakeCodeLLM([
            "Let me compute.\n```python\nprint(2 + 2)\n```",
            "FINAL: 4",
        ])
        monkeypatch.setattr(loop_module.litellm, "completion", llm)

        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        strategy = CodeActStrategy(agent)
        result = strategy.run("what is 2+2?")

        assert result == "4"
        assert len(llm.calls) == 2
        # Observation from step 1 was fed into step 2's prompt
        step2_user_msgs = [m for m in llm.calls[1] if m["role"] == "user"]
        assert any("OBSERVATION" in m["content"] and "4" in m["content"] for m in step2_user_msgs)

    def test_direct_answer_without_code(self, monkeypatch):
        llm = FakeCodeLLM(["42, obviously"])
        monkeypatch.setattr(loop_module.litellm, "completion", llm)

        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        assert CodeActStrategy(agent).run("answer me") == "42, obviously"

    def test_structured_final_with_schema(self, monkeypatch):
        llm = FakeCodeLLM(["FINAL: {\"name\": \"a\", \"value\": 9}"])
        monkeypatch.setattr(loop_module.litellm, "completion", llm)

        agent = Agent(AgentConfig(ltm_db_path=":memory:"))
        result = CodeActStrategy(agent).run("make item", output_schema=ItemSchema)
        assert isinstance(result, ItemSchema)

    def test_agent_dispatches_to_codeact(self, monkeypatch):
        llm = FakeCodeLLM(["FINAL: done"])
        monkeypatch.setattr(loop_module.litellm, "completion", llm)

        agent = Agent(AgentConfig(ltm_db_path=":memory:", execution_strategy="codeact"))
        assert agent.run("go") == "done"


# --- persistence (Phase 5) -----------------------------------------------

class TestJSONLSessionLog:
    def test_round_trip(self, tmp_path):
        bus = EventBus()
        log = JSONLSessionLog(tmp_path / "session.jsonl")
        log.attach(bus)

        bus.emit(Event(EventType.TURN_START, data="hello", source="loop"))
        bus.emit(Event(EventType.AGENT_RESPONSE, data={"key": "value"}, source="loop"))

        restored = log.read_all()
        assert len(restored) == 2
        assert restored[0].type == EventType.TURN_START
        assert restored[0].data == "hello"
        assert restored[0].source == "loop"
        assert restored[1].data == {"key": "value"}

    def test_non_serializable_data_stringified(self, tmp_path):
        bus = EventBus()
        log = JSONLSessionLog(tmp_path / "s.jsonl")
        log.attach(bus)
        weird = {1, 2}
        bus.emit(Event(EventType.STEP_END, data=weird))

        restored = log.read_all()
        assert restored[0].data == str(weird)

    def test_corrupt_lines_skipped(self, tmp_path):
        path = tmp_path / "corrupt.jsonl"
        good = json.dumps({
            "type": "turn/start", "data": None, "timestamp": 1.0,
            "source": "loop", "metadata": {},
        })
        path.write_text(f"{good}\nNOT JSON AT ALL\n{{'bad': 'json'}}\n")

        events = JSONLSessionLog(path).read_all()
        assert len(events) == 1
        assert events[0].type == EventType.TURN_START

    def test_load_history_into_new_bus(self, tmp_path):
        bus = EventBus()
        log = JSONLSessionLog(tmp_path / "s.jsonl")
        log.attach(bus)
        bus.emit(Event(EventType.MEMORY_PERSIST, data="fact", source="loop"))

        fresh = EventBus()
        count = fresh.load_history(log.path)
        assert count == 1
        assert fresh.query(EventType.MEMORY_PERSIST)[0].data == "fact"

    def test_on_any_receives_every_event(self):
        seen = []
        bus = EventBus()
        bus.on_any(seen.append)
        bus.emit(Event(EventType.TURN_START, data="a"))
        bus.emit(Event(EventType.TURN_END, data="b"))
        assert len(seen) == 2


# --- config additions ----------------------------------------------------

class TestConfigAdditions:
    def test_defaults(self):
        config = AgentConfig()
        assert config.execution_strategy == "tools"
        assert config.enable_tools is True
        assert config.repl_timeout == 10.0

    def test_ltm_db_path_configurable(self):
        config = AgentConfig(ltm_db_path="/tmp/test_mem.db")
        assert config.ltm_db_path == "/tmp/test_mem.db"
