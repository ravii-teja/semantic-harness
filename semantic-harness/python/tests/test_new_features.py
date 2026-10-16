"""Unit tests for newly added features: PostgresGraphMemory and PreconditionFuzzer."""

import pytest
from semantic_harness.guard.fuzzer import PreconditionFuzzer
from semantic_harness.memory.graph_pg import PostgresGraphMemory


def test_postgres_graph_memory_fallback():
    pg_mem = PostgresGraphMemory(dsn="postgresql://invalid:invalid@localhost:5432/non_existent")
    assert not pg_mem.is_connected

    entity = pg_mem.add_entity(name="Invoice_101", entity_type="Invoice", properties={"total": 500.0})
    assert entity.name == "Invoice_101"

    triplet = pg_mem.add_triplet(source="Customer_A", predicate="PAYS", target="Invoice_101")
    assert triplet.source_name == "Customer_A"

    relations = pg_mem.get_relations_for("Invoice_101")
    assert len(relations) == 1
    assert relations[0].predicate == "pays"


def test_precondition_fuzzer_zero_frr():
    fuzzer = PreconditionFuzzer()
    result = fuzzer.run_stress_test(iterations=30)
    assert result.total_mutations == 30
    assert result.false_reuses == 0
    assert result.frr_percent == 0.0
    assert result.blocked_mismatches == 30
