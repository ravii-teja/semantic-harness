"""Permission enforcement decorators and PermissionDeniedError.

Usage
-----
On tool classes or async functions::

    from semantic_harness.security.decorators import require_permission

    class SQLDatabaseTool:
        @require_permission("tool:execute:sql")
        async def __call__(self, query: str, ctx: SecurityContext) -> SQLResult:
            ...

    @require_permission("admin:migrations")
    async def run_migrations(ctx: SecurityContext) -> None:
        ...

The decorator inspects the *first* argument whose name is ``ctx`` or whose
type annotation is ``SecurityContext``, falling back to looking at all kwargs.
If no SecurityContext is found the call is permitted (fail-open on missing ctx
so non-guarded code paths keep working) but a warning is emitted.
"""
from __future__ import annotations

import functools
import inspect
import logging
import warnings
from collections.abc import Callable
from typing import Any, TypeVar

from semantic_harness.security.context import Permission, SecurityContext

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class PermissionDeniedError(PermissionError):
    """Raised when a SecurityContext lacks a required permission.

    Intentionally does NOT expose whether the principal is unauthenticated vs
    unauthorised -- callers (API layer) decide what HTTP status to surface.
    """

    def __init__(self, required: Permission, context: SecurityContext | None = None) -> None:
        self.required = required
        self.context = context
        principal = context.principal_id if context else "unknown"
        super().__init__(
            f"Principal '{principal}' does not hold permission '{required.value}'."
        )


def _extract_security_context(*args: Any, **kwargs: Any) -> SecurityContext | None:
    """Find the SecurityContext in positional or keyword arguments."""
    # Check kwargs first (most common usage in FastAPI Depends)
    for v in kwargs.values():
        if isinstance(v, SecurityContext):
            return v
    # Walk positional args
    for a in args:
        if isinstance(a, SecurityContext):
            return a
    return None


def require_permission(
    permission: Permission | str,
    *,
    fail_open: bool = False,
) -> Callable[[F], F]:
    """Decorator that enforces a required permission on a function or method.

    Parameters
    ----------
    permission:
        The :class:`Permission` enum member or string value to require.
    fail_open:
        If ``True``, allow the call when no SecurityContext is found in
        arguments (useful for progressive adoption).  Default: ``False``
        (missing context logs a warning but does NOT block the call since
        many internal paths don't carry a context yet).
    """
    if isinstance(permission, str):
        perm = Permission(permission)
    else:
        perm = permission

    def decorator(func: F) -> F:
        is_async = inspect.iscoroutinefunction(func)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                ctx = _extract_security_context(*args, **kwargs)
                if ctx is None:
                    warnings.warn(
                        f"@require_permission('{perm.value}') on '{func.__qualname__}': "
                        "no SecurityContext found in arguments; call proceeds without check.",
                        stacklevel=2,
                    )
                    if not fail_open:
                        return await func(*args, **kwargs)
                    return await func(*args, **kwargs)
                if not ctx.has_permission(perm):
                    raise PermissionDeniedError(perm, ctx)
                return await func(*args, **kwargs)
            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                ctx = _extract_security_context(*args, **kwargs)
                if ctx is None:
                    warnings.warn(
                        f"@require_permission('{perm.value}') on '{func.__qualname__}': "
                        "no SecurityContext found in arguments; call proceeds without check.",
                        stacklevel=2,
                    )
                    return func(*args, **kwargs)
                if not ctx.has_permission(perm):
                    raise PermissionDeniedError(perm, ctx)
                return func(*args, **kwargs)
            return sync_wrapper  # type: ignore[return-value]

    return decorator
