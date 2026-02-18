from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

import aiohttp

from app.azure_blob import download_blob, upload_blob


def make_photo_key(baby_id: int | str, entry: dict[str, Any]) -> str:
    """
    Build a stable blob key for a photo entry.

    Uses baby_id and the photo's createDate (or weightDate) as an identifier so we can
    find the same photo again when backfilling.
    """
    raw = entry.get("createDate") or entry.get("weightDate") or ""
    # Normalize to date string (YYYY-MM-DD) plus full timestamp for uniqueness
    ts = (raw or "").strip().replace("T", " ").replace("Z", "")
    # Fallback: use current time if missing
    if not ts:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    safe_ts = ts.replace(" ", "T").replace(":", "-")
    return f"baby/{baby_id}/photos/{safe_ts}.jpg"


async def fetch_and_store_photo(url: str, key: str, timeout_seconds: float = 15.0) -> Optional[bytes]:
    """
    Download a photo from the Hatch URL once and store it in Azure Blob Storage.

    Returns the downloaded bytes (or None on error) so callers can immediately serve it.
    """
    if not url:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
                # Try to infer content-type; default to image/jpeg
                content_type = resp.headers.get("Content-Type", "image/jpeg")
    except Exception:
        return None

    try:
        await upload_blob(key, data, content_type=content_type)
    except Exception:
        # Ignore storage errors; caller can still use bytes for this response
        pass
    return data


async def get_photo_bytes(key: str) -> Optional[bytes]:
    """
    Fetch photo bytes from Azure Blob Storage by key.

    Returns None if the blob does not exist.
    """
    return await download_blob(key)

