"""GCP cloud driver — Google Cloud Platform integration.

Requires optional dependency group: ``pip install 'semantic-harness[gcp]'``

Packages used (lazy-imported so installation is optional):
- ``google-auth`` — Application Default Credentials (ADC)
- ``google-cloud-secret-manager`` — Secret Manager
- ``google-cloud-storage`` — Cloud Storage (GCS)
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

_GCS_PREFIX = "gs://"


def _require_google_auth() -> Any:
    try:
        import google.auth  # type: ignore[import-untyped]
        import google.auth.transport.requests  # type: ignore[import-untyped]
        return google.auth
    except ImportError:
        raise ImportError(
            "GCP driver requires google-auth. "
            "Install with: pip install 'semantic-harness[gcp]'"
        )


# ---------------------------------------------------------------------------
# GCP Auth
# ---------------------------------------------------------------------------

class GCPAuthDriver(CloudAuthDriver):
    """Resolves credentials via Application Default Credentials (ADC)."""

    async def get_credentials(self) -> CloudCredentials:
        google_auth = _require_google_auth()
        import google.auth.transport.requests as greq  # type: ignore[import-untyped]

        creds, project = google_auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        # Refresh if needed
        if not creds.valid:
            creds.refresh(greq.Request())

        return CloudCredentials(
            access_token=creds.token,
            expiry=creds.expiry.timestamp() if creds.expiry else None,
            metadata={"project": project, "source": "adc"},
        )

    async def is_available(self) -> bool:
        try:
            google_auth = _require_google_auth()
            google_auth.default()
            return True
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# GCP Secrets
# ---------------------------------------------------------------------------

class GCPSecretProvider(SecretProvider):
    """Google Cloud Secret Manager backend."""

    def __init__(self, project_id: str | None = None) -> None:
        self._project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "")

    def _client(self) -> Any:
        try:
            from google.cloud import secretmanager  # type: ignore[import-untyped]
            return secretmanager.SecretManagerServiceClient()
        except ImportError:
            raise ImportError(
                "GCP Secret Manager requires google-cloud-secret-manager. "
                "Install with: pip install 'semantic-harness[gcp]'"
            )

    def _secret_name(self, key: str) -> str:
        return f"projects/{self._project}/secrets/{key}/versions/latest"

    async def get(self, key: str) -> str:
        client = self._client()
        response = client.access_secret_version(name=self._secret_name(key))
        return response.payload.data.decode("utf-8")

    async def set(self, key: str, value: str) -> None:
        client = self._client()
        parent = f"projects/{self._project}"
        # Create secret if it doesn't exist
        try:
            client.create_secret(
                request={"parent": parent, "secret_id": key, "replication": {"automatic": {}}}
            )
        except Exception:  # noqa: BLE001, S110
            pass  # Already exists
        client.add_secret_version(
            request={"parent": f"{parent}/secrets/{key}", "payload": {"data": value.encode()}}
        )

    async def delete(self, key: str) -> None:
        client = self._client()
        client.delete_secret(name=f"projects/{self._project}/secrets/{key}")

    async def list_keys(self) -> list[str]:
        client = self._client()
        parent = f"projects/{self._project}"
        return [s.name.split("/")[-1] for s in client.list_secrets(request={"parent": parent})]


# ---------------------------------------------------------------------------
# GCS Blob Storage
# ---------------------------------------------------------------------------

class GCSBlobStorage(BlobStorage):
    """Google Cloud Storage blob driver.  URI scheme: ``gs://bucket/path``."""

    def __init__(self, default_bucket: str | None = None) -> None:
        self._default_bucket = default_bucket or os.environ.get("GCS_BUCKET", "")

    def _client(self) -> Any:
        try:
            from google.cloud import storage  # type: ignore[import-untyped]
            return storage.Client()
        except ImportError:
            raise ImportError(
                "GCS blob storage requires google-cloud-storage. "
                "Install with: pip install 'semantic-harness[gcp]'"
            )

    def _parse(self, path: str) -> tuple[str, str]:
        path = path.removeprefix(_GCS_PREFIX)
        parts = path.split("/", 1)
        bucket = parts[0] if len(parts) > 1 else self._default_bucket
        blob_name = parts[1] if len(parts) > 1 else parts[0]
        return bucket, blob_name

    async def upload(self, path: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        client = self._client()
        bucket_name, blob_name = self._parse(path)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(data, content_type=content_type)
        return f"{_GCS_PREFIX}{bucket_name}/{blob_name}"

    async def download(self, path: str) -> bytes:
        client = self._client()
        bucket_name, blob_name = self._parse(path)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: {path}")
        return blob.download_as_bytes()

    async def list(self, prefix: str) -> list[str]:
        client = self._client()
        bucket_name, blob_prefix = self._parse(prefix)
        blobs = client.list_blobs(bucket_name, prefix=blob_prefix)
        return [f"{_GCS_PREFIX}{bucket_name}/{b.name}" for b in blobs]

    async def delete(self, path: str) -> None:
        client = self._client()
        bucket_name, blob_name = self._parse(path)
        client.bucket(bucket_name).blob(blob_name).delete()


# ---------------------------------------------------------------------------
# Composite GCP driver
# ---------------------------------------------------------------------------

class GCPCloudDriver(AbstractCloudDriver):
    """Full GCP driver: ADC + Secret Manager + GCS."""

    def __init__(
        self,
        project_id: str | None = None,
        default_bucket: str | None = None,
    ) -> None:
        self._auth = GCPAuthDriver()
        self._secrets = GCPSecretProvider(project_id)
        self._storage = GCSBlobStorage(default_bucket)

    @property
    def name(self) -> str:
        return "gcp"

    @property
    def auth(self) -> GCPAuthDriver:
        return self._auth

    @property
    def secrets(self) -> GCPSecretProvider:
        return self._secrets

    @property
    def storage(self) -> GCSBlobStorage:
        return self._storage

    async def is_available(self) -> bool:
        return await self._auth.is_available()
