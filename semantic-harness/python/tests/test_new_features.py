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


@pytest.mark.asyncio
async def test_postgres_graph_async_methods():
    pg_mem = PostgresGraphMemory(dsn="postgresql://invalid:invalid@localhost:5432/non_existent")
    # Async pool will fail to connect to invalid host, falling back cleanly
    success = await pg_mem.init_async_pool()
    assert not success

    entity = await pg_mem.aadd_entity("AsyncEntity", "TypeA")
    assert entity.name == "AsyncEntity"

    triplet = await pg_mem.aadd_triplet("AsyncEntity", "LINKS", "TargetEntity")
    assert triplet.predicate == "links"

    rels = await pg_mem.aget_relations_for("AsyncEntity")
    assert len(rels) >= 1
    await pg_mem.close_async_pool()


def test_sql_database_tool_query_and_kg_mapping():
    import sqlite3
    from semantic_harness.tools_sql import SQLDatabaseTool
    from semantic_harness.memory.graph import GraphMemory

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE orders (order_id TEXT, customer TEXT, amount REAL);")
    conn.execute("INSERT INTO orders VALUES ('ORD-1', 'AcmeCorp', 1250.0);")
    conn.execute("INSERT INTO orders VALUES ('ORD-2', 'BetaLLC', 850.0);")
    conn.commit()

    tool = SQLDatabaseTool(connection_or_dsn=conn, read_only=True)
    schema_md = tool.describe_schema()
    assert "orders" in schema_md
    assert "customer" in schema_md

    # Safe SELECT execution
    res = tool.execute_query("SELECT * FROM orders WHERE amount > 1000;")
    assert res.success
    assert res.row_count == 1
    assert res.rows[0]["customer"] == "AcmeCorp"

    # Security check: disallow destructive queries
    bad_res = tool.execute_query("DROP TABLE orders;")
    assert not bad_res.success
    assert "Security violation" in bad_res.error

    # Knowledge Graph mapping
    kg = GraphMemory(db_path=":memory:")
    mapped = tool.to_knowledge_graph(
        result=res,
        graph_memory=kg,
        source_column="customer",
        predicate="PLACED",
        target_column="order_id",
    )
    assert mapped == 1
    rels = kg.get_relations_for("AcmeCorp")
    assert len(rels) == 1
    assert rels[0].predicate == "placed"
    assert rels[0].target_name == "ORD-1"


@pytest.mark.asyncio
async def test_c2c_validate_with_retry_backoff():
    from pydantic import BaseModel
    from semantic_harness.semantics.c2c import C2CValidator

    class TargetSchema(BaseModel):
        score: int
        label: str

    validator = C2CValidator(max_retries=2)
    attempts = 0

    async def mock_generator(prompt: str):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return '{"score": "not_an_int", "label": "pending"}'
        return '{"score": 95, "label": "verified"}'

    result = await validator.validate_with_retry(
        initial_data='{"score": "bad", "label": "pending"}',
        schema=TargetSchema,
        generate_fn=mock_generator,
        base_delay_sec=0.01,
    )
    assert result.valid
    assert result.data.score == 95
    assert attempts == 2


@pytest.mark.asyncio
async def test_agent_orchestrator_delegation():
    from semantic_harness.core.agent import Agent, AgentConfig
    from semantic_harness.core.orchestrator import AgentOrchestrator
    from semantic_harness.memory.procedural import ProceduralMemory

    shared_mem = ProceduralMemory()
    orchestrator = AgentOrchestrator(shared_memory=shared_mem)

    class Researcher(Agent):
        """You are a research analyst."""
        async def arun(self, task: str):
            return {"task": task, "finding": "growth detected"}

    orchestrator.register_agent("analyst", Researcher(config=AgentConfig(model="mock")))
    res1 = await orchestrator.delegate("analyst", "evaluate revenue")
    assert res1["finding"] == "growth detected"

    # Second run should hit shared procedural memory directly
    cached = shared_mem.lookup("analyst:evaluate revenue", require_reliable=True)
    assert cached is not None
    assert cached.procedure["finding"] == "growth detected"


def test_dashboard_api_key_auth():
    from semantic_harness.visualization.dashboard import DashboardServer, DashboardHandler
    from unittest.mock import MagicMock

    server = DashboardServer(port=8080, api_key="secret-token-123")
    
    # 1. Without auth
    handler_unauth = DashboardHandler.__new__(DashboardHandler)
    handler_unauth.dashboard_server = server
    handler_unauth.headers = {}
    handler_unauth.path = "/api/data"
    assert not handler_unauth._is_authorized()

    # 2. With Bearer token
    handler_bearer = DashboardHandler.__new__(DashboardHandler)
    handler_bearer.dashboard_server = server
    handler_bearer.headers = {"Authorization": "Bearer secret-token-123"}
    handler_bearer.path = "/api/data"
    assert handler_bearer._is_authorized()

    # 3. With X-Semantic-Harness-Key
    handler_hdr = DashboardHandler.__new__(DashboardHandler)
    handler_hdr.dashboard_server = server
    handler_hdr.headers = {"X-Semantic-Harness-Key": "secret-token-123"}
    handler_hdr.path = "/api/data"
    assert handler_hdr._is_authorized()


def test_context_budget_tiktoken_or_fallback():
    from semantic_harness.semantics.budget import ContextBudget
    budget = ContextBudget(max_tokens=100, model_name="gpt-4o")
    tokens = budget.estimate_tokens("Hello world from Semantic Harness enterprise cognitive runtime!")
    assert tokens > 0

