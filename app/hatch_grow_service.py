"""
Hatch Baby (Grow) API client — feedings, diapers, sleep, weight.
Uses data.hatchbaby.com; same credentials as Hatch Rest.
"""
from __future__ import annotations

from typing import Any

import aiohttp

API_URL = "https://data.hatchbaby.com"


async def login(session: aiohttp.ClientSession, email: str, password: str) -> dict[str, Any]:
    """Login and return the full response (token, payload with babies, etc.)."""
    url = f"{API_URL}/public/v1/login"
    async with session.post(url, json={"email": email, "password": password}) as resp:
        data = await resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Login failed: {data.get('message')}")
    return data


async def _fetch(
    session: aiohttp.ClientSession, path: str, token: str
) -> dict[str, Any] | None:
    """GET a Hatch API endpoint. Returns payload dict or None on error."""
    url = f"{API_URL}{path}"
    headers = {"X-HatchBaby-Auth": token}
    try:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("payload")
    except Exception:
        pass
    return None


async def fetch_feedings(
    session: aiohttp.ClientSession, token: str, baby_id: int
) -> list[dict[str, Any]]:
    """Fetch feeding records for a baby (excluding deleted)."""
    payload = await _fetch(
        session, f"/service/app/feeding/v2/fetch/{baby_id}", token
    )
    if not payload or "feedings" not in payload:
        return []
    return [f for f in payload["feedings"] if not f.get("deleted")]


async def fetch_diapers(
    session: aiohttp.ClientSession, token: str, baby_id: int
) -> list[dict[str, Any]]:
    """Fetch diaper records for a baby (excluding deleted)."""
    payload = await _fetch(
        session, f"/service/app/diaper/v1/fetch/{baby_id}", token
    )
    if not payload or "diapers" not in payload:
        return []
    return [d for d in payload["diapers"] if not d.get("deleted")]


async def fetch_sleep(
    session: aiohttp.ClientSession, token: str, baby_id: int
) -> list[dict[str, Any]]:
    """Fetch sleep records for a baby."""
    payload = await _fetch(
        session, f"/service/app/sleep/v1/fetch/{baby_id}", token
    )
    if not payload or "sleeps" not in payload:
        return []
    return payload.get("sleeps") or []


async def fetch_weight(
    session: aiohttp.ClientSession, token: str, baby_id: int
) -> list[dict[str, Any]]:
    """Fetch weight records for a baby."""
    payload = await _fetch(
        session, f"/service/app/weight/v1/fetch/{baby_id}", token
    )
    if not payload or "weights" not in payload:
        return []
    return payload.get("weights") or []


async def fetch_photos(
    session: aiohttp.ClientSession, token: str, baby_id: int
) -> list[dict[str, Any]]:
    """Fetch daily photos for a baby. Each photo may include cutDownloadUrl (presigned S3 URL)."""
    payload = await _fetch(
        session, f"/service/app/photo/v1/fetch/{baby_id}", token
    )
    if not payload or "photos" not in payload:
        return []
    return payload.get("photos") or []
