from __future__ import annotations

import asyncio
import os
from typing import Optional

from azure.storage.blob.aio import BlobServiceClient, ContainerClient


_blob_service_client: Optional[BlobServiceClient] = None
_photo_container_client: Optional[ContainerClient] = None
_video_container_client: Optional[ContainerClient] = None

_VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm")


def _get_connection_string() -> str:
    conn = os.environ.get("AZURE_BLOB_CONNECTION_STRING", "").strip()
    if not conn:
        raise RuntimeError(
            "AZURE_BLOB_CONNECTION_STRING is not set. Configure it to enable photo storage."
        )
    return conn


def _get_photo_container_name() -> str:
    name = os.environ.get("AZURE_BLOB_CONTAINER", "").strip()
    if not name:
        raise RuntimeError(
            "AZURE_BLOB_CONTAINER is not set. Configure it to enable photo storage."
        )
    return name


def _get_video_container_name() -> str:
    return os.environ.get("AZURE_BLOB_VIDEO_CONTAINER", "").strip() or "hatch-videos"


def _is_video_key(key: str) -> bool:
    k = (key or "").lower()
    return any(k.endswith(ext) for ext in _VIDEO_EXTENSIONS)


async def _get_container_client(container_name: str) -> ContainerClient:
    """
    Return a cached async ContainerClient for the given container name.
    """
    global _blob_service_client, _photo_container_client, _video_container_client

    is_video = container_name == _get_video_container_name()
    cached = _video_container_client if is_video else _photo_container_client
    if cached is not None:
        return cached

    conn_str = _get_connection_string()
    if _blob_service_client is None:
        _blob_service_client = BlobServiceClient.from_connection_string(conn_str)

    client = _blob_service_client.get_container_client(container_name)
    try:
        await client.create_container()
    except Exception:
        pass

    if is_video:
        _video_container_client = client
    else:
        _photo_container_client = client
    return client


async def upload_blob(
    name: str,
    data: bytes,
    content_type: str = "image/jpeg",
    *,
    is_video: bool = False,
) -> None:
    """
    Upload bytes to the photo or video container under the given blob name.
    Overwrites if the blob already exists.
    """
    container_name = _get_video_container_name() if is_video else _get_photo_container_name()
    container = await _get_container_client(container_name)
    blob_client = container.get_blob_client(name)
    await blob_client.upload_blob(data, overwrite=True, content_type=content_type)


async def download_blob(name: str) -> Optional[bytes]:
    """
    Download bytes from the appropriate container (photo or video based on key extension).
    For video keys, tries the video container first, then the photo container (backwards compat).
    Returns None if the blob does not exist.
    """
    if _is_video_key(name):
        containers = [_get_video_container_name(), _get_photo_container_name()]
    else:
        containers = [_get_photo_container_name()]

    for container_name in containers:
        container = await _get_container_client(container_name)
        blob_client = container.get_blob_client(name)
        try:
            stream = await blob_client.download_blob()
            return await stream.readall()
        except Exception:
            continue
    return None


async def delete_blob(name: str) -> bool:
    """
    Delete a blob by name from the appropriate container.
    For video keys, tries the video container first, then the photo container (backwards compat).
    Returns True if deleted, False if blob did not exist in either container.
    """
    if _is_video_key(name):
        containers = [_get_video_container_name(), _get_photo_container_name()]
    else:
        containers = [_get_photo_container_name()]

    for container_name in containers:
        container = await _get_container_client(container_name)
        blob_client = container.get_blob_client(name)
        try:
            await blob_client.delete_blob()
            return True
        except Exception:
            continue
    return False


async def blob_health(timeout_seconds: float = 5.0) -> str:
    """
    Lightweight health check for Azure Blob Storage.
    Returns: "ok", "disabled", or "unavailable".
    """
    conn = os.environ.get("AZURE_BLOB_CONNECTION_STRING", "").strip()
    if not conn or "placeholder" in conn.lower() or "AccountKey=placeholder" in conn:
        return "disabled"
    try:
        client = BlobServiceClient.from_connection_string(conn)
        await asyncio.wait_for(client.get_service_properties(), timeout=timeout_seconds)
        await client.close()
        return "ok"
    except Exception:
        return "unavailable"

