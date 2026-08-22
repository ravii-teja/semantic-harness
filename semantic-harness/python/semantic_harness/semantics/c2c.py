"""C2C Validator — Chaos2Clarity semantic validation between workflow steps.

Based on Chaos2Clarity (C2C) research: https://zenodo.org/records/19414309
"""
from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_JSON_BRACE_RE = re.compile(r"[\[{].*[\]}]", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from raw LLM text.

    Tolerates markdown code fences and surrounding prose. Raises ValueError
    when no parseable JSON object is found (lists are rejected — schemas
    are objects).
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected text to parse JSON from, got {type(text).__name__}")

    candidates: list[str] = []
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        candidates.append(fence.group(1))
    candidates.append(text.strip())
    brace = _JSON_BRACE_RE.search(text)
    if brace:
        candidates.append(brace.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict):
            return data

    raise ValueError("No JSON object found in model output")


class ValidationResult(BaseModel):
    """Result of a C2C validation."""
    valid: bool
    data: Any | None = None
    errors: list[str] = []
    retry_prompt: str = ""

# Alias for backwards compatibility
C2CValidationResult = ValidationResult


class C2CValidator:
    """
    Concept-to-Concept semantic validation layer.

    Sits between workflow steps and ensures that data flowing from one
    stage to the next strictly adheres to expected semantic schemas.

    When validation fails, it generates a precise, actionable error message
    that can be fed back to the LLM for self-correction. This is critical
    for small models that frequently produce malformed outputs.

    Design:
    - Uses Pydantic for type-safe validation
    - Generates LLM-friendly error messages (not Python tracebacks)
    - Supports retry budgets with progressive error accumulation
    - Tracks validation success rates for observability

    Usage:
        validator = C2CValidator()

        class ReportSchema(BaseModel):
            title: str
            findings: list[str]
            confidence: float

        result = validator.validate(raw_llm_output, ReportSchema)
        if not result.valid:
            # Feed result.retry_prompt back to the LLM
            ...
    """

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self._stats = {"validations": 0, "successes": 0, "failures": 0}

    def validate(self, data: dict[str, Any], schema: type[T]) -> ValidationResult:
        """
        Validate data against a Pydantic schema.
        Returns a ValidationResult with either the validated data or actionable errors.
        """
        self._stats["validations"] += 1
        try:
            validated = schema(**data)
            self._stats["successes"] += 1
            return ValidationResult(valid=True, data=validated)
        except ValidationError as e:
            self._stats["failures"] += 1
            errors = []
            for err in e.errors():
                loc = ".".join(str(part) for part in err["loc"])
                errors.append(f"Field '{loc}': {err['msg']} (type: {err['type']})")

            retry_prompt = self._build_retry_prompt(errors, schema)
            return ValidationResult(valid=False, errors=errors, retry_prompt=retry_prompt)

    def validate_or_raise(self, data: dict[str, Any], schema: type[T]) -> T:
        """Validate and return the model instance, or raise ValueError with LLM-friendly message."""
        result = self.validate(data, schema)
        if result.valid and isinstance(result.data, schema):
            return result.data
        raise ValueError(result.retry_prompt)

    def _build_retry_prompt(self, errors: list[str], schema: type[T]) -> str:
        """Build an LLM-friendly retry prompt from validation errors."""
        schema_hint = ""
        try:
            fields = schema.model_fields
            field_descs = []
            for name, field_info in fields.items():
                required = "required" if field_info.is_required() else "optional"
                field_descs.append(f"  - {name} ({field_info.annotation.__name__ if field_info.annotation else 'any'}): {required}")
            schema_hint = "\n".join(field_descs)
        except Exception:
            pass

        lines = [
            "Your output failed semantic validation. Please fix these errors:",
            "",
            *[f"  ✗ {e}" for e in errors],
        ]
        if schema_hint:
            lines.extend([
                "",
                f"Expected schema ({schema.__name__}):",
                schema_hint,
            ])
        lines.extend([
            "",
            "Please regenerate your output matching the schema exactly.",
        ])
        return "\n".join(lines)

    @property
    def success_rate(self) -> float:
        if self._stats["validations"] == 0:
            return 1.0
        return self._stats["successes"] / self._stats["validations"]

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)
