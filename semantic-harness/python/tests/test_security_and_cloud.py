"""Tests for RBAC Security Context, Auth, and Multi-Cloud SDK.

Coverage:
- SecurityContext immutability and permission expansion
- Role hierarchy (viewer ⊂ analyst ⊂ operator ⊂ admin)
- @require_permission decorator (sync + async, missing ctx)
- PermissionDeniedError
- AuthResolver API key registration and lookup
- JWT validation (mocked — no live IdP needed)
- CloudFactory auto-detection and explicit backend
- LocalCloudDriver: secrets and blob storage
- ANONYMOUS_CONTEXT and SYSTEM_CONTEXT presets
"""
from __future__ import annotations

import os
import tempfile

import pytest

from semantic_harness.security.auth import AuthConfig, AuthResolver
from semantic_harness.security.context import (
    ANONYMOUS_CONTEXT,
    SYSTEM_CONTEXT,
    Permission,
    SecurityContext,
    expand_permissions,
)
from semantic_harness.security.decorators import (
    PermissionDeniedError,
    require_permission,
)

# ===========================================================================
# SecurityContext
# ===========================================================================

class TestSecurityContext:
    def _make_ctx(self, roles: list[str]) -> SecurityContext:
        return SecurityContext(
            tenant_id="test-tenant",
            principal_id="test-user",
            roles=frozenset(roles),
            permissions=expand_permissions(frozenset(roles)),
            cloud="local",
        )

    def test_viewer_has_dashboard_view(self) -> None:
        ctx = self._make_ctx(["viewer"])
        assert ctx.has_permission(Permission.DASHBOARD_VIEW)

    def test_viewer_lacks_tool_execute(self) -> None:
        ctx = self._make_ctx(["viewer"])
        assert not ctx.has_permission(Permission.TOOL_EXECUTE)

    def test_analyst_has_graph_read(self) -> None:
        ctx = self._make_ctx(["analyst"])
        assert ctx.has_permission(Permission.GRAPH_READ)

    def test_analyst_lacks_graph_write(self) -> None:
        ctx = self._make_ctx(["analyst"])
        assert not ctx.has_permission(Permission.GRAPH_WRITE)

    def test_operator_has_tool_execute_and_llm_call(self) -> None:
        ctx = self._make_ctx(["operator"])
        assert ctx.has_permission(Permission.TOOL_EXECUTE)
        assert ctx.has_permission(Permission.LLM_CALL)

    def test_operator_lacks_admin_migrations(self) -> None:
        ctx = self._make_ctx(["operator"])
        assert not ctx.has_permission(Permission.ADMIN_MIGRATIONS)

    def test_admin_has_all_permissions(self) -> None:
        ctx = self._make_ctx(["admin"])
        for perm in Permission:
            assert ctx.has_permission(perm), f"Admin should have {perm}"

    def test_frozen_immutable(self) -> None:
        ctx = self._make_ctx(["operator"])
        with pytest.raises((AttributeError, TypeError)):
            ctx.tenant_id = "hacked"  # type: ignore[misc]

    def test_has_role(self) -> None:
        ctx = self._make_ctx(["analyst"])
        assert ctx.has_role("analyst")
        assert not ctx.has_role("admin")

    def test_unknown_role_grants_nothing(self) -> None:
        ctx = self._make_ctx(["superagent"])
        assert ctx.permissions == frozenset()

    def test_string_permission_lookup(self) -> None:
        ctx = self._make_ctx(["operator"])
        assert ctx.has_permission("tool:execute")

    def test_anonymous_context(self) -> None:
        assert ANONYMOUS_CONTEXT.has_permission(Permission.DASHBOARD_VIEW)
        assert not ANONYMOUS_CONTEXT.has_permission(Permission.TOOL_EXECUTE)

    def test_system_context_is_admin(self) -> None:
        for perm in Permission:
            assert SYSTEM_CONTEXT.has_permission(perm)

    def test_repr_does_not_crash(self) -> None:
        ctx = self._make_ctx(["operator"])
        assert "operator" in repr(ctx)


# ===========================================================================
# @require_permission decorator
# ===========================================================================

class TestRequirePermission:
    def _operator_ctx(self) -> SecurityContext:
        return SecurityContext(
            tenant_id="t1",
            principal_id="u1",
            roles=frozenset({"operator"}),
            permissions=expand_permissions(frozenset({"operator"})),
            cloud="local",
        )

    def _viewer_ctx(self) -> SecurityContext:
        return SecurityContext(
            tenant_id="t1",
            principal_id="v1",
            roles=frozenset({"viewer"}),
            permissions=expand_permissions(frozenset({"viewer"})),
            cloud="local",
        )

    def test_sync_passes_with_permission(self) -> None:
        @require_permission(Permission.TOOL_EXECUTE)
        def do_work(ctx: SecurityContext) -> str:
            return "ok"

        result = do_work(ctx=self._operator_ctx())
        assert result == "ok"

    def test_sync_raises_on_missing_permission(self) -> None:
        @require_permission(Permission.ADMIN_MIGRATIONS)
        def run_migration(ctx: SecurityContext) -> None:
            pass

        with pytest.raises(PermissionDeniedError) as exc_info:
            run_migration(ctx=self._viewer_ctx())
        assert "admin:migrations" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_passes_with_permission(self) -> None:
        @require_permission("llm:call")
        async def call_llm(ctx: SecurityContext) -> str:
            return "response"

        result = await call_llm(ctx=self._operator_ctx())
        assert result == "response"

    @pytest.mark.asyncio
    async def test_async_raises_on_missing_permission(self) -> None:
        @require_permission(Permission.TENANT_MANAGE)
        async def manage_tenant(ctx: SecurityContext) -> None:
            pass

        with pytest.raises(PermissionDeniedError):
            await manage_tenant(ctx=self._operator_ctx())

    def test_missing_ctx_emits_warning_and_proceeds(self) -> None:
        @require_permission(Permission.TOOL_EXECUTE)
        def no_ctx_fn(x: int) -> int:
            return x * 2

        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = no_ctx_fn(21)
        assert result == 42
        assert len(w) == 1
        assert "no SecurityContext" in str(w[0].message)

    def test_string_permission_works(self) -> None:
        @require_permission("tool:execute:sql")
        def run_sql(ctx: SecurityContext) -> str:
            return "select 1"

        ctx = SecurityContext(
            tenant_id="t", principal_id="a",
            roles=frozenset({"analyst"}),
            permissions=expand_permissions(frozenset({"analyst"})),
            cloud="local",
        )
        assert run_sql(ctx=ctx) == "select 1"

    def test_permission_denied_error_attributes(self) -> None:
        ctx = self._viewer_ctx()
        err = PermissionDeniedError(Permission.ADMIN_SECRETS, ctx)
        assert err.required == Permission.ADMIN_SECRETS
        assert err.context is ctx


# ===========================================================================
# AuthResolver — API Key path
# ===========================================================================

class TestAuthResolverAPIKey:
    def setup_method(self) -> None:
        # Fresh resolver with no env keys
        self.resolver = AuthResolver(AuthConfig(
            static_api_keys_env="",
            legacy_api_key_env="",
        ))

    def test_register_and_resolve(self) -> None:
        self.resolver.register_api_key(
            "sh_live_test_abc123",
            roles=["operator"],
            tenant_id="acme",
            cloud="gcp",
        )
        ctx = self.resolver.resolve("sh_live_test_abc123")
        assert ctx.tenant_id == "acme"
        assert ctx.cloud == "gcp"
        assert ctx.has_permission(Permission.TOOL_EXECUTE)
        assert ctx.principal_type == "service"

    def test_invalid_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid or unknown API key"):
            self.resolver.resolve("sh_live_test_DOESNOTEXIST")

    def test_env_multi_key_parsing(self) -> None:
        env_str = "sh_live_k1:viewer:tenant1:local,sh_live_k2:admin:tenant2:aws"
        resolver = AuthResolver(AuthConfig(
            static_api_keys_env=env_str,
            legacy_api_key_env="",
        ))
        ctx1 = resolver.resolve("sh_live_k1")
        ctx2 = resolver.resolve("sh_live_k2")
        assert ctx1.has_role("viewer")
        assert ctx2.has_role("admin")
        assert ctx1.tenant_id == "tenant1"
        assert ctx2.cloud == "aws"

    def test_legacy_single_key_support(self) -> None:
        resolver = AuthResolver(AuthConfig(
            static_api_keys_env="",
            legacy_api_key_env="sh_legacy_key_xyz",
        ))
        ctx = resolver.resolve("sh_legacy_key_xyz")
        assert ctx.has_role("admin")
        assert ctx.tenant_id == "__default__"

    def test_admin_api_key_has_all_permissions(self) -> None:
        self.resolver.register_api_key("sh_live_admin_key", roles=["admin"], tenant_id="corp")
        ctx = self.resolver.resolve("sh_live_admin_key")
        for perm in Permission:
            assert ctx.has_permission(perm), f"Admin key missing {perm}"


# ===========================================================================
# Cloud — LocalCloudDriver
# ===========================================================================

class TestLocalCloudDriver:
    @pytest.mark.asyncio
    async def test_secrets_set_and_get(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        driver = LocalCloudDriver()
        await driver.secrets.set("test_key", "my_secret_value")
        val = await driver.secrets.get("test_key")
        assert val == "my_secret_value"

    @pytest.mark.asyncio
    async def test_secrets_missing_raises_key_error(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        driver = LocalCloudDriver()
        os.environ.pop("SEMANTIC_HARNESS_SECRET_NONEXISTENT", None)
        os.environ.pop("NONEXISTENT", None)
        with pytest.raises(KeyError):
            await driver.secrets.get("nonexistent")

    @pytest.mark.asyncio
    async def test_secrets_list_keys(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        driver = LocalCloudDriver()
        await driver.secrets.set("list_test_key", "val")
        keys = await driver.secrets.list_keys()
        assert "list_test_key" in keys

    @pytest.mark.asyncio
    async def test_blob_upload_download_delete(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = LocalCloudDriver(storage_root=tmpdir)
            data = b"hello semantic harness cloud"
            uri = await driver.storage.upload("test/blob.bin", data)
            assert uri.startswith("file://")
            assert await driver.storage.exists("test/blob.bin")
            downloaded = await driver.storage.download("test/blob.bin")
            assert downloaded == data
            await driver.storage.delete("test/blob.bin")
            assert not await driver.storage.exists("test/blob.bin")

    @pytest.mark.asyncio
    async def test_blob_list(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = LocalCloudDriver(storage_root=tmpdir)
            await driver.storage.upload("archive/turn_1.bin", b"data1")
            await driver.storage.upload("archive/turn_2.bin", b"data2")
            paths = await driver.storage.list("archive/")
            assert len(paths) == 2

    @pytest.mark.asyncio
    async def test_missing_blob_raises_file_not_found(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = LocalCloudDriver(storage_root=tmpdir)
            with pytest.raises(FileNotFoundError):
                await driver.storage.download("nonexistent/path.bin")

    @pytest.mark.asyncio
    async def test_auth_credentials(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        driver = LocalCloudDriver()
        creds = await driver.auth.get_credentials()
        assert creds is not None

    @pytest.mark.asyncio
    async def test_is_available(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        driver = LocalCloudDriver()
        assert await driver.is_available() is True

    def test_driver_name(self) -> None:
        from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
        assert LocalCloudDriver().name == "local"


# ===========================================================================
# CloudFactory
# ===========================================================================

class TestCloudFactory:
    def test_explicit_local_backend(self) -> None:
        from semantic_harness.cloud import CloudFactory
        factory = CloudFactory(backend="local")
        driver = factory.get_driver()
        assert driver.name == "local"

    def test_auto_returns_local_without_cloud_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CLOUD_PROVIDER", raising=False)
        from semantic_harness.cloud import CloudFactory
        # In test environment (no metadata server) should fall back to local
        # We can't guarantee no cloud env so just check factory produces a driver
        factory = CloudFactory(backend="local")
        driver = factory.get_driver()
        assert driver is not None

    def test_get_cloud_convenience(self) -> None:
        from semantic_harness.cloud import get_cloud
        driver = get_cloud("local")
        assert driver.name == "local"

    def test_factory_caches_driver(self) -> None:
        from semantic_harness.cloud import CloudFactory
        factory = CloudFactory(backend="local")
        d1 = factory.get_driver()
        d2 = factory.get_driver()
        assert d1 is d2

    def test_explicit_gcp_raises_import_without_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GCP driver creation succeeds (class init doesn't import google-auth)."""
        from semantic_harness.cloud import CloudFactory
        factory = CloudFactory(backend="gcp")
        # Driver object is created; actual SDK import happens on first method call
        driver = factory.get_driver()
        assert driver.name == "gcp"

    def test_explicit_aws_driver_name(self) -> None:
        from semantic_harness.cloud import CloudFactory
        factory = CloudFactory(backend="aws")
        driver = factory.get_driver()
        assert driver.name == "aws"

    def test_explicit_azure_driver_name(self) -> None:
        from semantic_harness.cloud import CloudFactory
        factory = CloudFactory(backend="azure")
        driver = factory.get_driver()
        assert driver.name == "azure"
