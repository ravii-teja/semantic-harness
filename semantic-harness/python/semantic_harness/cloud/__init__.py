"""Cloud package for Semantic Harness — Multi-Cloud SDK Abstraction Layer.

Provides a unified ``CloudFactory`` and ``get_cloud()`` entry-point that
auto-detects or accepts an explicit cloud backend and returns the matching
driver implementing :class:`~semantic_harness.cloud.base.AbstractCloudDriver`.

Supported backends
------------------
- ``local``  — env vars + local filesystem (always available, zero deps)
- ``gcp``    — Google Cloud ADC + Secret Manager + GCS  [optional: gcp]
- ``aws``    — AWS IAM/IRSA + Secrets Manager + S3      [optional: aws]
- ``azure``  — Azure Managed Identity + Key Vault + Blob [optional: azure]

Quick start::

    from semantic_harness.cloud import get_cloud

    cloud = get_cloud()                    # auto-detect
    cloud = get_cloud("gcp")              # explicit

    secret = await cloud.secrets.get("DB_PASSWORD")
    await cloud.storage.upload("gs://my-bucket/snapshot.bin", data)
    creds = await cloud.auth.get_credentials()

Detection order (when CLOUD_PROVIDER is not set)
-------------------------------------------------
1. ``CLOUD_PROVIDER`` environment variable (override)
2. GCP metadata server (http://169.254.169.254/computeMetadata/v1/)
3. AWS metadata server (http://169.254.169.254/latest/meta-data/)
4. Azure metadata server (http://169.254.169.254/metadata/instance/)
5. Local driver (always succeeds)
"""
from __future__ import annotations

import logging
import os
import urllib.request
from typing import Any

from semantic_harness.cloud.base import AbstractCloudDriver

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cloud auto-detection helpers
# ---------------------------------------------------------------------------

def _probe_metadata(url: str, headers: dict[str, str] | None = None, timeout: float = 0.5) -> bool:
    """Try a quick HTTP HEAD to a metadata server.  Returns True on success."""
    req = urllib.request.Request(url, method="HEAD")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


def _detect_cloud() -> str:
    """Detect the current cloud environment by probing metadata endpoints."""
    explicit = os.environ.get("CLOUD_PROVIDER", "").lower()
    if explicit in ("gcp", "aws", "azure", "local"):
        return explicit

    # GCP: requires Metadata-Flavor header
    if _probe_metadata(
        "http://169.254.169.254/computeMetadata/v1/",
        headers={"Metadata-Flavor": "Google"},
    ):
        return "gcp"

    # AWS: no special header required
    if _probe_metadata("http://169.254.169.254/latest/meta-data/"):
        return "aws"

    # Azure: requires Metadata header
    if _probe_metadata(
        "http://169.254.169.254/metadata/instance?api-version=2021-02-01",
        headers={"Metadata": "true"},
    ):
        return "azure"

    return "local"


# ---------------------------------------------------------------------------
# CloudFactory
# ---------------------------------------------------------------------------

class CloudFactory:
    """Factory that instantiates the appropriate cloud driver.

    Parameters
    ----------
    backend:
        ``'auto'`` (default) probes metadata endpoints to detect the running
        cloud.  Pass ``'gcp'``, ``'aws'``, ``'azure'``, or ``'local'`` to
        force a specific driver.
    **kwargs:
        Additional keyword arguments forwarded to the driver constructor
        (e.g. ``project_id='my-proj'`` for GCP, ``region='eu-west-1'`` for AWS).
    """

    def __init__(self, backend: str = "auto", **kwargs: Any) -> None:
        self._backend = backend
        self._kwargs = kwargs
        self._driver: AbstractCloudDriver | None = None

    def _resolve_backend(self) -> str:
        if self._backend == "auto":
            return _detect_cloud()
        return self._backend.lower()

    def get_driver(self) -> AbstractCloudDriver:
        """Return the cached driver, building it on first call."""
        if self._driver is not None:
            return self._driver

        backend = self._resolve_backend()
        logger.info("CloudFactory: using backend='%s'", backend)

        if backend == "gcp":
            from semantic_harness.cloud.drivers.gcp_driver import GCPCloudDriver
            self._driver = GCPCloudDriver(**self._kwargs)
        elif backend == "aws":
            from semantic_harness.cloud.drivers.aws_driver import AWSCloudDriver
            self._driver = AWSCloudDriver(**self._kwargs)
        elif backend == "azure":
            from semantic_harness.cloud.drivers.azure_driver import AzureCloudDriver
            self._driver = AzureCloudDriver(**self._kwargs)
        else:
            from semantic_harness.cloud.drivers.local_driver import LocalCloudDriver
            self._driver = LocalCloudDriver(**self._kwargs)

        return self._driver


# ---------------------------------------------------------------------------
# Module-level convenience API
# ---------------------------------------------------------------------------

_default_factory: CloudFactory | None = None


def get_cloud(backend: str = "auto", **kwargs: Any) -> AbstractCloudDriver:
    """Return the default cloud driver, auto-detecting the environment.

    Subsequent calls with the same ``backend`` return the cached driver.
    Pass an explicit ``backend`` to override.
    """
    global _default_factory
    if _default_factory is None or _default_factory._backend != backend:
        _default_factory = CloudFactory(backend, **kwargs)
    return _default_factory.get_driver()


__all__ = [
    "AbstractCloudDriver",
    "CloudFactory",
    "get_cloud",
]
