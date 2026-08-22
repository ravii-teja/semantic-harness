"""Tests for TurboQuant / PolarQuant extreme vector quantization and fuzzy procedural search."""
import time

from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.memory.turbo_quant import (
    PolarQuantizer,
    SemanticFeatureEmbedder,
    TurboQuantVectorIndex,
)


class TestPolarQuantizer:
    def test_compression_ratio(self):
        dim = 128
        quantizer = PolarQuantizer(dim=dim, enable_qjl=True)
        vec = [float(i % 7) for i in range(dim)]
        q = quantizer.quantize(vec)

        # 128 float32 is 512 bytes. Quantized packed bits is ~16 bytes + 16 bytes QJL
        assert q.dim == 128
        assert q.compression_ratio >= 10.0
        assert q.byte_size <= 64

    def test_cosine_similarity_preservation(self):
        quantizer = PolarQuantizer(dim=64, enable_qjl=True)

        v1 = [1.0 if i < 32 else 0.0 for i in range(64)]
        v2 = [1.0 if i < 32 else 0.0 for i in range(64)]  # Identical
        v3 = [0.0 if i < 32 else 1.0 for i in range(64)]  # Orthogonal
        v4 = [-1.0 if i < 32 else 0.0 for i in range(64)] # Opposite

        q1 = quantizer.quantize(v1)
        q2 = quantizer.quantize(v2)
        q3 = quantizer.quantize(v3)
        q4 = quantizer.quantize(v4)

        sim_identical = PolarQuantizer.similarity(q1, q2)
        sim_orthogonal = PolarQuantizer.similarity(q1, q3)
        sim_opposite = PolarQuantizer.similarity(q1, q4)

        assert sim_identical >= 0.95
        assert abs(sim_orthogonal) <= 0.35
        assert sim_opposite <= -0.70

    def test_dequantization_shape(self):
        quantizer = PolarQuantizer(dim=64)
        vec = [float(i) for i in range(64)]
        q = quantizer.quantize(vec)
        recon = quantizer.dequantize(q)

        assert len(recon) == 64
        # Norms should be in same ballpark
        recon_norm = sum(x * x for x in recon) ** 0.5
        assert abs(recon_norm - q.norm) < 0.2 * q.norm


class TestSemanticFeatureEmbedder:
    def test_text_similarity(self):
        embedder = SemanticFeatureEmbedder(dim=64)
        quantizer = PolarQuantizer(dim=64)

        e1 = embedder.embed("parse customer invoice total")
        e2 = embedder.embed("extract invoice customer and total amount")
        e3 = embedder.embed("generate synthetic protein folding dataset")

        q1 = quantizer.quantize(e1)
        q2 = quantizer.quantize(e2)
        q3 = quantizer.quantize(e3)

        sim_related = PolarQuantizer.similarity(q1, q2)
        sim_unrelated = PolarQuantizer.similarity(q1, q3)

        assert sim_related > sim_unrelated
        assert sim_related > 0.50


class TestTurboQuantVectorIndex:
    def test_add_and_search(self):
        index = TurboQuantVectorIndex(dim=64)

        index.add("inv", "extract invoice total and tax", procedure={"action": "invoice_parser"})
        index.add("email", "classify customer support email sentiment", procedure={"action": "sentiment_clf"})
        index.add("sql", "generate postgres sql query from schema", procedure={"action": "sql_coder"})

        assert len(index) == 3

        # Search with slight variant phrasing
        results = index.search("parse invoice total amount", top_k=2, min_similarity=0.4)
        assert len(results) >= 1
        assert results[0].key == "inv"
        assert results[0].procedure["action"] == "invoice_parser"

    def test_sub_millisecond_search_latency(self):
        index = TurboQuantVectorIndex(dim=64)
        for i in range(50):
            index.add(f"intent_{i}", f"operation {i} for data processing workflow", procedure={"id": i})

        start = time.perf_counter()
        results = index.search("operation 25 data processing", top_k=3)
        duration_us = (time.perf_counter() - start) * 1_000_000

        assert len(results) > 0
        # Should be sub-millisecond (< 1000 µs)
        assert duration_us < 2000.0


class TestProceduralMemoryTurboQuant:
    def test_exact_and_fuzzy_lookup(self):
        proc = ProceduralMemory(vector_dim=64, enable_fuzzy_search=True)

        proc.cache("extract invoice number and balance", procedure={"handler": "invoice_v1"})
        proc.record_success("extract invoice number and balance")
        proc.record_success("extract invoice number and balance")
        proc.record_success("extract invoice number and balance")

        # 1. Exact match
        exact_hit = proc.lookup("extract invoice number and balance")
        assert exact_hit is not None
        assert exact_hit.similarity == 1.0
        assert exact_hit.is_reliable

        # 2. Fuzzy match with semantic variant phrasing
        fuzzy_hit = proc.lookup("get invoice number and balance due", similarity_threshold=0.60)
        assert fuzzy_hit is not None
        assert fuzzy_hit.procedure["handler"] == "invoice_v1"
        assert fuzzy_hit.similarity >= 0.60

    def test_fuzzy_invalidation_on_failures(self):
        proc = ProceduralMemory(vector_dim=64, enable_fuzzy_search=True)
        intent = "format markdown table to json"

        proc.cache(intent, procedure={"handler": "bad_parser"})
        # 3 failures drop confidence to 0
        proc.record_failure(intent)
        proc.record_failure(intent)
        proc.record_failure(intent)

        # Should be auto-invalidated from both hash map and vector index
        assert proc.lookup(intent) is None
        assert proc.lookup("format markdown to json", similarity_threshold=0.5) is None
