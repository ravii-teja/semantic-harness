"""
Example 03: Procedural Memory Cache Benchmark

Demonstrates how procedural caching eliminates LLM latency and token costs
for repeated semantic tasks.
"""

import time
from semantic_harness import ProceduralMemory

if __name__ == "__main__":
    proc = ProceduralMemory()
    task_intent = "extract_invoice_metadata"
    verified_procedure = {
        "invoice_no": "INV-2026-99",
        "total": 1250.00,
        "currency": "USD"
    }

    # Cache procedure and establish reliability
    proc.cache(task_intent, verified_procedure)
    for _ in range(3):
        proc.record_success(task_intent)

    print("--- Benchmark: Procedural Cache Retrieval ---")
    start = time.perf_counter()
    hit = proc.lookup(task_intent)
    duration_us = (time.perf_counter() - start) * 1_000_000

    if hit and hit.is_reliable:
        print(f"Procedural Cache Hit! (Confidence: {hit.confidence * 100:.0f}%)")
        print(f"Latency: {duration_us:.2f} µs (vs ~1,500,000 µs typical LLM turn)")
        print(f"Result: {hit.procedure}")
        print(f"Token savings: 100%")
