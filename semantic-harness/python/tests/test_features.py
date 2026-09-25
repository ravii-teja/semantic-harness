"""Tests for Tokenomics Tracker, AmortizationEngine, DynamicCostRouter, and Knowledge Graph Memory."""
import pytest
from semantic_harness import (
    TokenomicsTracker,
    AmortizationEngine,
    DynamicCostRouter,
    ModelTier,
    ModelPricing,
    GraphMemory,
    Entity,
    Triplet,
    PythonREPL,
)


def test_tokenomics_tracker_cost_and_rates():
    tracker = TokenomicsTracker()
    tracker.set_pricing("test-cloud", prompt_per_million=2.0, completion_per_million=8.0)

    # Turn 1: Regular call
    tracker.record_turn(
        turn_id="turn_1",
        model_name="test-cloud",
        prompt_tokens=1000,
        completion_tokens=500,
        is_cache_hit=False,
    )
    # Expected cost: (1000/1M)*2.0 + (500/1M)*8.0 = 0.002 + 0.004 = 0.006

    # Turn 2: Cached procedural hit
    tracker.record_turn(
        turn_id="turn_2",
        model_name="test-cloud",
        prompt_tokens=0,
        completion_tokens=0,
        cached_tokens=1500,
        is_cache_hit=True,
    )

    summary = tracker.summary()
    assert summary["total_turns"] == 2
    assert summary["total_prompt_tokens"] == 1000
    assert summary["total_completion_tokens"] == 500
    assert summary["total_cached_tokens"] == 1500
    assert summary["cache_hit_rate"] == 0.5
    assert pytest.approx(summary["total_cost_usd"], rel=1e-3) == 0.006


def test_amortization_engine():
    # Compilation costs $0.05
    # Each frontier call costs $0.01
    # Each procedural hit costs $0.0001
    r_star = AmortizationEngine.break_even_threshold(
        compilation_cost_usd=0.05,
        frontier_turn_cost_usd=0.01,
        procedural_turn_cost_usd=0.0001,
    )
    assert 5.0 < r_star < 5.1

    roi = AmortizationEngine.calculate_roi(
        compilation_cost_usd=0.05,
        invocations=20,
        frontier_turn_cost_usd=0.01,
        procedural_turn_cost_usd=0.0,
    )
    assert roi["uncompiled_baseline_cost_usd"] == 0.20
    assert roi["actual_amortized_cost_usd"] == 0.05
    assert roi["net_savings_usd"] == 0.15
    assert roi["roi_pct"] == 300.0


def test_dynamic_cost_router():
    tracker = TokenomicsTracker()
    router = DynamicCostRouter(
        tracker,
        local_model="qwen2.5-coder:3b",
        frontier_model="gpt-4o",
        max_local_retries=2,
    )

    # 1. Procedural hit
    tier, model = router.decide_tier(has_procedural_cache=True)
    assert tier == ModelTier.CACHE
    assert model == "procedural_cache"

    # 2. Fresh local SLM turn
    tier, model = router.decide_tier(has_procedural_cache=False, current_retries=0)
    assert tier == ModelTier.LOCAL_SLM
    assert model == "qwen2.5-coder:3b"

    # 3. Retried past max_local_retries -> Escalates to frontier
    tier, model = router.decide_tier(has_procedural_cache=False, current_retries=2)
    assert tier == ModelTier.CLOUD_FRONTIER
    assert model == "gpt-4o"

    # 4. Critical complexity -> Routes to frontier directly
    tier, model = router.decide_tier(has_procedural_cache=False, current_retries=0, estimated_complexity=0.95)
    assert tier == ModelTier.CLOUD_FRONTIER
    assert model == "gpt-4o"


def test_knowledge_graph_memory():
    kg = GraphMemory(db_path=":memory:")

    # Add entities and relationships
    kg.add_triplet("Alice", "works_at", "AcmeCorp", confidence=0.99)
    kg.add_triplet("AcmeCorp", "acquired", "BetaLabs", confidence=0.95)
    kg.add_triplet("BetaLabs", "located_in", "San Francisco", confidence=0.90)

    # 1-hop for Alice
    rels_alice = kg.get_relations_for("Alice")
    assert len(rels_alice) == 1
    assert rels_alice[0].predicate == "works_at"
    assert rels_alice[0].target_name == "AcmeCorp"

    # Multi-hop traversal starting from Alice (2 hops)
    subgraph = kg.traverse_subgraph(["Alice"], max_hops=2)
    predicates = [t.predicate for t in subgraph]
    assert "works_at" in predicates
    assert "acquired" in predicates

    # Render context
    context = kg.render_subgraph_context(["Alice"], max_hops=2)
    assert "Alice" in context
    assert "AcmeCorp" in context
    assert "BetaLabs" in context

    # Text extraction
    extracted = kg.extract_triplets_from_text("(Bob) --[reports_to]--> (Alice)")
    assert len(extracted) == 1
    assert extracted[0].source_name == "Bob"
    assert extracted[0].predicate == "reports_to"
    assert extracted[0].target_name == "Alice"


def test_repl_bounded_previews():
    repl = PythonREPL(restrict_builtins=False)
    repl.execute("a = [i for i in range(100)]")
    repl.execute("b = {'key_' + str(i): i for i in range(50)}")
    repl.execute("c = 'x' * 500")

    previews = repl.get_bounded_previews()
    assert "a" in previews
    assert "list len=100" in previews["a"]
    assert "b" in previews
    assert "dict len=50" in previews["b"]
    assert "c" in previews
    assert "str len=500" in previews["c"]
