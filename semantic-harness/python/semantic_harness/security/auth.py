"""OIDC/JWT + API Key identity resolution.

Resolves any inbound credential (JWT Bearer token or X-API-Key) into a
:class:`~semantic_harness.security.context.SecurityContext`.

JWT path (OIDC/JWKS)
--------------------
Works with *any* OpenID Connect compliant IdP -- Okta, Azure Entra ID,
AWS Cognito, Keycloak, Google Workspace, Auth0, Firebase Auth.  No vendor SDK
required; uses only ``PyJWT[crypto]`` for signature verification against the
IdP's public JWKS endpoint.

API Key path (M2M)
------------------
Prefixed keys (``sh_live_...``) are stored as SHA-256 hashes.  Validation is
O(1) against an in-memory or environment-backed key store.

Configuration
-------------
All settings are read from environment variables (or an injected dict) so the
auth module is fully stateless and testable without a real IdP:

.. code-block:: bash

    JWKS_URI=https://idp.example.com/.well-known/openid-configuration
    RBAC_AUDIENCE=semantic-harness-api
    RBAC_ISSUER=https://idp.example.com/
    RBAC_ROLES_CLAIM=sh_roles          # JWT claim that carries role list
    RBAC_TENANT_CLAIM=sh_tenant_id     # JWT claim for tenant isolation
    RBAC_CLOUD_CLAIM=sh_cloud          # optional: overrides cloud backend
    JWKS_CACHE_TTL=3600                # seconds
    SEMANTIC_HARNESS_API_KEYS=sh_live_dev_abc123:viewer:dev-tenant,...
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from semantic_harness.security.context import (
    ANONYMOUS_CONTEXT,
    SecurityContext,
    expand_permissions,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AuthConfig:
    """Auth configuration, typically loaded from environment variables."""
    jwks_uri: str = field(
        default_factory=lambda: os.environ.get("JWKS_URI", "")
    )
    audience: str = field(
        default_factory=lambda: os.environ.get("RBAC_AUDIENCE", "semantic-harness-api")
    )
    issuer: str = field(
        default_factory=lambda: os.environ.get("RBAC_ISSUER", "")
    )
    roles_claim: str = field(
        default_factory=lambda: os.environ.get("RBAC_ROLES_CLAIM", "sh_roles")
    )
    tenant_claim: str = field(
        default_factory=lambda: os.environ.get("RBAC_TENANT_CLAIM", "sh_tenant_id")
    )
    cloud_claim: str = field(
        default_factory=lambda: os.environ.get("RBAC_CLOUD_CLAIM", "sh_cloud")
    )
    jwks_cache_ttl: int = field(
        default_factory=lambda: int(os.environ.get("JWKS_CACHE_TTL", "3600"))
    )
    # Comma-separated: "key:role:tenant,key2:role2:tenant2"
    static_api_keys_env: str = field(
        default_factory=lambda: os.environ.get("SEMANTIC_HARNESS_API_KEYS", "")
    )
    # Legacy single key from previous dashboard auth
    legacy_api_key_env: str = field(
        default_factory=lambda: os.environ.get("SEMANTIC_HARNESS_API_KEY", "")
    )


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------

class _JWKSCache:
    """Simple in-process JWKS public key cache with TTL refresh."""

    def __init__(self, ttl: int = 3600) -> None:
        self._ttl = ttl
        self._cache: dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._raw_uri: str = ""

    def _resolve_uri(self, uri: str) -> str:
        """If uri points to an OIDC discovery doc, follow it to jwks_uri."""
        if "openid-configuration" in uri or "/.well-known" in uri:
            try:
                with urllib.request.urlopen(uri, timeout=5) as resp:
                    doc = json.loads(resp.read())
                    return doc.get("jwks_uri", uri)
            except Exception as exc:  # noqa: BLE001
                logger.warning("JWKS discovery failed for %s: %s", uri, exc)
        return uri

    def get_keys(self, jwks_uri: str) -> dict[str, Any]:
        """Return JWKS key set, fetching/refreshing as needed."""
        now = time.monotonic()
        if self._raw_uri != jwks_uri or now - self._fetched_at > self._ttl:
            resolved = self._resolve_uri(jwks_uri)
            try:
                with urllib.request.urlopen(resolved, timeout=5) as resp:
                    data = json.loads(resp.read())
                    self._cache = {k["kid"]: k for k in data.get("keys", [])}
                    self._fetched_at = now
                    self._raw_uri = jwks_uri
                    logger.debug("JWKS refreshed: %d keys from %s", len(self._cache), resolved)
            except Exception as exc:  # noqa: BLE001
                logger.error("JWKS fetch failed: %s", exc)
        return self._cache


_jwks_cache = _JWKSCache()


# ---------------------------------------------------------------------------
# API Key store
# ---------------------------------------------------------------------------

@dataclass
class _APIKeyEntry:
    hashed_key: str
    roles: frozenset[str]
    tenant_id: str
    cloud: str = "local"


class _APIKeyStore:
    """In-memory hashed API key registry."""

    def __init__(self) -> None:
        self._entries: dict[str, _APIKeyEntry] = {}

    def register(self, raw_key: str, roles: list[str], tenant_id: str, cloud: str = "local") -> None:
        h = hashlib.sha256(raw_key.encode()).hexdigest()
        self._entries[h] = _APIKeyEntry(
            hashed_key=h,
            roles=frozenset(roles),
            tenant_id=tenant_id,
            cloud=cloud,
        )
        logger.debug("API key registered for tenant=%s roles=%s", tenant_id, roles)

    def lookup(self, raw_key: str) -> _APIKeyEntry | None:
        h = hashlib.sha256(raw_key.encode()).hexdigest()
        return self._entries.get(h)

    def load_from_env(self, env_string: str) -> None:
        """Parse comma-separated 'key:role:tenant[:cloud]' entries."""
        if not env_string.strip():
            return
        for entry in env_string.split(","):
            parts = entry.strip().split(":")
            if len(parts) < 3:
                logger.warning("Invalid API key env entry (expected key:role:tenant): %s", entry)
                continue
            raw_key, role, tenant = parts[0], parts[1], parts[2]
            cloud_backend = parts[3] if len(parts) > 3 else "local"
            self.register(raw_key, [role], tenant, cloud_backend)


_api_key_store = _APIKeyStore()


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------

class AuthResolver:
    """Resolves inbound credentials to SecurityContext.

    Supports JWT Bearer tokens (OIDC/JWKS validated) and prefixed API keys.
    Thread-safe for concurrent async usage (no shared mutable state beyond
    the module-level JWKS cache which is tolerable-race-safe for reads).
    """

    def __init__(self, config: AuthConfig | None = None) -> None:
        self.config = config or AuthConfig()
        # Load static API keys from env at construction time
        _api_key_store.load_from_env(self.config.static_api_keys_env)
        # Legacy single key support (previous dashboard.py behaviour)
        if self.config.legacy_api_key_env:
            _api_key_store.register(
                self.config.legacy_api_key_env,
                roles=["admin"],
                tenant_id="__default__",
                cloud="local",
            )

    def register_api_key(
        self,
        raw_key: str,
        roles: list[str],
        tenant_id: str,
        cloud: str = "local",
    ) -> None:
        """Programmatically register a hashed API key (e.g. from DB load)."""
        _api_key_store.register(raw_key, roles, tenant_id, cloud)

    def resolve(self, token: str) -> SecurityContext:
        """Resolve a raw token string to SecurityContext.

        Tries API key first (O(1) hash lookup), then falls back to JWT
        validation.  Returns ANONYMOUS_CONTEXT if JWKS is not configured and
        the key is unrecognised.
        """
        if token.startswith("sh_"):
            return self._resolve_api_key(token)
        return self._resolve_jwt(token)

    def _resolve_api_key(self, raw_key: str) -> SecurityContext:
        entry = _api_key_store.lookup(raw_key)
        if entry is None:
            raise ValueError("Invalid or unknown API key.")
        perms = expand_permissions(entry.roles)
        return SecurityContext(
            tenant_id=entry.tenant_id,
            principal_id=f"apikey:{hashlib.sha256(raw_key.encode()).hexdigest()[:8]}",
            principal_type="service",
            roles=entry.roles,
            permissions=perms,
            cloud=entry.cloud,
        )

    def _resolve_jwt(self, raw_token: str) -> SecurityContext:
        """Validate JWT via JWKS and extract SecurityContext."""
        cfg = self.config
        if not cfg.jwks_uri:
            logger.warning("JWKS_URI not configured; returning anonymous context.")
            return ANONYMOUS_CONTEXT

        try:
            import jwt as _jwt  # PyJWT[crypto]
        except ImportError:
            raise ImportError(
                "JWT validation requires PyJWT[crypto]. "
                "Install with: pip install 'semantic-harness[rbac]'"
            )

        # Peek at header to get kid
        header = _jwt.get_unverified_header(raw_token)
        kid = header.get("kid", "")
        keys = _jwks_cache.get_keys(cfg.jwks_uri)

        if kid not in keys:
            # Try without kid matching (single-key setups)
            if not keys:
                raise ValueError("No JWKS keys available for JWT validation.")
            raw_jwk = next(iter(keys.values()))
        else:
            raw_jwk = keys[kid]

        public_key = _jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(raw_jwk))
        options: dict[str, Any] = {}
        if not cfg.audience:
            options["verify_aud"] = False

        payload: dict[str, Any] = _jwt.decode(
            raw_token,
            key=public_key,
            algorithms=["RS256", "ES256"],
            audience=cfg.audience or None,
            issuer=cfg.issuer or None,
            options=options,
        )

        roles_raw = payload.get(cfg.roles_claim, [])
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]
        roles = frozenset(roles_raw)

        tenant_id = payload.get(cfg.tenant_claim, "__default__")
        cloud = payload.get(cfg.cloud_claim, "local")
        principal_id = payload.get("sub", "unknown")

        return SecurityContext(
            tenant_id=tenant_id,
            principal_id=principal_id,
            principal_type="human",
            roles=roles,
            permissions=expand_permissions(roles),
            cloud=cloud,
            metadata=dict(payload),
        )


# Module-level singleton (lazily initialised)
_default_resolver: AuthResolver | None = None


def get_resolver() -> AuthResolver:
    """Return the default module-level AuthResolver (singleton)."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = AuthResolver()
    return _default_resolver


def resolve(token: str) -> SecurityContext:
    """Convenience wrapper: resolve a token using the default resolver."""
    return get_resolver().resolve(token)
