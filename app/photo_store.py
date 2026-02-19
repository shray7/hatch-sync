from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

import aiohttp

from app.azure_blob import download_blob, upload_blob


def _normalize_photo_timestamp(raw: str) -> str:
    """
    Normalize a createDate/weightDate string to a safe key segment: YYYY-MM-DDTHH-MM-SS.
    Strips fractional seconds and 'Z' so keys are consistent regardless of API format.
    """
    ts = (raw or "").strip().replace("Z", "")
    # Drop fractional seconds so "2026-02-17T23:16:08.000" -> "2026-02-17T23:16:08"
    if "." in ts:
        ts = ts.split(".")[0]
    ts = ts.replace("T", " ").strip()
    if not ts:
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    return ts.replace(" ", "T").replace(":", "-")


def make_photo_key(baby_id: int | str, entry: dict[str, Any]) -> str:
    """
    Build a stable blob key for a photo entry.

    Uses baby_id and the photo's createDate (or weightDate) as an identifier so we can
    find the same photo again when backfilling. Timestamp is normalized (no fractional
    seconds) so keys match regardless of Hatch API format.
    """
    raw = entry.get("createDate") or entry.get("weightDate") or ""
    safe_ts = _normalize_photo_timestamp(raw)
    return f"baby/{baby_id}/photos/{safe_ts}.jpg"


def normalize_photo_key_for_lookup(key: str) -> str:
    """
    Normalize a photo key for lookup so keys with/without fractional seconds match.
    e.g. baby/123/photos/2026-02-17T23-16-08.000.jpg -> baby/123/photos/2026-02-17T23-16-08.jpg
    """
    if not key or ".jpg" not in key:
        return key
    prefix, ext = key.rsplit(".", 1)
    # Strip fractional seconds in the timestamp segment (last path segment before .jpg)
    if "/" in prefix:
        path, ts = prefix.rsplit("/", 1)
        if "." in ts:
            ts = ts.split(".")[0]
        return f"{path}/{ts}.{ext}"
    return key


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

