"""AWS cloud driver — Amazon Web Services integration.

Requires optional dependency group: ``pip install 'semantic-harness[aws]'``

Packages used (lazy-imported):
- ``boto3`` — IAM credentials, Secrets Manager, S3
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

_S3_PREFIX = "s3://"


def _boto3_session(**kwargs: Any) -> Any:
    try:
        import boto3  # type: ignore[import-untyped]
        return boto3.Session(**kwargs)
    except ImportError:
        raise ImportError(
            "AWS driver requires boto3. "
            "Install with: pip install 'semantic-harness[aws]'"
        )


# ---------------------------------------------------------------------------
# AWS Auth
# ---------------------------------------------------------------------------

class AWSAuthDriver(CloudAuthDriver):
    """Resolves AWS credentials via IAM Instance Profile / EKS IRSA / env."""

    def __init__(self, region: str | None = None) -> None:
        self._region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    async def get_credentials(self) -> CloudCredentials:
        session = _boto3_session(region_name=self._region)
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("No AWS credentials found (IAM role, env vars, or ~/.aws/credentials).")
        frozen = creds.get_frozen_credentials()
        return CloudCredentials(
            access_token=frozen.token,  # STS session token (if applicable)
            metadata={
                "access_key_id": frozen.access_key,
                "region": self._region,
                "source": "boto3",
            },
        )

    async def is_available(self) -> bool:
        try:
            session = _boto3_session()
            creds = session.get_credentials()
            return creds is not None
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# AWS Secrets Manager
# ---------------------------------------------------------------------------

class AWSSecretProvider(SecretProvider):
    """AWS Secrets Manager backend."""

    def __init__(self, region: str | None = None, prefix: str = "") -> None:
        self._region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self._prefix = prefix or os.environ.get("AWS_SECRET_PREFIX", "")

    def _client(self) -> Any:
        session = _boto3_session(region_name=self._region)
        return session.client("secretsmanager")

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> str:
        client = self._client()
        response = client.get_secret_value(SecretId=self._key(key))
        return response.get("SecretString") or response["SecretBinary"].decode()

    async def set(self, key: str, value: str) -> None:
        client = self._client()
        full_key = self._key(key)
        try:
            client.create_secret(Name=full_key, SecretString=value)
        except client.exceptions.ResourceExistsException:
            client.put_secret_value(SecretId=full_key, SecretString=value)

    async def delete(self, key: str) -> None:
        client = self._client()
        client.delete_secret(SecretId=self._key(key), ForceDeleteWithoutRecovery=True)

    async def list_keys(self) -> list[str]:
        client = self._client()
        paginator = client.get_paginator("list_secrets")
        keys: list[str] = []
        for page in paginator.paginate():
            for s in page["SecretList"]:
                name = s["Name"]
                if name.startswith(self._prefix):
                    keys.append(name[len(self._prefix):])
        return keys


# ---------------------------------------------------------------------------
# S3 Blob Storage
# ---------------------------------------------------------------------------

class S3BlobStorage(BlobStorage):
    """Amazon S3 blob driver.  URI scheme: ``s3://bucket/key``."""

    def __init__(self, region: str | None = None, default_bucket: str | None = None) -> None:
        self._region = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self._default_bucket = default_bucket or os.environ.get("S3_BUCKET", "")

    def _client(self) -> Any:
        session = _boto3_session(region_name=self._region)
        return session.client("s3")

    def _parse(self, path: str) -> tuple[str, str]:
        path = path.removeprefix(_S3_PREFIX)
        parts = path.split("/", 1)
        bucket = parts[0] if len(parts) > 1 else self._default_bucket
        key = parts[1] if len(parts) > 1 else parts[0]
        return bucket, key

    async def upload(self, path: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        client = self._client()
        bucket, key = self._parse(path)
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return f"{_S3_PREFIX}{bucket}/{key}"

    async def download(self, path: str) -> bytes:
        client = self._client()
        bucket, key = self._parse(path)
        try:
            response = client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 object not found: {path}")

    async def list(self, prefix: str) -> list[str]:
        client = self._client()
        bucket, key_prefix = self._parse(prefix)
        response = client.list_objects_v2(Bucket=bucket, Prefix=key_prefix)
        return [f"{_S3_PREFIX}{bucket}/{obj['Key']}" for obj in response.get("Contents", [])]

    async def delete(self, path: str) -> None:
        client = self._client()
        bucket, key = self._parse(path)
        client.delete_object(Bucket=bucket, Key=key)

    async def exists(self, path: str) -> bool:
        client = self._client()
        bucket, key = self._parse(path)
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Composite AWS driver
# ---------------------------------------------------------------------------

class AWSCloudDriver(AbstractCloudDriver):
    """Full AWS driver: IAM/IRSA credentials + Secrets Manager + S3."""

    def __init__(
        self,
        region: str | None = None,
        secret_prefix: str = "",
        default_bucket: str | None = None,
    ) -> None:
        r = region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self._auth = AWSAuthDriver(r)
        self._secrets = AWSSecretProvider(r, secret_prefix)
        self._storage = S3BlobStorage(r, default_bucket)

    @property
    def name(self) -> str:
        return "aws"

    @property
    def auth(self) -> AWSAuthDriver:
        return self._auth

    @property
    def secrets(self) -> AWSSecretProvider:
        return self._secrets

    @property
    def storage(self) -> S3BlobStorage:
        return self._storage

    async def is_available(self) -> bool:
        return await self._auth.is_available()
