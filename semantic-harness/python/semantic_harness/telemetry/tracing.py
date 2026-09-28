"""
OpenTelemetry-compatible tracing infrastructure for Semantic Harness.

Provides hierarchical span tracking, context managers, and JSON/dict exports
for observability in production agentic pipelines.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import threading
import time
from typing import Any, Dict, Iterator, List, Optional
import uuid


class Span:
    """Represents a discrete execution span within an agentic pipeline."""

    def __init__(
        self,
        name: str,
        trace_id: str,
        span_id: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.name: str = name
        self.trace_id: str = trace_id
        self.span_id: str = span_id
        self.parent_id: Optional[str] = parent_id
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.status: str = "UNSET"
        self.attributes: Dict[str, Any] = attributes.copy() if attributes else {}
        self.events: List[Dict[str, Any]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        """Assign a span attribute key-value pair."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event timestamped to this span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })

    def finish(self, status: str = "OK") -> None:
        """Mark span complete with status OK or ERROR."""
        self.end_time = time.time()
        self.status = status

    @property
    def duration_seconds(self) -> float:
        """Span duration in seconds."""
        end = self.end_time or time.time()
        return max(0.0, end - self.start_time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


class SemanticTracer:
    """Thread-safe tracer for tracking spans and execution context."""

    def __init__(self, service_name: str = "semantic-harness") -> None:
        self.service_name: str = service_name
        self._lock = threading.RLock()
        self._spans: List[Span] = []
        self._local = threading.local()

    def _get_current_span(self) -> Optional[Span]:
        stack = getattr(self._local, "span_stack", None)
        return stack[-1] if stack else None

    def _push_span(self, span: Span) -> None:
        if not hasattr(self._local, "span_stack"):
            self._local.span_stack = []
        self._local.span_stack.append(span)

    def _pop_span(self) -> Optional[Span]:
        if hasattr(self._local, "span_stack") and self._local.span_stack:
            return self._local.span_stack.pop()
        return None

    def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span."""
        with self._lock:
            parent = self._get_current_span()
            trace_id = parent.trace_id if parent else uuid.uuid4().hex
            span_id = uuid.uuid4().hex[:16]
            parent_id = parent.span_id if parent else None

            merged_attrs = {"service.name": self.service_name}
            if attributes:
                merged_attrs.update(attributes)

            span = Span(
                name=name,
                trace_id=trace_id,
                span_id=span_id,
                parent_id=parent_id,
                attributes=merged_attrs,
            )
            self._spans.append(span)
            self._push_span(span)
            return span

    @contextmanager
    def span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Span]:
        """Context manager to scope a span execution."""
        active_span = self.start_span(name, attributes)
        try:
            yield active_span
            active_span.finish("OK")
        except Exception as exc:
            active_span.set_attribute("error.type", exc.__class__.__name__)
            active_span.set_attribute("error.message", str(exc))
            active_span.finish("ERROR")
            raise
        finally:
            self._pop_span()

    def get_spans(self) -> List[Span]:
        """Return a copy of all recorded spans."""
        with self._lock:
            return list(self._spans)

    def export_json(self) -> str:
        """Export all spans as JSON."""
        with self._lock:
            return json.dumps([s.to_dict() for s in self._spans], indent=2)

    def clear(self) -> None:
        """Clear all recorded spans."""
        with self._lock:
            self._spans.clear()


_GLOBAL_TRACER: Optional[SemanticTracer] = None
_GLOBAL_TRACER_LOCK = threading.Lock()


def get_tracer(service_name: str = "semantic-harness") -> SemanticTracer:
    """Obtain or initialize the global SemanticTracer singleton."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        with _GLOBAL_TRACER_LOCK:
            if _GLOBAL_TRACER is None:
                _GLOBAL_TRACER = SemanticTracer(service_name=service_name)
    return _GLOBAL_TRACER
