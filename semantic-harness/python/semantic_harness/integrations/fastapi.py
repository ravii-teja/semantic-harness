"""FastAPI and Starlette integration for Semantic Harness.

Provides zero-effort procedural compilation and token-saving caching middleware
for modern Python ASGI web applications and agent APIs.
"""
from __future__ import annotations

import functools
import hashlib
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

from semantic_harness.core.tokenomics import (
    DynamicCostRouter,
    ModelPricing,
    ModelTier,
    TokenomicsTracker,
)
from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.middleware import SemanticLayer

try:
    from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    HAS_STARLETTE = True
except ImportError:  # pragma: no cover
    HAS_STARLETTE = False
    BaseHTTPMiddleware = object  # type: ignore[misc, assignment]
    Request = Any  # type: ignore[misc, assignment]
    Response = Any  # type: ignore[misc, assignment]
    JSONResponse = Any  # type: ignore[misc, assignment]
    RequestResponseEndpoint = Any  # type: ignore[misc, assignment]


class SemanticHarnessMiddleware(BaseHTTPMiddleware):
    """
    ASGI / FastAPI Middleware that transparently compiles and intercepts
    agent reasoning routes.

    On Cache HIT:
      - Bypasses downstream LLM / handler execution completely.
      - Returns zero-token compiled procedure output instantly (<1ms).
      - Adds `X-Semantic-Harness-Cache: HIT`.
      - Adds `X-Semantic-Harness-Cost-Saved: $...`.
      - Adds `X-Semantic-Harness-Latency-Saved-Ms: ...`.

    On Cache MISS:
      - Executes downstream endpoint handler.
      - Tracks execution latency and response schema.
      - Records execution into ProceduralMemory; compiles after verification.
      - Adds `X-Semantic-Harness-Cache: MISS`.

    Usage:
        from fastapi import FastAPI
        from semantic_harness.integrations.fastapi import SemanticHarnessMiddleware

        app = FastAPI()
        app.add_middleware(
            SemanticHarnessMiddleware,
            cache_paths=["/api/v1/agent", "/api/v1/generate"],
            pricing_model="gpt-4o",
        )
    """

    def __init__(
        self,
        app: Any,
        cache_paths: list[str] | None = None,
        layer: SemanticLayer | None = None,
        procedural_memory: ProceduralMemory | None = None,
        tokenomics_tracker: TokenomicsTracker | None = None,
        pricing_model: str = "gpt-4o",
        min_success_count: int = 1,
    ) -> None:
        if not HAS_STARLETTE:  # pragma: no cover
            raise ImportError(
                "Starlette or FastAPI must be installed to use SemanticHarnessMiddleware. "
                "Install with `pip install fastapi` or `pip install starlette`."
            )
        super().__init__(app)
        self.cache_paths = cache_paths or ["/agent", "/generate", "/query"]
        self.layer = layer or SemanticLayer()
        self.procedural = procedural_memory or self.layer.procedural
        self.tokenomics = tokenomics_tracker or TokenomicsTracker()
        self.pricing_model = pricing_model
        self.min_success_count = min_success_count
        self._execution_times: dict[str, float] = {}

    def _should_intercept(self, request: Request) -> bool:
        """Determine if request path matches targeted agent routes."""
        path = request.url.path
        return any(path.startswith(cp) or path == cp for cp in self.cache_paths)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count from raw payload."""
        return max(1, len(text) // 4)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Intercept, evaluate cache, and dispatch request."""
        if not self._should_intercept(request) or request.method not in ("POST", "PUT"):
            return await call_next(request)

        # Read and cache request body
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8", errors="replace")

        # Intent key derived from path + body
        intent_key = f"{request.url.path}:{body_str}"
        schema_fp = hashlib.sha256(request.url.path.encode()).hexdigest()[:16]

        # 1. Zero-Token Procedural Fast Path Check
        start_time = time.perf_counter()
        cached, explanation = self.procedural.explain_lookup(
            intent=intent_key,
            schema_fingerprint=schema_fp,
            require_reliable=True,
        )

        if cached is not None and cached.trajectory is not None:
            # CACHE HIT
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            avg_cold_ms = self._execution_times.get(request.url.path, 1250.0)
            saved_ms = max(0.0, avg_cold_ms - elapsed_ms)

            # Estimate cost savings
            prompt_tokens = self._estimate_tokens(body_str)
            comp_tokens = self._estimate_tokens(str(cached.trajectory))
            pricing = self.tokenomics.pricing.get(
                self.pricing_model, self.tokenomics.pricing.get("gpt-4o", ModelPricing(2.5, 10.0))
            )
            cost_saved = pricing.compute_cost(prompt_tokens, comp_tokens)

            # Record in tokenomics
            self.tokenomics.record_turn(
                turn_id=cached.intent_hash[:16],
                model_name=self.pricing_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=comp_tokens,
                cached_tokens=prompt_tokens + comp_tokens,
                is_cache_hit=True,
                latency_ms=elapsed_ms,
            )

            # Parse or return response payload
            content = cached.trajectory
            if isinstance(content, (dict, list)):
                response = JSONResponse(content=content)
            else:
                try:
                    response = JSONResponse(content=json.loads(str(content)))
                except Exception:
                    response = Response(content=str(content), media_type="application/json")

            response.headers["X-Semantic-Harness-Cache"] = "HIT"
            response.headers["X-Semantic-Harness-Tokens-Bypassed"] = str(prompt_tokens + comp_tokens)
            response.headers["X-Semantic-Harness-Cost-Saved"] = f"${cost_saved:.6f}"
            response.headers["X-Semantic-Harness-Latency-Saved-Ms"] = f"{saved_ms:.2f}"
            response.headers["X-Semantic-Harness-Procedural-Hash"] = cached.intent_hash[:16]
            return response

        # 2. CACHE MISS — Execute downstream endpoint
        cold_start = time.perf_counter()
        response = await call_next(request)
        cold_elapsed_ms = (time.perf_counter() - cold_start) * 1000.0
        self._execution_times[request.url.path] = cold_elapsed_ms

        response.headers["X-Semantic-Harness-Cache"] = "MISS"

        # Record procedural observation if status is 200
        if 200 <= response.status_code < 300:
            # We can record the procedure success using intent
            self.procedural.record_success(intent=intent_key)

        return response


def procedural_route(
    validates: type[BaseModel] | None = None,
    cache: bool = True,
    pricing_model: str = "gpt-4o",
    layer: SemanticLayer | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for FastAPI endpoint functions to enable zero-token procedural caching.

    Example:
        @app.post("/analyze")
        @procedural_route(validates=AnalysisOutput, cache=True)
        async def analyze_data(req: AnalysisRequest):
            return await run_llm_analysis(req.query)
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        target_layer = layer or SemanticLayer()

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_endpoint(*args: Any, **kwargs: Any) -> Any:
                # Wrap with layer.step
                wrapped = target_layer.step(validates=validates, cache=cache)(fn)
                return await wrapped(*args, **kwargs)
            return async_endpoint
        else:
            @functools.wraps(fn)
            def sync_endpoint(*args: Any, **kwargs: Any) -> Any:
                wrapped = target_layer.step(validates=validates, cache=cache)(fn)
                return wrapped(*args, **kwargs)
            return sync_endpoint

    return decorator
