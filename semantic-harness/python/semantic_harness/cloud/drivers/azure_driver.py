"""Azure cloud driver — Microsoft Azure integration.

Requires optional dependency group: ``pip install 'semantic-harness[azure]'``

Packages used (lazy-imported):
- ``azure-identity`` — Managed Identity / DefaultAzureCredential
- ``azure-keyvault-secrets`` — Azure Key Vault
- ``azure-storage-blob`` — Azure Blob Storage
"""
from __future__ import annotations

import logging
import os
from typing import Any

from semantic_harness.cloud.base import (
    AbstractCloudDriver,
    BlobStorage,
    CloudAuthDriver,
    CloudCredentials,
    SecretProvider,
)

logger = logging.getLogger(__name__)

_AZ_PREFIX = "az://"


def _require_identity() -> Any:
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        return DefaultAzureCredential()
    except ImportError:
        raise ImportError(
            "Azure driver requires azure-identity. "
            "Install with: pip install 'semantic-harness[azure]'"
        )


# ---------------------------------------------------------------------------
# Azure Auth
# ---------------------------------------------------------------------------

class AzureAuthDriver(CloudAuthDriver):
    """Resolves Azure credentials via Managed Identity / DefaultAzureCredential."""

    _SCOPE = "https://management.azure.com/.default"

    async def get_credentials(self) -> CloudCredentials:
        credential = _require_identity()
        token = credential.get_token(self._SCOPE)
        return CloudCredentials(
            access_token=token.token,
            expiry=float(token.expires_on),
            metadata={"source": "DefaultAzureCredential"},
        )

    async def is_available(self) -> bool:
        try:
            credential = _require_identity()
            credential.get_token(self._SCOPE)
            return True
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Azure Key Vault Secrets
# ---------------------------------------------------------------------------

class AzureSecretProvider(SecretProvider):
    """Azure Key Vault Secrets backend."""

    def __init__(self, vault_url: str | None = None) -> None:
        self._vault_url = vault_url or os.environ.get("AZURE_KEY_VAULT_URL", "")

    def _client(self) -> Any:
        try:
            from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]
            return SecretClient(vault_url=self._vault_url, credential=_require_identity())
        except ImportError:
            raise ImportError(
                "Azure Key Vault requires azure-keyvault-secrets. "
                "Install with: pip install 'semantic-harness[azure]'"
            )

    async def get(self, key: str) -> str:
        client = self._client()
        secret = client.get_secret(key)
        if secret.value is None:
            raise KeyError(f"Azure Key Vault secret '{key}' has no value.")
        return secret.value

    async def set(self, key: str, value: str) -> None:
        client = self._client()
        client.set_secret(key, value)

    async def delete(self, key: str) -> None:
        client = self._client()
        client.begin_delete_secret(key).result()

    async def list_keys(self) -> list[str]:
        client = self._client()
        return [s.name for s in client.list_properties_of_secrets()]


# ---------------------------------------------------------------------------
# Azure Blob Storage
# ---------------------------------------------------------------------------

class AzureBlobStorage(BlobStorage):
    """Azure Blob Storage driver.  URI scheme: ``az://container/blob``."""

    def __init__(
        self,
        account_url: str | None = None,
        default_container: str | None = None,
    ) -> None:
        self._account_url = account_url or os.environ.get("AZURE_STORAGE_ACCOUNT_URL", "")
        self._default_container = default_container or os.environ.get("AZURE_STORAGE_CONTAINER", "")

    def _client(self) -> Any:
        try:
            from azure.storage.blob import BlobServiceClient  # type: ignore[import-untyped]
            return BlobServiceClient(account_url=self._account_url, credential=_require_identity())
        except ImportError:
            raise ImportError(
                "Azure Blob Storage requires azure-storage-blob. "
                "Install with: pip install 'semantic-harness[azure]'"
            )

    def _parse(self, path: str) -> tuple[str, str]:
        path = path.removeprefix(_AZ_PREFIX)
        parts = path.split("/", 1)
        container = parts[0] if len(parts) > 1 else self._default_container
        blob = parts[1] if len(parts) > 1 else parts[0]
        return container, blob

    async def upload(self, path: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        service_client = self._client()
        container, blob_name = self._parse(path)
        blob_client = service_client.get_blob_client(container=container, blob=blob_name)
        blob_client.upload_blob(data, overwrite=True, content_settings={"content_type": content_type})
        return f"{_AZ_PREFIX}{container}/{blob_name}"

    async def download(self, path: str) -> bytes:
        service_client = self._client()
        container, blob_name = self._parse(path)
        blob_client = service_client.get_blob_client(container=container, blob=blob_name)
        if not blob_client.exists():
            raise FileNotFoundError(f"Azure blob not found: {path}")
        return blob_client.download_blob().readall()

    async def list(self, prefix: str) -> list[str]:
        service_client = self._client()
        container, blob_prefix = self._parse(prefix)
        container_client = service_client.get_container_client(container)
        return [
            f"{_AZ_PREFIX}{container}/{b.name}"
            for b in container_client.list_blobs(name_starts_with=blob_prefix)
        ]

    async def delete(self, path: str) -> None:
        service_client = self._client()
        container, blob_name = self._parse(path)
        service_client.get_blob_client(container=container, blob=blob_name).delete_blob()

    async def exists(self, path: str) -> bool:
        service_client = self._client()
        container, blob_name = self._parse(path)
        return service_client.get_blob_client(container=container, blob=blob_name).exists()


# ---------------------------------------------------------------------------
# Composite Azure driver
# ---------------------------------------------------------------------------

class AzureCloudDriver(AbstractCloudDriver):
    """Full Azure driver: Managed Identity + Key Vault + Blob Storage."""

    def __init__(
        self,
        vault_url: str | None = None,
        storage_account_url: str | None = None,
        default_container: str | None = None,
    ) -> None:
        self._auth = AzureAuthDriver()
        self._secrets = AzureSecretProvider(vault_url)
        self._storage = AzureBlobStorage(storage_account_url, default_container)

    @property
    def name(self) -> str:
        return "azure"

    @property
    def auth(self) -> AzureAuthDriver:
        return self._auth

    @property
    def secrets(self) -> AzureSecretProvider:
        return self._secrets

    @property
    def storage(self) -> AzureBlobStorage:
        return self._storage

    async def is_available(self) -> bool:
        return await self._auth.is_available()
