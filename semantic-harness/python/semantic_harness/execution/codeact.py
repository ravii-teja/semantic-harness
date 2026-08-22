"""CodeAct strategy — the LLM writes Python, a sandboxed REPL executes it.

Research basis: NOOA's CodeAct loop. Small models are often better at
writing Python than emitting JSON tool schemas, so code-as-action is the
preferred execution strategy for sub-1B models.
"""
from __future__ import annotations

import re
from typing import Any

import litellm
from pydantic import BaseModel

from semantic_harness.core.events import Event, EventType
from semantic_harness.execution.repl import ExecutionResult, PythonREPL
from semantic_harness.semantics.c2c import C2CValidator, extract_json

_CODE_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)

FINAL_MARKER = "FINAL:"

CODEACT_SYSTEM_SUFFIX = """

## How to work (CodeAct protocol)
Write Python code inside ```python ... ``` fences to make progress.
- Use print(...) to inspect values; output is returned to you as observations.
- Variables persist between steps (shared REPL namespace).
- `agent` is bound to your agent object for accessing its state/methods.
When you know the final answer, reply with a line starting with "FINAL:" followed by the answer and no code block.
If you have nothing to execute, just answer directly.
"""


def extract_code(text: str) -> str | None:
    """Extract the first ```python fenced block from LLM output."""
    match = _CODE_FENCE_RE.search(text or "")
    return match.group(1).strip() if match else None


class CodeActStrategy:
    """Multi-step execution loop where actions are Python code blocks."""

    def __init__(self, agent, *, restrict_builtins: bool = True):
        self.agent = agent
        self.restrict_builtins = restrict_builtins
        self.validator = C2CValidator()

    def _make_repl(self) -> PythonREPL:
        return PythonREPL(
            locals={"agent": self.agent},
            restrict_builtins=self.restrict_builtins,
            default_timeout=getattr(self.agent.config, "repl_timeout", 10.0),
        )

    def run(self, task: str, *, output_schema: type[BaseModel] | None = None) -> Any:
        """Run a synchronous CodeAct turn."""
        events = self.agent.events
        config = self.agent.config

        events.emit(Event(EventType.TURN_START, data=task, source="codeact"))

        repl = self._make_repl()
        messages = self._initial_messages(task)
        result: Any = None
        had_error = False

        try:
            for step_num in range(config.max_steps):
                events.emit(Event(EventType.STEP_START, data=step_num, source="codeact"))
                events.emit(Event(
                    EventType.AGENT_REQUEST,
                    data={"model": config.model, "strategy": "codeact"},
                    source="codeact",
                ))

                try:
                    response = litellm.completion(
                        model=config.model,
                        messages=messages,
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                    )
                    text = response.choices[0].message.content or ""
                except Exception as e:
                    had_error = True
                    result = f"Error: {e}"
                    events.emit(Event(EventType.STEP_ERROR, data={"step": step_num, "error": str(e)}, source="codeact"))
                    break

                events.emit(Event(EventType.AGENT_RESPONSE, data=text, source="codeact"))

                # Final answer?
                if FINAL_MARKER in text or extract_code(text) is None:
                    candidate = (
                        text.split(FINAL_MARKER, 1)[1].strip()
                        if FINAL_MARKER in text else text.strip()
                    )
                    if output_schema is not None:
                        validated = self._validate(candidate, output_schema)
                        if not validated["valid"]:
                            self._append(messages, text, validated["retry"])
                            events.emit(Event(EventType.STEP_END, data=step_num, source="codeact"))
                            continue
                        result = validated["data"]
                    else:
                        result = candidate
                    events.emit(Event(EventType.STEP_END, data=step_num, source="codeact"))
                    break

                code = extract_code(text) or ""
                exec_result = repl.execute(code)
                observation = self._format_observation(exec_result)
                if not exec_result.success:
                    events.emit(Event(EventType.STEP_ERROR, data={"step": step_num, "error": exec_result.error}, source="repl"))

                self._append(messages, text, f"OBSERVATION:\n{observation}")
                events.emit(Event(EventType.STEP_END, data=step_num, source="codeact"))
        finally:
            events.emit(Event(EventType.TURN_END, data=result, source="codeact"))

        if result is None and not had_error and output_schema is not None:
            raise ValueError(f"No schema-valid output after {config.max_steps} CodeAct steps")
        return result

    async def arun(self, task: str, *, output_schema: type[BaseModel] | None = None) -> Any:
        """Run an async CodeAct turn."""
        events = self.agent.events
        config = self.agent.config

        events.emit(Event(EventType.TURN_START, data=task, source="codeact"))

        repl = self._make_repl()
        messages = self._initial_messages(task)
        result: Any = None

        try:
            for step_num in range(config.max_steps):
                events.emit(Event(EventType.STEP_START, data=step_num, source="codeact"))
                events.emit(Event(
                    EventType.AGENT_REQUEST,
                    data={"model": config.model, "strategy": "codeact"},
                    source="codeact",
                ))

                try:
                    response = await litellm.acompletion(
                        model=config.model,
                        messages=messages,
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                    )
                    text = response.choices[0].message.content or ""
                except Exception as e:
                    result = f"Error: {e}"
                    events.emit(Event(EventType.STEP_ERROR, data={"step": step_num, "error": str(e)}, source="codeact"))
                    break

                events.emit(Event(EventType.AGENT_RESPONSE, data=text, source="codeact"))

                if FINAL_MARKER in text or extract_code(text) is None:
                    candidate = (
                        text.split(FINAL_MARKER, 1)[1].strip()
                        if FINAL_MARKER in text else text.strip()
                    )
                    if output_schema is not None:
                        validated = self._validate(candidate, output_schema)
                        if not validated["valid"]:
                            self._append(messages, text, validated["retry"])
                            events.emit(Event(EventType.STEP_END, data=step_num, source="codeact"))
                            continue
                        result = validated["data"]
                    else:
                        result = candidate
                    events.emit(Event(EventType.STEP_END, data=step_num, source="codeact"))
                    break

                code = extract_code(text) or ""
                exec_result = repl.execute(code)
                observation = self._format_observation(exec_result)
                if not exec_result.success:
                    events.emit(Event(EventType.STEP_ERROR, data={"step": step_num, "error": exec_result.error}, source="repl"))

                self._append(messages, text, f"OBSERVATION:\n{observation}")
                events.emit(Event(EventType.STEP_END, data=step_num, source="codeact"))
        finally:
            events.emit(Event(EventType.TURN_END, data=result, source="codeact"))

        if result is None and output_schema is not None:
            raise ValueError(f"No schema-valid output after {config.max_steps} CodeAct steps")
        return result

    # --- helpers ---------------------------------------------------------

    def _initial_messages(self, task: str) -> list[dict]:
        system_content = self.agent.context.render() + CODEACT_SYSTEM_SUFFIX
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task},
        ]

    @staticmethod
    def _append(messages: list[dict], assistant_text: str, user_text: str):
        messages.append({"role": "assistant", "content": assistant_text})
        messages.append({"role": "user", "content": user_text})

    @staticmethod
    def _format_observation(result: ExecutionResult) -> str:
        parts = []
        if result.output:
            parts.append(result.output.rstrip())
        if result.value is not None:
            parts.append(f"-> {result.value!r}")
        if not result.success:
            parts.append(f"ERROR:\n{result.error}")
        return "\n".join(parts) if parts else "(no output)"

    def _validate(self, candidate: str, schema: type[BaseModel]) -> dict:
        """Validate a candidate final answer against output_schema."""
        try:
            parsed = extract_json(candidate)
        except ValueError as e:
            retry = f"Your final answer was not valid JSON ({e}). Respond with ONLY a JSON object."
            return {"valid": False, "retry": retry, "data": None}
        validation = self.validator.validate(parsed, schema)
        return {"valid": validation.valid, "retry": validation.retry_prompt, "data": validation.data}
