from __future__ import annotations

import os
from typing import Optional

from azure.storage.blob.aio import BlobServiceClient, ContainerClient


_blob_service_client: Optional[BlobServiceClient] = None
_container_client: Optional[ContainerClient] = None


def _get_connection_string() -> str:
    conn = os.environ.get("AZURE_BLOB_CONNECTION_STRING", "").strip()
    if not conn:
        raise RuntimeError(
            "AZURE_BLOB_CONNECTION_STRING is not set. Configure it to enable photo storage."
        )
    return conn


def _get_container_name() -> str:
    name = os.environ.get("AZURE_BLOB_CONTAINER", "").strip()
    if not name:
        raise RuntimeError(
            "AZURE_BLOB_CONTAINER is not set. Configure it to enable photo storage."
        )
    return name


async def get_container_client() -> ContainerClient:
    """
    Return a cached async ContainerClient for the configured container.

    Uses AZURE_BLOB_CONNECTION_STRING + AZURE_BLOB_CONTAINER.
    """
    global _blob_service_client, _container_client
    if _container_client is not None:
        return _container_client

    conn_str = _get_connection_string()
    container_name = _get_container_name()

    if _blob_service_client is None:
        _blob_service_client = BlobServiceClient.from_connection_string(conn_str)

    _container_client = _blob_service_client.get_container_client(container_name)
    # Ensure container exists (idempotent)
    try:
        await _container_client.create_container()
    except Exception:
        # Already exists or cannot be created; let actual upload/read fail if misconfigured
        pass
    return _container_client


async def upload_blob(name: str, data: bytes, content_type: str = "image/jpeg") -> None:
    """
    Upload bytes to the configured container under the given blob name.
    Overwrites if the blob already exists.
    """
    container = await get_container_client()
    blob_client = container.get_blob_client(name)
    await blob_client.upload_blob(data, overwrite=True, content_type=content_type)


async def download_blob(name: str) -> Optional[bytes]:
    """
    Download bytes from the configured container. Returns None if the blob does not exist.
    """
    container = await get_container_client()
    blob_client = container.get_blob_client(name)
    try:
        stream = await blob_client.download_blob()
        return await stream.readall()
    except Exception:
        return None

