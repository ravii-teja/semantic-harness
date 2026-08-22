"""
Semantic Harness — Reproducible Benchmark Suite
Usage:
    cd benchmarks
    python run_benchmark.py --provider ollama --model qwen2.5:0.5b
    python run_benchmark.py --provider openai --model gpt-4o-mini
    python run_benchmark.py --benchmark all

Outputs results to benchmarks/results/YYYY-MM-DD_HH-MM.json
"""
from __future__ import annotations

import argparse
import json
import time
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

# Add python package directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from pydantic import BaseModel, field_validator
from semantic_harness.semantics.c2c import C2CValidator
from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.execution.repl import PythonREPL


# ─── Schemas for structured output tests ─────────────────────────────────────

class InvoiceSchema(BaseModel):
    invoice_number: str
    total: float
    currency: str
    line_items: list[str]


class SentimentSchema(BaseModel):
    sentiment: str
    confidence: float
    key_phrases: list[str]

    @field_validator("sentiment")
    @classmethod
    def validate_sentiment(cls, v: str) -> str:
        allowed = {"positive", "negative", "neutral"}
        if v.lower() not in allowed:
            raise ValueError(f"Must be one of {allowed}")
        return v.lower()

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be 0.0–1.0")
        return v


class UserProfileSchema(BaseModel):
    user_id: int
    username: str
    email: str


# ─── Benchmark result dataclass ───────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    name: str
    provider: str
    model: str
    total_runs: int
    pass_count: int
    fail_count: int
    pass_rate: float
    avg_latency_ms: float
    c2c_retries_needed: int
    notes: str = ""


# ─── C2C Schema Validation Benchmark ─────────────────────────────────────────

def benchmark_c2c_validation(provider_name: str, model_str: str, runs: int = 50) -> BenchmarkResult:
    """
    Tests Chaos2Clarity (C2C) validator against malformed LLM outputs.
    Simulates what SLMs produce: wrong types, missing fields, markdown fences.
    """
    from semantic_harness.providers.factory import get_provider

    validator = C2CValidator(schema=UserProfileSchema)
    provider = get_provider(model_str)

    pass_count = 0
    fail_count = 0
    total_retries = 0
    latencies = []

    # Representative malformed outputs SLMs commonly produce
    malformed_samples = [
        {"user_id": "not_an_int", "username": "alice"},               # wrong type + missing field
        {"user_id": 1, "username": "bob", "email": "not-an-email"},   # invalid email format
        '{"user_id": 2, "username": "carol", "email": "c@x.com"}',   # string instead of dict
        {"user_id": 3},                                                # 2 missing fields
        {"USER_ID": 4, "USERNAME": "dave", "EMAIL": "d@x.com"},       # wrong key casing
    ]

    for i in range(runs):
        sample = malformed_samples[i % len(malformed_samples)]
        start = time.perf_counter()

        # Initial validation
        result = validator.validate(sample)

        if result.is_valid:
            pass_count += 1
        else:
            # Build C2C retry prompt and send to LLM
            retry_prompt = validator.build_retry_prompt(result)
            messages = [
                {"role": "system", "content": "You are a JSON API. Return ONLY valid JSON, no markdown."},
                {"role": "user", "content": retry_prompt},
            ]
            try:
                llm_resp = provider.complete_sync(messages, model=model_str, max_tokens=256)
                retry_result = validator.validate(llm_resp.content)
                total_retries += 1
                if retry_result.is_valid:
                    pass_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1

        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)

    return BenchmarkResult(
        name="C2C Schema Validation (SLM self-correction)",
        provider=provider_name,
        model=model_str,
        total_runs=runs,
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=pass_count / runs,
        avg_latency_ms=sum(latencies) / len(latencies),
        c2c_retries_needed=total_retries,
    )


def benchmark_procedural_cache(runs: int = 10000) -> BenchmarkResult:
    """
    Benchmarks procedural memory cache hit latency vs. typical LLM latency.
    """
    proc = ProceduralMemory()

    intent = "extract_invoice_total"
    cached_result = {"invoice_number": "INV-2026-99", "total": 1250.0, "currency": "USD"}

    # Prime the cache (3 successful runs to reach confidence threshold)
    proc.cache(intent=intent, procedure=cached_result)
    for _ in range(3):
        proc.record_success(intent)

    # Measure cache hit latency
    latencies = []
    hits = 0

    for _ in range(runs):
        start = time.perf_counter()
        hit = proc.lookup(intent)
        elapsed = (time.perf_counter() - start) * 1_000_000  # microseconds
        latencies.append(elapsed)
        if hit and hit.is_reliable:
            hits += 1

    avg_us = sum(latencies) / len(latencies)
    simulated_llm_us = 1_500_000  # 1.5 seconds in microseconds
    speedup = simulated_llm_us / avg_us if avg_us > 0 else 0

    return BenchmarkResult(
        name="Procedural Memory Cache Hit Latency",
        provider="local",
        model="none",
        total_runs=runs,
        pass_count=hits,
        fail_count=runs - hits,
        pass_rate=hits / runs,
        avg_latency_ms=avg_us / 1000,
        c2c_retries_needed=0,
        notes=f"Avg cache latency: {avg_us:.2f}µs | Speedup vs LLM (1.5s): {speedup:,.0f}x | Token savings: 100%",
    )


def benchmark_repl_sandbox(runs: int = 100) -> BenchmarkResult:
    """Tests CodeAct REPL sandbox: correctness + security blocking."""
    repl = PythonREPL(timeout=5.0, sandbox=True)

    test_cases = [
        # (code, should_succeed, description)
        ("2 + 2", True, "arithmetic"),
        ("data = [1,2,3]; sum(data)", True, "list ops"),
        ("import os", False, "blocked import"),
        ("import json; json.dumps({'a': 1})", True, "allowed import"),
        ("open('/etc/passwd')", False, "blocked builtin"),
        ("x = 10\nx * x", True, "stateful variable"),
    ]

    pass_count = 0
    fail_count = 0
    latencies = []

    for code, should_succeed, _ in test_cases * (runs // len(test_cases)):
        start = time.perf_counter()
        result = repl.execute(code)
        elapsed = (time.perf_counter() - start) * 1000

        if result.success == should_succeed:
            pass_count += 1
        else:
            fail_count += 1
        latencies.append(elapsed)
        repl.reset()

    return BenchmarkResult(
        name="CodeAct REPL Sandbox (correctness + security)",
        provider="local",
        model="none",
        total_runs=pass_count + fail_count,
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=pass_count / (pass_count + fail_count),
        avg_latency_ms=sum(latencies) / len(latencies),
        c2c_retries_needed=0,
    )


# ─── Main runner ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Semantic Harness Benchmark Suite")
    parser.add_argument("--provider", default="local", choices=["local", "openai", "anthropic", "ollama"])
    parser.add_argument("--model", default="qwen2.5:0.5b")
    parser.add_argument("--benchmark", nargs="+", default=["all"], help="Benchmarks to run: all, c2c, cache, repl")
    parser.add_argument("--runs", type=int, default=50)
    args = parser.parse_args()

    selected = set(args.benchmark)
    run_all = "all" in selected

    results = []
    print(f"\n{'='*70}")
    print(f"  SEMANTIC HARNESS BENCHMARK — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*70}\n")

    if run_all or "cache" in selected:
        print("Running: Procedural Memory Cache...")
        r = benchmark_procedural_cache(runs=10000)
        results.append(r)
        print(f"  ✓ Pass rate: {r.pass_rate*100:.1f}% | Avg latency: {r.avg_latency_ms*1000:.2f}µs")
        print(f"    {r.notes}\n")

    if run_all or "repl" in selected:
        print("Running: CodeAct REPL Sandbox...")
        r = benchmark_repl_sandbox(runs=args.runs)
        results.append(r)
        print(f"  ✓ Pass rate: {r.pass_rate*100:.1f}% | Avg latency: {r.avg_latency_ms:.2f}ms\n")

    if (run_all or "c2c" in selected) and args.provider != "local":
        print(f"Running: C2C Validation (provider={args.provider}, model={args.model})...")
        r = benchmark_c2c_validation(args.provider, args.model, runs=args.runs)
        results.append(r)
        print(f"  ✓ Pass rate: {r.pass_rate*100:.1f}% | C2C retries: {r.c2c_retries_needed}/{args.runs}\n")
    elif run_all or "c2c" in selected:
        print("Skipping C2C benchmark (requires --provider openai/anthropic/ollama)\n")

    # Save results
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    with open(out_file, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print(f"Results saved to: {out_file}")
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
