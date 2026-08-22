"""Agent loop — the core turn/step lifecycle."""
from __future__ import annotations

from typing import Any

import litellm
from pydantic import BaseModel

from semantic_harness.core.events import Event, EventType
from semantic_harness.semantics.budget import ContextBudget
from semantic_harness.semantics.c2c import C2CValidator, extract_json


class AgentLoop:
    """
    The core agent execution loop.

    Lifecycle (inspired by DSH):
        turn/start
            → memory/recall (spontaneous recall from long-term memory)
            → step/start (repeats up to max_steps)
                → agent/request (LLM call via litellm)
                → agent/response
                → semantic/validate-output (C2C validation, retries on failure)
                → tool/call + tool/result (when tools are dispatched)
            → step/end
        turn/end

    The loop iterates until:
      - a final answer is produced (plain text, or schema-valid output),
      - or the LLM call errors out,
      - or max_steps is exhausted.

    Pass output_schema=<PydanticModel> to force structured output: raw text
    is JSON-extracted and validated; invalid outputs get an actionable
    retry_prompt fed back for self-correction.
    """

    def __init__(self, agent):
        self.agent = agent
        self.budget = ContextBudget(max_tokens=agent.config.context_budget)
        self.validator = C2CValidator()

    def run(self, task: str, *, output_schema: type[BaseModel] | None = None, **kwargs) -> Any:
        """Run a synchronous turn."""
        self.agent.events.emit(Event(EventType.TURN_START, data=task, source="loop"))

        # Spontaneous recall from long-term memory
        self._before_turn_recall(task)

        # Check procedural cache
        if self.agent.config.procedural_cache:
            cached = self.agent.procedural.lookup(task)
            if cached and cached.is_reliable:
                self.agent.events.emit(Event(
                    EventType.MEMORY_PROCEDURAL_HIT,
                    data={"intent": task, "confidence": cached.confidence},
                    source="procedural",
                ))
                self.agent.events.emit(Event(EventType.TURN_END, data=cached.procedure, source="loop"))
                return cached.procedure

        # Seed the conversation with this turn's task so retries stack correctly
        self.agent.short_term.add(task, role="user")

        result: Any = None
        had_error = False

        for step_num in range(self.agent.config.max_steps):
            self.agent.events.emit(Event(EventType.STEP_START, data=step_num, source="loop"))

            messages = self._build_messages()

            # Budget check — trim if needed
            system_tokens = self.budget.estimate_tokens(messages[0]["content"]) if messages else 0
            messages = [messages[0]] + self.budget.trim_to_budget(messages[1:], system_tokens)

            # LLM call
            self.agent.events.emit(Event(EventType.AGENT_REQUEST, data={"model": self.agent.config.model}, source="loop"))

            try:
                response = litellm.completion(
                    model=self.agent.config.model,
                    messages=messages,
                    max_tokens=self.agent.config.max_tokens,
                    temperature=self.agent.config.temperature,
                    **self._tool_kwargs(),
                )
                message = response.choices[0].message
            except Exception as e:
                had_error = True
                result = f"Error: {e}"
                self.agent.events.emit(Event(
                    EventType.STEP_ERROR,
                    data={"step": step_num, "error": str(e)},
                    source="loop",
                ))
                if self.agent.config.procedural_cache:
                    self.agent.procedural.record_failure(task)
                break

            # Tool-call round: dispatch, record results, continue looping
            if getattr(message, "tool_calls", None):
                self._handle_tool_calls(message, step_num)
                self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                continue

            raw = message.content

            self.agent.events.emit(Event(EventType.AGENT_RESPONSE, data=raw, source="loop"))
            self.agent.short_term.add(raw, role="assistant")

            # Structured output path: parse → validate → retry with feedback
            if output_schema is not None:
                try:
                    parsed = extract_json(raw)
                except ValueError as e:
                    parsed = {}
                    self.agent.events.emit(Event(
                        EventType.SEMANTIC_VALIDATE_OUTPUT,
                        data={"step": step_num, "valid": False, "error": str(e)},
                        source="c2c",
                    ))
                    self.agent.short_term.add(
                        f"Your previous message was not valid JSON ({e}). "
                        f"Respond with ONLY a JSON object.",
                        role="user",
                    )
                    self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                    continue

                validation = self.validator.validate(parsed, output_schema)
                self.agent.events.emit(Event(
                    EventType.SEMANTIC_VALIDATE_OUTPUT,
                    data={"step": step_num, "valid": validation.valid, "errors": validation.errors},
                    source="c2c",
                ))

                if validation.valid:
                    result = validation.data
                    self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                    break

                # Feed the LLM-friendly retry prompt back for self-correction
                self.agent.short_term.add(validation.retry_prompt, role="user")
                self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                continue

            # Plain-text mode: first completion answers the task
            result = raw
            self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
            break

        if result is None and not had_error and output_schema is not None:
            raise ValueError(
                f"No schema-valid output after {self.agent.config.max_steps} steps"
            )

        # Cache the successful procedure — never cache error results (failure poisoning fix)
        if self.agent.config.procedural_cache and result is not None and not had_error:
            self.agent.procedural.cache(task, result)
            self.agent.procedural.record_success(task)

        # Persist to long-term memory
        if result is not None and not had_error:
            self.agent.events.emit(Event(EventType.MEMORY_PERSIST, data=result, source="loop"))

        self.agent.events.emit(Event(EventType.TURN_END, data=result, source="loop"))
        return result

    async def arun(self, task: str, *, output_schema: type[BaseModel] | None = None, **kwargs) -> Any:
        """Run an async turn using litellm's async API."""
        self.agent.events.emit(Event(EventType.TURN_START, data=task, source="loop"))

        # Spontaneous recall
        self._before_turn_recall(task)

        # Procedural cache check
        if self.agent.config.procedural_cache:
            cached = self.agent.procedural.lookup(task)
            if cached and cached.is_reliable:
                self.agent.events.emit(Event(EventType.MEMORY_PROCEDURAL_HIT, data={"intent": task}, source="procedural"))
                self.agent.events.emit(Event(EventType.TURN_END, data=cached.procedure, source="loop"))
                return cached.procedure

        # Seed the conversation with this turn's task so retries stack correctly
        self.agent.short_term.add(task, role="user")

        result: Any = None

        for step_num in range(self.agent.config.max_steps):
            self.agent.events.emit(Event(EventType.STEP_START, data=step_num, source="loop"))

            messages = self._build_messages()
            self.agent.events.emit(Event(EventType.AGENT_REQUEST, data={"model": self.agent.config.model}, source="loop"))

            try:
                response = await litellm.acompletion(
                    model=self.agent.config.model,
                    messages=messages,
                    max_tokens=self.agent.config.max_tokens,
                    temperature=self.agent.config.temperature,
                    **self._tool_kwargs(),
                )
                message = response.choices[0].message
            except Exception as e:
                result = f"Error: {e}"
                self.agent.events.emit(Event(
                    EventType.STEP_ERROR,
                    data={"step": step_num, "error": str(e)},
                    source="loop",
                ))
                if self.agent.config.procedural_cache:
                    self.agent.procedural.record_failure(task)
                break

            # Tool-call round: dispatch, record results, continue looping
            if getattr(message, "tool_calls", None):
                self._handle_tool_calls(message, step_num)
                self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                continue

            raw = message.content

            self.agent.events.emit(Event(EventType.AGENT_RESPONSE, data=raw, source="loop"))
            self.agent.short_term.add(raw, role="assistant")

            if output_schema is not None:
                try:
                    parsed = extract_json(raw)
                except ValueError as e:
                    parsed = {}
                    self.agent.events.emit(Event(
                        EventType.SEMANTIC_VALIDATE_OUTPUT,
                        data={"step": step_num, "valid": False, "error": str(e)},
                        source="c2c",
                    ))
                    self.agent.short_term.add(
                        f"Your previous message was not valid JSON ({e}). "
                        f"Respond with ONLY a JSON object.",
                        role="user",
                    )
                    self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                    continue

                validation = self.validator.validate(parsed, output_schema)
                self.agent.events.emit(Event(
                    EventType.SEMANTIC_VALIDATE_OUTPUT,
                    data={"step": step_num, "valid": validation.valid, "errors": validation.errors},
                    source="c2c",
                ))

                if validation.valid:
                    result = validation.data
                    self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                    break

                self.agent.short_term.add(validation.retry_prompt, role="user")
                self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
                continue

            result = raw
            self.agent.events.emit(Event(EventType.STEP_END, data=step_num, source="loop"))
            break

        if result is None and output_schema is not None:
            raise ValueError(
                f"No schema-valid output after {self.agent.config.max_steps} steps"
            )

        # Never cache error results (failure poisoning fix)
        if self.agent.config.procedural_cache and result is not None and not result.startswith("Error:"):
            self.agent.procedural.cache(task, result)
            self.agent.procedural.record_success(task)

        self.agent.events.emit(Event(EventType.TURN_END, data=result, source="loop"))
        return result

    def _tool_kwargs(self) -> dict[str, Any]:
        """Build the `tools` kwarg for litellm when tools are available."""
        if not getattr(self.agent.config, "enable_tools", True):
            return {}
        registry = getattr(self.agent, "tools", None)
        schemas = registry.schemas() if registry else []
        return {"tools": schemas} if schemas else {}

    def _handle_tool_calls(self, message: Any, step_num: int):
        """
        Dispatch every tool call in an assistant message, persisting the
        exchange to short-term memory so the next step sees the results.
        """
        tool_calls_payload = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in message.tool_calls
        ]

        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if message.content:
            assistant_msg["content"] = message.content
        assistant_msg["tool_calls"] = tool_calls_payload
        self.agent.short_term.add_message(assistant_msg)

        registry = getattr(self.agent, "tools", None)

        for tc, payload in zip(message.tool_calls, tool_calls_payload, strict=False):
            name = tc.function.name
            self.agent.events.emit(Event(
                EventType.TOOL_CALL,
                data={"name": name, "arguments": tc.function.arguments},
                source="loop",
            ))

            output = (
                registry.execute(name, tc.function.arguments)
                if registry else "Error: no tool registry on agent"
            )

            self.agent.events.emit(Event(
                EventType.TOOL_RESULT,
                data={"name": name, "output": output},
                source="loop",
            ))
            self.agent.short_term.add_message({
                "role": "tool",
                "tool_call_id": payload["id"],
                "content": output,
            })

    def _build_messages(self) -> list[dict[str, Any]]:
        """Build the message list for the LLM call from current conversation state."""
        # System prompt from context assembler
        event_history = self.agent.events.render_history(limit=20)
        system_content = self.agent.context.render(event_history=event_history)

        messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]

        # Short-term memory (conversation history incl. task + retry prompts)
        messages.extend(self.agent.short_term.get_messages())

        return messages

    def _before_turn_recall(self, task: str):
        """Spontaneous recall from long-term memory (NOOA BeforeTurn pattern)."""
        try:
            recalled = self.agent.long_term.search(task, k=3)
            if recalled:
                recall_text = "\n".join([f"- {m.content}" for m in recalled])
                self.agent.context.set_dynamic(
                    "recalled_facts",
                    lambda: f"Relevant facts from memory:\n{recall_text}",
                )
                self.agent.events.emit(Event(
                    EventType.MEMORY_RECALL,
                    data={"count": len(recalled), "query": task},
                    source="long_term",
                ))
        except Exception:
            pass  # Memory recall is best-effort
