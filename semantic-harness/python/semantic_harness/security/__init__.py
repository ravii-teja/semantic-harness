"""Security package for Semantic Harness.

Provides Role-Based Access Control (RBAC) with:
- Immutable SecurityContext propagated through agent turns
- OIDC/JWKS JWT validation (vendor-neutral; works with any IdP)
- SHA-256 hashed API keys for M2M authentication
- Permission enforcement via @require_permission decorator
- PostgreSQL Row-Level Security helper utilities

Quick start::

    from semantic_harness.security import (
        SecurityContext,
        Role,
        Permission,
        require_permission,
        resolve,
        PermissionDeniedError,
        ANONYMOUS_CONTEXT,
        SYSTEM_CONTEXT,
    )

    # Resolve a JWT or API key
    ctx = resolve("sh_live_prod_abc123")

    # Check a permission
    if ctx.has_permission(Permission.TOOL_EXECUTE):
        ...

    # Enforce on a function
    @require_permission(Permission.ADMIN_MIGRATIONS)
    async def run_migrations(ctx: SecurityContext) -> None:
        ...
"""
from semantic_harness.security.auth import (
    AuthConfig,
    AuthResolver,
    get_resolver,
    resolve,
)
from semantic_harness.security.context import (
    ANONYMOUS_CONTEXT,
    SYSTEM_CONTEXT,
    Permission,
    Role,
    SecurityContext,
    expand_permissions,
)
from semantic_harness.security.decorators import (
    PermissionDeniedError,
    require_permission,
)

__all__ = [
    "ANONYMOUS_CONTEXT",
    "SYSTEM_CONTEXT",
    "AuthConfig",
    "AuthResolver",
    "Permission",
    "PermissionDeniedError",
    "Role",
    "SecurityContext",
    "expand_permissions",
    "get_resolver",
    "require_permission",
    "resolve",
]
