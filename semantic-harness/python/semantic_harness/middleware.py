"""SemanticLayer — the drop-in middleware API for any agent/loop."""
from __future__ import annotations

import functools
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

    def __init__(self):
        self.validator = C2CValidator()
        self.procedural = ProceduralMemory()
        self._step_stats: dict[str, dict[str, int]] = {}

    def step(
        self,
        validates: type[BaseModel] | None = None,
        cache: bool = False,
        max_retries: int = 3,
        on_validation_error: Callable | None = None,
    ):
        """
        Decorator that wraps a function with semantic validation and procedural caching.

        Args:
            validates: Pydantic schema to validate the output against
            cache: If True, cache successful results for identical inputs
            max_retries: Number of validation retries before giving up
            on_validation_error: Custom handler for validation errors
        """
        def decorator(fn: Callable) -> Callable:
            fn_name = fn.__name__
            self._step_stats[fn_name] = {"calls": 0, "cache_hits": 0, "validations": 0, "failures": 0}

            @functools.wraps(fn)
            def wrapper(*args, **kwargs) -> Any:
                self._step_stats[fn_name]["calls"] += 1

                # Build a cache key from the function name + arguments
                cache_key = f"{fn_name}:{str(args)}:{str(sorted(kwargs.items()))}"

                # Check procedural cache
                if cache:
                    cached = self.procedural.lookup(cache_key)
                    if cached and cached.is_reliable:
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

                # Cache successful result
                if cache:
                    self.procedural.cache(cache_key, result)
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
):
    """Module-level convenience decorator using the default SemanticLayer."""
    return _default_layer.step(validates=validates, cache=cache, max_retries=max_retries)
