"""Guard plugins — detect unproductive loops and enforce budgets."""
from __future__ import annotations

from semantic_harness.core.events import Event, EventBus, EventType


class RepeatToolGuard:
    """
    Detects when the same tool/action is called repeatedly.
    Injects a warning into the event bus (inspired by DSH's guard plugins).
    """

    def __init__(self, events: EventBus, threshold: int = 3):
        self.events = events
        self.threshold = threshold
        self._call_counts: dict[str, int] = {}
        self.events.on(EventType.TOOL_CALL, self._on_tool_call)

    def _on_tool_call(self, event: Event):
        tool_name = event.data.get("name", "") if isinstance(event.data, dict) else str(event.data)
        self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1

        if self._call_counts[tool_name] >= self.threshold:
            self.events.emit(Event(
                EventType.GUARD_REPEAT_WARNING,
                data={
                    "tool": tool_name,
                    "count": self._call_counts[tool_name],
                    "message": f"Warning: '{tool_name}' has been called {self._call_counts[tool_name]} times. Consider a different approach.",
                },
                source="repeat-guard",
            ))

    def reset(self):
        self._call_counts.clear()


class StepBudgetGuard:
    """Enforces a maximum number of steps per turn."""

    def __init__(self, events: EventBus, max_steps: int = 10):
        self.events = events
        self.max_steps = max_steps
        self._step_count = 0
        self.events.on(EventType.STEP_START, self._on_step)
        self.events.on(EventType.TURN_START, self._on_turn_start)

    def _on_turn_start(self, event: Event):
        self._step_count = 0

    def _on_step(self, event: Event):
        self._step_count += 1
        if self._step_count >= self.max_steps:
            self.events.emit(Event(
                EventType.GUARD_BUDGET_EXCEEDED,
                data={"steps": self._step_count, "max": self.max_steps},
                source="budget-guard",
            ))
