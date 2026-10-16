"""Local cloud driver — zero external dependencies.

Uses environment variables (or a ``.env`` file) for secrets and the local
filesystem for blob storage.  This is the default driver when no cloud
environment is detected and is also the fallback used in tests and local
development.

Blob storage URI scheme: ``file:///absolute/path/...``
Secret store: ``os.environ`` (or ``SEMANTIC_HARNESS_SECRET_<KEY>=value``)
"""
from __future__ import annotations

import os
import pathlib

from semantic_harness.cloud.base import (
    AbstractCloudDriver,
    BlobStorage,
    CloudAuthDriver,
    CloudCredentials,
    SecretProvider,
)

# Try to load .env file if python-dotenv is available (optional)
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Local Auth
# ---------------------------------------------------------------------------

class LocalAuthDriver(CloudAuthDriver):
    """Reads credentials from environment variables — no network calls."""

    async def get_credentials(self) -> CloudCredentials:
        return CloudCredentials(
            api_key=os.environ.get("SEMANTIC_HARNESS_API_KEY"),
            metadata={"source": "env"},
        )

    async def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Local Secrets
# ---------------------------------------------------------------------------

class LocalSecretProvider(SecretProvider):
    """Reads secrets from environment variables.

    Lookup order:
    1. ``SEMANTIC_HARNESS_SECRET_<UPPER_KEY>``
    2. ``<UPPER_KEY>``
    3. KeyError
    """

    async def get(self, key: str) -> str:
        prefixed = f"SEMANTIC_HARNESS_SECRET_{key.upper()}"
        value = os.environ.get(prefixed) or os.environ.get(key.upper())
        if value is None:
            raise KeyError(f"Secret '{key}' not found in environment.")
        return value

    async def set(self, key: str, value: str) -> None:
        """Sets in the current process environment (not persisted to shell)."""
        os.environ[f"SEMANTIC_HARNESS_SECRET_{key.upper()}"] = value

    async def delete(self, key: str) -> None:
        os.environ.pop(f"SEMANTIC_HARNESS_SECRET_{key.upper()}", None)
        os.environ.pop(key.upper(), None)

    async def list_keys(self) -> list[str]:
        prefix = "SEMANTIC_HARNESS_SECRET_"
        return [k[len(prefix):].lower() for k in os.environ if k.startswith(prefix)]


# ---------------------------------------------------------------------------
# Local Blob Storage
# ---------------------------------------------------------------------------

_FILE_PREFIX = "file://"


class LocalBlobStorage(BlobStorage):
    """Stores blobs as files on the local filesystem.

    Paths should use the ``file:///abs/path`` or plain ``/abs/path`` scheme.
    A ``root_dir`` may be set to sandbox all writes to a specific directory.
    """

    def __init__(self, root_dir: str | None = None) -> None:
        self._root = pathlib.Path(root_dir) if root_dir else pathlib.Path.cwd()

    def _resolve(self, path: str) -> pathlib.Path:
        if path.startswith(_FILE_PREFIX):
            p = pathlib.Path(path[len(_FILE_PREFIX):])
        else:
            p = pathlib.Path(path)
        if not p.is_absolute():
            p = self._root / p
        return p

    async def upload(
        self,
        path: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        resolved = self._resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(data)
        return f"{_FILE_PREFIX}{resolved}"

    async def download(self, path: str) -> bytes:
        resolved = self._resolve(path)
        if not resolved.exists():
            raise FileNotFoundError(f"Blob not found: {path}")
        return resolved.read_bytes()

    async def list(self, prefix: str) -> list[str]:
        resolved = self._resolve(prefix)
        base = resolved if resolved.is_dir() else resolved.parent
        if not base.exists():
            return []
        return [f"{_FILE_PREFIX}{p}" for p in base.rglob("*") if p.is_file()]

    async def delete(self, path: str) -> None:
        resolved = self._resolve(path)
        if resolved.exists():
            resolved.unlink()

    async def exists(self, path: str) -> bool:
        return self._resolve(path).exists()


# ---------------------------------------------------------------------------
# Composite local driver
# ---------------------------------------------------------------------------

class LocalCloudDriver(AbstractCloudDriver):
    """Zero-dependency local cloud driver for dev / testing."""

    def __init__(self, storage_root: str | None = None) -> None:
        self._auth = LocalAuthDriver()
        self._secrets = LocalSecretProvider()
        self._storage = LocalBlobStorage(storage_root)

    @property
    def name(self) -> str:
        return "local"

    @property
    def auth(self) -> LocalAuthDriver:
        return self._auth

    @property
    def secrets(self) -> LocalSecretProvider:
        return self._secrets

    @property
    def storage(self) -> LocalBlobStorage:
        return self._storage

    async def is_available(self) -> bool:
        return True
