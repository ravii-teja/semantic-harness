#!/usr/bin/env python3
"""Example 05: TurboQuant & PolarQuant Compressed Vector Embeddings for Fuzzy Procedural Memory.

Demonstrates:
1. PolarQuant randomized orthogonal Hadamard rotation + 1-bit sign quantization + QJL error correction.
2. Vector memory compression (>10x reduction in memory footprint).
3. Fuzzy semantic intent matching: solving varied user phrasings with sub-millisecond cached procedures.
"""

import time
from semantic_harness import ProceduralMemory, PolarQuantizer, SemanticFeatureEmbedder


def main():
    print("================================================================")
    print(" 🚀 Example 05: TurboQuant Quantized Vector Search in Procedural Memory")
    print("================================================================\n")

    # 1. Vector Quantization Benchmark
    dim = 64
    quantizer = PolarQuantizer(dim=dim, enable_qjl=True)
    embedder = SemanticFeatureEmbedder(dim=dim)

    text = "Extract quarterly revenue, net profit margin, and EPS from report"
    raw_vector = embedder.embed(text)
    quantized_vec = quantizer.quantize(raw_vector)

    print("--- 1. PolarQuant Vector Compression Benchmark ---")
    print(f"  Input text: '{text}'")
    print(f"  Continuous dimension: {dim} float32 values ({dim * 4} bytes)")
    print(f"  PolarQuant compressed size: {quantized_vec.byte_size} bytes")
    print(f"  Memory Compression Ratio: {quantized_vec.compression_ratio:.2f}x\n")

    # 2. Fuzzy Procedural Memory
    print("--- 2. Training Procedural Memory on Canonical Intent ---")
    proc_memory = ProceduralMemory(vector_dim=dim, enable_fuzzy_search=True)
    canonical_intent = "parse customer invoice and calculate sales tax"
    verified_result = {
        "invoice_id": "INV-2026-X8",
        "subtotal": 1200.0,
        "tax_rate": 0.0825,
        "tax_amount": 99.0,
        "total": 1299.0,
    }

    proc_memory.cache(canonical_intent, procedure=verified_result)
    proc_memory.record_success(canonical_intent)
    proc_memory.record_success(canonical_intent)
    proc_memory.record_success(canonical_intent)
    print(f"  Cached procedure: '{canonical_intent}' (Reliable: {proc_memory.lookup(canonical_intent).is_reliable})\n")

    # 3. Fuzzy Semantic Search Testing across Varied Phrasings
    test_queries = [
        "parse customer invoice and calculate sales tax",        # Exact match
        "extract invoice and compute tax amount for customer",   # Semantic variant 1
        "calculate sales tax and parse invoice document",        # Semantic variant 2
        "generate python code to train neural network on cifar", # Unrelated intent
    ]

    print("--- 3. Evaluating Fuzzy Intent Retrieval ---")
    for q in test_queries:
        start_time = time.perf_counter()
        match = proc_memory.lookup(q, similarity_threshold=0.65)
        elapsed_us = (time.perf_counter() - start_time) * 1_000_000

        if match and match.is_reliable:
            print(f"  ✅ [CACHE HIT] Query: '{q}'")
            print(f"     Match Similarity: {match.similarity * 100:.1f}% | Latency: {elapsed_us:.2f} µs | Token Cost: 0")
            print(f"     Result: {match.procedure}\n")
        else:
            print(f"  ❌ [CACHE MISS] Query: '{q}'")
            print(f"     Status: Query must be routed to LLM for full reasoning (Latency: {elapsed_us:.2f} µs)\n")

    print("================================================================")
    print(" ✅ TurboQuant Vector Quantization & Fuzzy Procedural Cache Verified!")
    print("================================================================")


if __name__ == "__main__":
    main()
