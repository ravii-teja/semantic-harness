"""Abstract base classes for the multi-cloud driver layer.

All cloud drivers implement these ABCs.  The cloud abstraction layer
intentionally uses *async* methods throughout to support FastAPI and
asyncio-based agent runtimes without blocking.

Driver implementations live in ``semantic_harness/cloud/drivers/``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class CloudCredentials:
    """Portable credential bag returned by :meth:`CloudAuthDriver.get_credentials`."""
    access_token: str | None = None
    api_key: str | None = None
    expiry: float | None = None   # Unix timestamp
    metadata: dict[str, Any] | None = None


class CloudAuthDriver(ABC):
    """Resolves cloud-native workload identity credentials."""

    @abstractmethod
    async def get_credentials(self) -> CloudCredentials:
        """Return short-lived credentials for the current cloud identity."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this cloud environment is detected."""
        ...


class SecretProvider(ABC):
    """Unified secret manager interface across GCP / AWS / Azure / local."""

    @abstractmethod
    async def get(self, key: str) -> str:
        """Retrieve a secret value by key.

        Raises
        ------
        KeyError
            If the secret does not exist.
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        """Create or update a secret value."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a secret."""
        ...

    async def list_keys(self) -> list[str]:
        """List all secret keys (optional; not all backends support this)."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support listing secret keys."
        )


class BlobStorage(ABC):
    """Unified blob/object storage interface across GCS / S3 / Azure Blob / local."""

    @abstractmethod
    async def upload(
        self,
        path: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to the given path.  Returns the canonical URI."""
        ...

    @abstractmethod
    async def download(self, path: str) -> bytes:
        """Download bytes from the given path."""
        ...

    @abstractmethod
    async def list(self, prefix: str) -> list[str]:
        """List paths under the given prefix."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete the object at path."""
        ...

    async def exists(self, path: str) -> bool:
        """Return True if the path exists (default: try download)."""
        try:
            await self.download(path)
            return True
        except (FileNotFoundError, KeyError):
            return False


class AbstractCloudDriver(ABC):
    """Composite cloud driver exposing auth, secrets, and blob storage."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier: 'gcp' | 'aws' | 'azure' | 'local'."""
        ...

    @property
    @abstractmethod
    def auth(self) -> CloudAuthDriver:
        """Cloud-native credential resolver."""
        ...

    @property
    @abstractmethod
    def secrets(self) -> SecretProvider:
        """Managed secret store accessor."""
        ...

    @property
    @abstractmethod
    def storage(self) -> BlobStorage:
        """Object/blob storage accessor."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this driver is runnable in the current environment."""
        ...
