"""Event/session persistence — append-only JSONL event log.

Every emitted event is serialized to one JSON line, giving crash-safe
observability and replay: after a restart, `bus.load_history(path)` restores
the full event timeline for query/render.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from semantic_harness.core.events import Event, EventType


def _serialize_data(data: Any) -> Any:
    """Best-effort JSON-ification of arbitrary event payloads."""
    if data is None or isinstance(data, (str, int, float, bool)):
        return data
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


class JSONLSessionLog:
    """
    Append-only JSONL-backed event log. Attach to any EventBus:

        log = JSONLSessionLog("session.jsonl")
        log.attach(agent.events)   # every event is now persisted
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        parent = self.path.parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: Event) -> None:
        record = {
            "type": event.type.value if isinstance(event.type, EventType) else str(event.type),
            "data": _serialize_data(event.data),
            "timestamp": event.timestamp,
            "source": event.source,
            "metadata": _serialize_data(event.metadata),
        }
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def attach(self, bus) -> None:
        """Persist every future event emitted on this bus."""
        bus.on_any(self.append)

    def read_all(self) -> list[Event]:
        return read_session_log(self.path)


def read_session_log(path: str | Path) -> list[Event]:
    """Read a session log back into Event objects. Malformed lines are skipped."""
    events: list[Event] = []
    p = Path(path)
    if not p.exists():
        return events

    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            events.append(Event(
                type=EventType(record["type"]),
                data=record.get("data"),
                timestamp=record.get("timestamp", 0.0),
                source=record.get("source", ""),
                metadata=record.get("metadata", {}) or {},
            ))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue  # skip corrupt/unknown entries rather than failing replay
    return events
