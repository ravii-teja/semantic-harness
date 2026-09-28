"""Tests for FastAPI / Starlette middleware integration."""
import hashlib
import pytest
from pydantic import BaseModel

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from semantic_harness.integrations.fastapi import (
        SemanticHarnessMiddleware,
        procedural_route,
    )
    from semantic_harness.middleware import SemanticLayer
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    answer: str
    tokens: int


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_fastapi_middleware_cache_miss_then_hit():
    """Verify middleware passes through on miss and intercepts on hit with headers."""
    app = FastAPI()
    layer = SemanticLayer()

    intent_key = '/agent:{"query":"quarterly_report"}'
    computed_fp = hashlib.sha256("/agent".encode()).hexdigest()[:16]

    layer.procedural.compile(
        intent=intent_key,
        trajectory={"answer": "Q3 Revenue was $42M", "tokens": 0},
        schema_fingerprint=computed_fp,
        min_success_count=1,
    )
    layer.procedural.record_success(intent=intent_key)

    app.add_middleware(
        SemanticHarnessMiddleware,
        cache_paths=["/agent"],
        layer=layer,
        pricing_model="gpt-4o",
        min_success_count=1,
    )

    @app.post("/agent")
    async def agent_endpoint(req: QueryRequest):
        return {"answer": f"Computed for {req.query}", "tokens": 150}

    client = TestClient(app)

    # 1. Exact Hit on pre-compiled procedure
    resp_hit = client.post("/agent", json={"query": "quarterly_report"})
    assert resp_hit.status_code == 200
    assert resp_hit.headers.get("X-Semantic-Harness-Cache") == "HIT"
    assert "X-Semantic-Harness-Cost-Saved" in resp_hit.headers
    assert "X-Semantic-Harness-Latency-Saved-Ms" in resp_hit.headers
    data = resp_hit.json()
    assert data["answer"] == "Q3 Revenue was $42M"

    # 2. Miss on uncompiled query
    resp_miss = client.post("/agent", json={"query": "brand_new_question"})
    assert resp_miss.status_code == 200
    assert resp_miss.headers.get("X-Semantic-Harness-Cache") == "MISS"
    data_miss = resp_miss.json()
    assert data_miss["answer"] == "Computed for brand_new_question"


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_procedural_route_decorator():
    """Verify @procedural_route decorator wraps FastAPI routes."""
    app = FastAPI()

    class OutputSchema(BaseModel):
        status: str
        result: int

    calls = 0

    @app.post("/calculate")
    @procedural_route(validates=OutputSchema, cache=True)
    async def calculate(val: int):
        nonlocal calls
        calls += 1
        return {"status": "ok", "result": val * 2}

    client = TestClient(app)

    resp1 = client.post("/calculate?val=21")
    assert resp1.status_code == 200
    assert resp1.json() == {"status": "ok", "result": 42}
    assert calls == 1

    # Second call with same param hits the step cache
    resp2 = client.post("/calculate?val=21")
    assert resp2.status_code == 200
    assert resp2.json() == {"status": "ok", "result": 42}
    # Notice: calls remains 1 because procedural cache returned the result!
    assert calls == 1
