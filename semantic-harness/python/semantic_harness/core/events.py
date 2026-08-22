"""Event bus for the agent lifecycle — inspired by DSH's waterfall pattern."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Core event taxonomy."""
    # Turn lifecycle
    TURN_START = "turn/start"
    TURN_END = "turn/end"
    STEP_START = "step/start"
    STEP_END = "step/end"

    # LLM
    AGENT_REQUEST = "agent/request"
    AGENT_RESPONSE = "agent/response"
    STEP_ERROR = "step/error"

    # Tools
    TOOL_CALL = "tool/call"
    TOOL_RESULT = "tool/result"

    # Semantic layer
    SEMANTIC_VALIDATE_INPUT = "semantic/validate-input"
    SEMANTIC_VALIDATE_OUTPUT = "semantic/validate-output"
    SEMANTIC_COMPACTION = "semantic/compaction"

    # Memory
    MEMORY_RECALL = "memory/recall"
    MEMORY_PERSIST = "memory/persist"
    MEMORY_PROCEDURAL_HIT = "memory/procedural-hit"

    # Guard
    GUARD_REPEAT_WARNING = "guard/repeat-warning"
    GUARD_BUDGET_EXCEEDED = "guard/budget-exceeded"


@dataclass
class Event:
    """A single event in the agent lifecycle."""
    type: EventType
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Event({self.type.value}, source={self.source!r})"


class EventBus:
    """
    Pub/sub event bus with waterfall support.

    Waterfall events pass through each listener in order. Any listener can
    modify the event data or short-circuit by returning a value.
    """

    def __init__(self):
        self._listeners: dict[EventType, list[tuple[int, Callable]]] = {}
        self._any_listeners: list[Callable] = []
        self._history: list[Event] = []

    def on(self, event_type: EventType, listener: Callable, priority: int = 0):
        """Register a listener for an event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append((priority, listener))
        self._listeners[event_type].sort(key=lambda x: x[0])

    def on_any(self, listener: Callable):
        """Register a listener that receives EVERY emitted event (e.g. persistence)."""
        self._any_listeners.append(listener)

    def off(self, event_type: EventType, listener: Callable):
        """Remove a listener."""
        if event_type in self._listeners:
            self._listeners[event_type] = [
                (p, fn) for p, fn in self._listeners[event_type] if fn is not listener
            ]

    def emit(self, event: Event) -> Event:
        """Emit an event. Returns the (possibly modified) event after all listeners."""
        self._history.append(event)
        if event.type in self._listeners:
            for _, listener in self._listeners[event.type]:
                result = listener(event)
                if result is not None:
                    event.data = result
        for listener in self._any_listeners:
            result = listener(event)
            if result is not None:
                event.data = result
        return event

    def query(
        self,
        event_type: EventType | None = None,
        limit: int | None = None,
        source: str | None = None,
    ) -> list[Event]:
        """Query event history."""
        results = self._history
        if event_type:
            results = [e for e in results if e.type == event_type]
        if source:
            results = [e for e in results if e.source == source]
        if limit:
            results = results[-limit:]
        return results

    def render_history(self, limit: int = 50) -> str:
        """Render recent event history as a string for the LLM context."""
        recent = self._history[-limit:] if limit else self._history
        if not recent:
            return ""
        lines = ["## Event History"]
        for e in recent:
            lines.append(f'<event type="{e.type.value}" source="{e.source}">\n{e.data}\n</event>')
        return "\n".join(lines)

    def clear(self):
        """Clear event history."""
        self._history.clear()

    def load_history(self, path) -> int:
        """
        Load events persisted by JSONLSessionLog into this bus's history,
        enabling query/render after a restart. Returns the number loaded.
        """
        from semantic_harness.core.persistence import read_session_log
        self._history.extend(read_session_log(path))
        return len(self._history)
