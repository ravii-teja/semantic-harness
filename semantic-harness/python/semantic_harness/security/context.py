"""Security context model: immutable principal identity and permission carrier.

Design rationale
----------------
SecurityContext is deliberately *frozen* (immutable after construction). This
prevents any code inside an agent loop from silently elevating its own
privileges mid-turn -- a critical defence-in-depth property.  One context is
resolved at the request boundary and propagated inward; it is never mutated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Standard harness roles.  Roles are cumulative: each includes all below."""
    VIEWER = "viewer"
    ANALYST = "analyst"
    OPERATOR = "operator"
    ADMIN = "admin"


class Permission(str, Enum):
    """Fine-grained individual permissions checked at enforcement points."""
    # Dashboard / API
    DASHBOARD_VIEW = "dashboard:view"
    METRICS_READ = "metrics:read"

    # Graph / memory
    GRAPH_READ = "graph:read"
    GRAPH_WRITE = "graph:write"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"

    # Tool execution
    TOOL_EXECUTE = "tool:execute"
    TOOL_EXECUTE_SQL = "tool:execute:sql"
    TOOL_EXECUTE_DESTRUCTIVE = "tool:execute:destructive"

    # LLM / orchestration
    LLM_CALL = "llm:call"
    ORCHESTRATOR_RUN = "orchestrator:run"

    # Admin
    ADMIN_MIGRATIONS = "admin:migrations"
    ADMIN_SECRETS = "admin:secrets"
    TENANT_MANAGE = "tenant:manage"


# Role → expanded permission set (cumulative upward)
_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset({
        Permission.DASHBOARD_VIEW,
        Permission.METRICS_READ,
    }),
    Role.ANALYST: frozenset({
        Permission.DASHBOARD_VIEW,
        Permission.METRICS_READ,
        Permission.GRAPH_READ,
        Permission.MEMORY_READ,
        Permission.TOOL_EXECUTE_SQL,  # SELECT only
    }),
    Role.OPERATOR: frozenset({
        Permission.DASHBOARD_VIEW,
        Permission.METRICS_READ,
        Permission.GRAPH_READ,
        Permission.GRAPH_WRITE,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.TOOL_EXECUTE,
        Permission.TOOL_EXECUTE_SQL,
        Permission.LLM_CALL,
        Permission.ORCHESTRATOR_RUN,
    }),
    Role.ADMIN: frozenset({p for p in Permission}),  # All permissions
}


def expand_permissions(roles: frozenset[str]) -> frozenset[Permission]:
    """Expand a set of role strings into the union of their permissions."""
    perms: set[Permission] = set()
    for role_str in roles:
        try:
            role = Role(role_str)
            perms.update(_ROLE_PERMISSIONS.get(role, frozenset()))
        except ValueError:
            pass  # Unknown roles are silently ignored (least-privilege default)
    return frozenset(perms)


@dataclass(frozen=True)
class SecurityContext:
    """Immutable principal identity and permission set.

    Resolved once at request ingress (JWT or API key) and propagated
    through the entire agent execution turn.  Must never be mutated.

    Attributes
    ----------
    tenant_id:
        Multi-tenant isolation key.  Injected into all graph/DB queries.
    principal_id:
        Unique identifier for the calling user or service account.
    principal_type:
        One of "human", "agent", or "service".
    roles:
        Effective role set (e.g. ``frozenset({"operator"})``).
    permissions:
        Pre-expanded individual permissions derived from roles plus any
        direct grants embedded in the IdP token.
    cloud:
        Cloud backend resolved at auth time ("gcp" | "aws" | "azure" | "local").
    metadata:
        Arbitrary additional IdP claims or session tags (read-only dict).
    """

    tenant_id: str
    principal_id: str
    principal_type: str = "human"
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[Permission] = field(default_factory=frozenset)
    cloud: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    def has_permission(self, perm: Permission | str) -> bool:
        """Return True if this context holds the requested permission."""
        if isinstance(perm, str):
            try:
                perm = Permission(perm)
            except ValueError:
                return False
        return perm in self.permissions

    def has_role(self, role: Role | str) -> bool:
        """Return True if this context holds the requested role (or higher)."""
        role_str = role.value if isinstance(role, Role) else role
        return role_str in self.roles

    def __repr__(self) -> str:
        roles = sorted(self.roles)
        return (
            f"SecurityContext(tenant={self.tenant_id!r}, "
            f"principal={self.principal_id!r}, "
            f"type={self.principal_type!r}, "
            f"roles={roles})"
        )


# Convenience: a no-auth context for local dev / testing only
ANONYMOUS_CONTEXT = SecurityContext(
    tenant_id="__anonymous__",
    principal_id="anonymous",
    principal_type="human",
    roles=frozenset({"viewer"}),
    permissions=expand_permissions(frozenset({"viewer"})),
    cloud="local",
)

SYSTEM_CONTEXT = SecurityContext(
    tenant_id="__system__",
    principal_id="system",
    principal_type="service",
    roles=frozenset({"admin"}),
    permissions=frozenset(set(Permission)),
    cloud="local",
)
