"""
Prometheus metrics collector and exporter for Semantic Harness.

Provides thread-safe metrics accumulation and Prometheus exposition text format
for step latency, token consumption, cost, and procedural cache utilization.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict


class MetricsCollector:
    """Thread-safe Prometheus metrics collector for Semantic Harness agents."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._step_calls: Dict[tuple[str, str], int] = {}
        self._step_latencies: Dict[str, list[float]] = {}
        self._cache_hits: Dict[str, int] = {}
        self._tokens_prompt: Dict[str, int] = {}
        self._tokens_completion: Dict[str, int] = {}
        self._cost_usd: Dict[str, float] = {}
        self._cache_size: int = 0

    def record_step(self, step_name: str, duration_sec: float, status: str = "success") -> None:
        """Record execution of a step."""
        with self._lock:
            key = (step_name, status)
            self._step_calls[key] = self._step_calls.get(key, 0) + 1
            if step_name not in self._step_latencies:
                self._step_latencies[step_name] = []
            self._step_latencies[step_name].append(duration_sec)

    def record_cache_hit(self, step_name: str) -> None:
        """Record a procedural cache hit."""
        with self._lock:
            self._cache_hits[step_name] = self._cache_hits.get(step_name, 0) + 1

    def record_tokens(
        self, model: str, prompt_tokens: int, completion_tokens: int, cost_usd: float = 0.0
    ) -> None:
        """Record token consumption and calculated cost."""
        with self._lock:
            self._tokens_prompt[model] = self._tokens_prompt.get(model, 0) + prompt_tokens
            self._tokens_completion[model] = self._tokens_completion.get(model, 0) + completion_tokens
            self._cost_usd[model] = self._cost_usd.get(model, 0.0) + cost_usd

    def set_cache_size(self, size: int) -> None:
        """Update current procedural cache size gauge."""
        with self._lock:
            self._cache_size = size

    def export_prometheus(self) -> str:
        """Export metrics formatted for Prometheus scrapers (text/plain; version=0.0.4)."""
        lines: list[str] = []

        with self._lock:
            # Step executions
            lines.append("# HELP semantic_harness_step_calls_total Total number of step calls")
            lines.append("# TYPE semantic_harness_step_calls_total counter")
            for (step, status), count in sorted(self._step_calls.items()):
                lines.append(f'semantic_harness_step_calls_total{{step="{step}",status="{status}"}} {count}')

            # Cache hits
            lines.append("# HELP semantic_harness_cache_hits_total Total number of procedural cache hits")
            lines.append("# TYPE semantic_harness_cache_hits_total counter")
            for step, hits in sorted(self._cache_hits.items()):
                lines.append(f'semantic_harness_cache_hits_total{{step="{step}"}} {hits}')

            # Step durations
            lines.append("# HELP semantic_harness_step_duration_seconds Average duration per step in seconds")
            lines.append("# TYPE semantic_harness_step_duration_seconds gauge")
            for step, latencies in sorted(self._step_latencies.items()):
                avg = sum(latencies) / len(latencies) if latencies else 0.0
                lines.append(f'semantic_harness_step_duration_seconds{{step="{step}"}} {avg:.6f}')

            # Tokens
            lines.append("# HELP semantic_harness_tokens_total Cumulative tokens consumed by model and type")
            lines.append("# TYPE semantic_harness_tokens_total counter")
            for model, p_tokens in sorted(self._tokens_prompt.items()):
                lines.append(f'semantic_harness_tokens_total{{model="{model}",type="prompt"}} {p_tokens}')
            for model, c_tokens in sorted(self._tokens_completion.items()):
                lines.append(f'semantic_harness_tokens_total{{model="{model}",type="completion"}} {c_tokens}')

            # Cost
            lines.append("# HELP semantic_harness_cost_usd_total Estimated cumulative cost in USD")
            lines.append("# TYPE semantic_harness_cost_usd_total counter")
            for model, cost in sorted(self._cost_usd.items()):
                lines.append(f'semantic_harness_cost_usd_total{{model="{model}"}} {cost:.6f}')

            # Cache size
            lines.append("# HELP semantic_harness_procedural_cache_size Current number of compiled procedures")
            lines.append("# TYPE semantic_harness_procedural_cache_size gauge")
            lines.append(f"semantic_harness_procedural_cache_size {self._cache_size}")

        return "\n".join(lines) + "\n"

    def generate_prometheus_text(self) -> str:
        """Alias for export_prometheus() returning Prometheus format text."""
        return self.export_prometheus()

    def get_summary(self) -> Dict[str, Any]:
        """Obtain a structured metrics summary dictionary."""
        with self._lock:
            total_steps = sum(self._step_calls.values())
            total_hits = sum(self._cache_hits.values())
            all_latencies = [lat for lats in self._step_latencies.values() for lat in lats]
            avg_duration_ms = (sum(all_latencies) / len(all_latencies) * 1000.0) if all_latencies else 0.0

            denominator = (total_steps + total_hits)
            hit_rate_pct = (total_hits / denominator * 100.0) if denominator > 0 else 0.0

            prompt_tokens = sum(self._tokens_prompt.values())
            completion_tokens = sum(self._tokens_completion.values())
            cost_usd = sum(self._cost_usd.values())

            return {
                "step_calls_total": total_steps,
                "cache_hits_total": total_hits,
                "cache_hit_rate_pct": hit_rate_pct,
                "average_step_duration_ms": avg_duration_ms,
                "prompt_tokens_total": prompt_tokens,
                "completion_tokens_total": completion_tokens,
                "cost_usd_total": cost_usd,
                "procedural_cache_size": self._cache_size,
            }

    def reset(self) -> None:
        """Reset all metrics back to zero."""
        with self._lock:
            self._step_calls.clear()
            self._step_latencies.clear()
            self._cache_hits.clear()
            self._tokens_prompt.clear()
            self._tokens_completion.clear()
            self._cost_usd.clear()
            self._cache_size = 0


_GLOBAL_COLLECTOR: MetricsCollector | None = None
_GLOBAL_LOCK = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Obtain or initialize the global MetricsCollector singleton."""
    global _GLOBAL_COLLECTOR
    if _GLOBAL_COLLECTOR is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_COLLECTOR is None:
                _GLOBAL_COLLECTOR = MetricsCollector()
    return _GLOBAL_COLLECTOR
