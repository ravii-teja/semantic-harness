"""Tokenomics & Cost Amortization Engine for Semantic Harness.

Provides real-time token tracking, dollar cost calculations, amortization
curve analysis (r*), and dynamic model routing (SLM vs. Cloud Frontier).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ModelTier(str, Enum):
    CACHE = "cache"
    LOCAL_SLM = "local_slm"
    CLOUD_FRONTIER = "cloud_frontier"


@dataclass
class ModelPricing:
    """Pricing profile per million tokens (USD)."""
    prompt_per_million: float = 0.0
    completion_per_million: float = 0.0

    def compute_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            (prompt_tokens / 1_000_000.0) * self.prompt_per_million
            + (completion_tokens / 1_000_000.0) * self.completion_per_million
        )


DEFAULT_PRICING: dict[str, ModelPricing] = {
    # Free local models (Ollama, MLX, vLLM local)
    "local_slm": ModelPricing(0.0, 0.0),
    "ollama": ModelPricing(0.0, 0.0),
    "mlx": ModelPricing(0.0, 0.0),
    "qwen2.5:0.5b": ModelPricing(0.0, 0.0),
    "qwen2.5-coder:3b": ModelPricing(0.0, 0.0),
    "llama3.2:1b": ModelPricing(0.0, 0.0),
    "llama3.2:3b": ModelPricing(0.0, 0.0),
    # Commercial Frontier Models
    "gpt-4o": ModelPricing(2.50, 10.00),
    "gpt-4o-mini": ModelPricing(0.15, 0.60),
    "claude-3-5-sonnet": ModelPricing(3.00, 15.00),
    "claude-3-5-haiku": ModelPricing(0.80, 4.00),
    "deepseek-v3": ModelPricing(0.14, 0.28),
}


@dataclass
class TokenUsageRecord:
    """Telemetry record for a single execution step or turn."""
    turn_id: str
    model_name: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    retry_tokens: int = 0
    is_cache_hit: bool = False
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class TokenomicsTracker:
    """Collects per-turn token usage, computes costs, and generates telemetry summaries."""

    def __init__(self, pricing_profiles: dict[str, ModelPricing] | None = None):
        self.pricing = dict(DEFAULT_PRICING)
        if pricing_profiles:
            self.pricing.update(pricing_profiles)
        self.records: list[TokenUsageRecord] = []

    def set_pricing(self, model_name: str, prompt_per_million: float, completion_per_million: float):
        self.pricing[model_name] = ModelPricing(prompt_per_million, completion_per_million)

    def record_turn(
        self,
        turn_id: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cached_tokens: int = 0,
        retry_tokens: int = 0,
        is_cache_hit: bool = False,
        latency_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> TokenUsageRecord:
        pricing = self.pricing.get(model_name, ModelPricing(0.0, 0.0))
        cost = 0.0
        if not is_cache_hit:
            cost = pricing.compute_cost(prompt_tokens + retry_tokens, completion_tokens)

        rec = TokenUsageRecord(
            turn_id=turn_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=cached_tokens,
            retry_tokens=retry_tokens,
            is_cache_hit=is_cache_hit,
            cost_usd=cost,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        self.records.append(rec)
        return rec

    def record(self, *args: Any, **kwargs: Any) -> TokenUsageRecord:
        """Ergonomic alias for record_turn."""
        return self.record_turn(*args, **kwargs)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(r.prompt_tokens for r in self.records)

    @property
    def total_completion_tokens(self) -> int:
        return sum(r.completion_tokens for r in self.records)

    @property
    def total_tokens(self) -> int:
        """Total tokens across prompt, completion, and retry."""
        return sum(r.prompt_tokens + r.completion_tokens + r.retry_tokens for r in self.records)

    @property
    def total_cached_tokens(self) -> int:
        return sum(r.cached_tokens for r in self.records)

    @property
    def total_retry_tokens(self) -> int:
        return sum(r.retry_tokens for r in self.records)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def cache_hit_rate(self) -> float:
        if not self.records:
            return 0.0
        hits = sum(1 for r in self.records if r.is_cache_hit)
        return hits / len(self.records)

    def summary(self) -> dict[str, Any]:
        return {
            "total_turns": len(self.records),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "total_retry_tokens": self.total_retry_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
        }


class AmortizationEngine:
    """Calculates break-even thresholds and economic ROI of procedural memory compilation."""

    @staticmethod
    def break_even_threshold(
        compilation_cost_usd: float,
        frontier_turn_cost_usd: float,
        procedural_turn_cost_usd: float = 0.0,
    ) -> float:
        """Calculate the break-even reuse count r*.

        r* = compilation_cost / (frontier_cost - procedural_cost)
        """
        net_savings_per_turn = frontier_turn_cost_usd - procedural_turn_cost_usd
        if net_savings_per_turn <= 0:
            return float("inf")
        return compilation_cost_usd / net_savings_per_turn

    @staticmethod
    def calculate_roi(
        compilation_cost_usd: float,
        invocations: int,
        frontier_turn_cost_usd: float,
        procedural_turn_cost_usd: float = 0.0,
    ) -> dict[str, float]:
        """Compute net economic savings and ROI percentage over N invocations."""
        uncompiled_baseline_cost = invocations * frontier_turn_cost_usd
        actual_amortized_cost = compilation_cost_usd + (invocations * procedural_turn_cost_usd)
        net_savings_usd = uncompiled_baseline_cost - actual_amortized_cost
        roi_pct = (net_savings_usd / max(1e-6, compilation_cost_usd)) * 100.0 if compilation_cost_usd > 0 else 0.0

        return {
            "invocations": float(invocations),
            "uncompiled_baseline_cost_usd": round(uncompiled_baseline_cost, 6),
            "actual_amortized_cost_usd": round(actual_amortized_cost, 6),
            "net_savings_usd": round(net_savings_usd, 6),
            "roi_pct": round(roi_pct, 2),
        }


class DynamicCostRouter:
    """Routes execution between procedural cache, local SLM, and frontier fallback based on budget."""

    def __init__(
        self,
        tracker: TokenomicsTracker,
        local_model: str | None = None,
        frontier_model: str = "gpt-4o-mini",
        max_local_retries: int = 2,
    ):
        self.tracker = tracker
        if local_model is None:
            from semantic_harness.core.hardware import get_default_local_model
            self.local_model = get_default_local_model()
        else:
            self.local_model = local_model
        self.frontier_model = frontier_model
        self.max_local_retries = max_local_retries

    def decide_tier(
        self,
        has_procedural_cache: bool,
        current_retries: int = 0,
        estimated_complexity: float = 0.5,
    ) -> tuple[ModelTier, str]:
        """Decide the execution tier: CACHE, LOCAL_SLM, or CLOUD_FRONTIER."""
        if has_procedural_cache:
            return ModelTier.CACHE, "procedural_cache"

        # If retried too many times on local SLM, escalate to frontier model
        if current_retries >= self.max_local_retries:
            return ModelTier.CLOUD_FRONTIER, self.frontier_model

        # Highly complex tasks with high complexity score can directly route to frontier if configured
        if estimated_complexity > 0.90:
            return ModelTier.CLOUD_FRONTIER, self.frontier_model

        return ModelTier.LOCAL_SLM, self.local_model
