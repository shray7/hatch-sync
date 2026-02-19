"""
Google Photos Library API helpers: list and download media for import.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PHOTOS_API_BASE = "https://photoslibrary.googleapis.com/v1"


async def list_media_items(access_token: str, page_size: int = 50, page_token: str | None = None) -> dict[str, Any]:
    """
    Search (list) media items in the user's library. Returns dict with mediaItems list and nextPageToken.
    """
    body: dict[str, Any] = {"pageSize": min(page_size, 100)}
    if page_token:
        body["pageToken"] = page_token
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{PHOTOS_API_BASE}/mediaItems:search",
            json=body,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        )
    resp.raise_for_status()
    return resp.json()


async def batch_get_media_items(access_token: str, media_item_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch multiple media items by ID. Returns list of media item dicts (or skips errors)."""
    if not media_item_ids:
        return []
    # API allows up to 50 per request
    ids = media_item_ids[:50]
    params = "&".join(f"mediaItemIds={id}" for id in ids)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{PHOTOS_API_BASE}/mediaItems:batchGet?{params}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    resp.raise_for_status()
    data = resp.json()
    results = []
    for r in data.get("mediaItemResults", []):
        if "mediaItem" in r:
            results.append(r["mediaItem"])
        # else status/error - skip
    return results


def get_download_url(base_url: str, mime_type: str) -> str:
    """Append the correct parameter to baseUrl for downloading. Image: =d, video: =dv."""
    base = (base_url or "").strip()
    if not base:
        return ""
    if "video" in (mime_type or "").lower():
        return base + "=dv"
    return base + "=d"


async def download_media_bytes(url: str) -> bytes | None:
    """Download bytes from a Google Photos baseUrl (with =d or =dv appended)."""
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.warning("download_media_bytes failed: %s", e)
        return None
