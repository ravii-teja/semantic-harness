"""SemanticLayer — the drop-in middleware API for any agent/loop."""
from __future__ import annotations

import functools
import hashlib
import inspect
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from semantic_harness.memory.procedural import ProceduralMemory
from semantic_harness.semantics.c2c import C2CValidator


class SemanticLayer:
    """
    Drop-in semantic middleware for ANY agent framework.

    This is the primary public API for semantic-harness. You don't need to
    subclass Agent or restructure your code. Just wrap your functions.

    Usage:
        from semantic_harness import SemanticLayer
        from pydantic import BaseModel

        layer = SemanticLayer()

        class ReportSchema(BaseModel):
            title: str
            findings: list[str]

        @layer.step(validates=ReportSchema, cache=True)
        def my_research_step(topic: str) -> dict:
            return my_llm_call(topic)

        # Now my_research_step automatically:
        # 1. Validates output against ReportSchema
        # 2. Caches verified results for identical inputs
        # 3. Returns cached result on repeat calls (skipping LLM!)
    """

    def __init__(self) -> None:
        self.validator = C2CValidator()
        self.procedural = ProceduralMemory()
        self._step_stats: dict[str, dict[str, int]] = {}

    @staticmethod
    def _get_schema_fingerprint(schema: type[BaseModel] | None) -> str | None:
        """Compute deterministic hash of a Pydantic schema structure."""
        if not schema:
            return None
        try:
            fields = {
                name: str(f.annotation)
                for name, f in schema.model_fields.items()
            }
            dumped = json.dumps(fields, sort_keys=True)
            return hashlib.sha256(dumped.encode()).hexdigest()[:16]
        except Exception:
            return schema.__name__

    def step(
        self,
        validates: type[BaseModel] | None = None,
        cache: bool = False,
        max_retries: int = 3,
        on_validation_error: Callable[..., Any] | None = None,
        tool_signatures: dict[str, str] | None = None,
        env_keys: list[str] | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Decorator that wraps a function with semantic validation and procedural compilation.

        Args:
            validates: Pydantic schema to validate the output against
            cache: If True, compile and reuse successful executions
            max_retries: Number of validation retries before giving up
            on_validation_error: Custom handler for validation errors
            tool_signatures: Optional tool signature constraints
            env_keys: Optional required environment dependencies
        """
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            fn_name = fn.__name__
            self._step_stats[fn_name] = {"calls": 0, "cache_hits": 0, "validations": 0, "failures": 0}
            schema_fp = self._get_schema_fingerprint(validates)

            if inspect.iscoroutinefunction(fn):
                @functools.wraps(fn)
                async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    self._step_stats[fn_name]["calls"] += 1

                    # Build a cache key from the function name + arguments
                    cache_key = f"{fn_name}:{str(args)}:{str(sorted(kwargs.items()))}"

                    # Check procedural cache with explainable precondition enforcement
                    if cache:
                        cached, explanation = self.procedural.explain_lookup(
                            intent=cache_key,
                            schema_fingerprint=schema_fp,
                            tool_signatures=tool_signatures,
                            require_reliable=True,
                        )
                        if cached and explanation.is_reused:
                            self._step_stats[fn_name]["cache_hits"] += 1
                            return cached.procedure

                    # Execute the coroutine function
                    result = await fn(*args, **kwargs)

                    # Validate output if schema is provided
                    if validates and isinstance(result, dict):
                        self._step_stats[fn_name]["validations"] += 1
                        validation = self.validator.validate(result, validates)

                        if not validation.valid:
                            self._step_stats[fn_name]["failures"] += 1

                            if on_validation_error:
                                res = on_validation_error(result, validation)
                                if inspect.isawaitable(res):
                                    return await res
                                return res

                            # Retry logic: feed validation errors back
                            for _attempt in range(max_retries):
                                result = await fn(*args, **kwargs)
                                if isinstance(result, dict):
                                    validation = self.validator.validate(result, validates)
                                    if validation.valid:
                                        result = validation.data
                                        break
                            else:
                                raise ValueError(
                                    f"Validation failed after {max_retries} retries:\n"
                                    + "\n".join(validation.errors)
                                )
                        else:
                            result = validation.data

                    # Compile successful result into procedural memory
                    if cache:
                        self.procedural.compile(
                            intent=cache_key,
                            trajectory=result,
                            schema_fingerprint=schema_fp,
                            tool_signatures=tool_signatures,
                            env_keys=env_keys,
                            min_confidence=0.8,
                            min_success_count=1 if validates else 3,  # immediate reuse only when verified by schema
                        )
                        self.procedural.record_success(cache_key)

                    return result

                return async_wrapper

            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                self._step_stats[fn_name]["calls"] += 1

                # Build a cache key from the function name + arguments
                cache_key = f"{fn_name}:{str(args)}:{str(sorted(kwargs.items()))}"

                # Check procedural cache with explainable precondition enforcement
                if cache:
                    cached, explanation = self.procedural.explain_lookup(
                        intent=cache_key,
                        schema_fingerprint=schema_fp,
                        tool_signatures=tool_signatures,
                        require_reliable=True,
                    )
                    if cached and explanation.is_reused:
                        self._step_stats[fn_name]["cache_hits"] += 1
                        return cached.procedure

                # Execute the function
                result = fn(*args, **kwargs)

                # Validate output if schema is provided
                if validates and isinstance(result, dict):
                    self._step_stats[fn_name]["validations"] += 1
                    validation = self.validator.validate(result, validates)

                    if not validation.valid:
                        self._step_stats[fn_name]["failures"] += 1

                        if on_validation_error:
                            return on_validation_error(result, validation)

                        # Retry logic: feed validation errors back
                        for _attempt in range(max_retries):
                            result = fn(*args, **kwargs)
                            if isinstance(result, dict):
                                validation = self.validator.validate(result, validates)
                                if validation.valid:
                                    result = validation.data
                                    break
                        else:
                            raise ValueError(
                                f"Validation failed after {max_retries} retries:\n"
                                + "\n".join(validation.errors)
                            )
                    else:
                        result = validation.data

                # Compile successful result into procedural memory
                if cache:
                    self.procedural.compile(
                        intent=cache_key,
                        trajectory=result,
                        schema_fingerprint=schema_fp,
                        tool_signatures=tool_signatures,
                        env_keys=env_keys,
                        min_confidence=0.8,
                        min_success_count=1 if validates else 3,  # immediate reuse only when verified by schema
                    )
                    self.procedural.record_success(cache_key)

                return result

            return wrapper
        return decorator

    @property
    def stats(self) -> dict[str, Any]:
        """Get aggregate statistics."""
        return {
            "steps": dict(self._step_stats),
            "validator": self.validator.stats,
            "procedural_cache_size": self.procedural.size,
        }


# Convenience: module-level decorator
_default_layer = SemanticLayer()

def step(
    validates: type[BaseModel] | None = None,
    cache: bool = False,
    max_retries: int = 3,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Module-level convenience decorator using the default SemanticLayer."""
    return _default_layer.step(validates=validates, cache=cache, max_retries=max_retries)
