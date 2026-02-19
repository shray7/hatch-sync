"""
Hatch Baby (Grow) API client — feedings, diapers, sleep, weight.
Uses data.hatchbaby.com; same credentials as Hatch Rest.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

API_URL = "https://data.hatchbaby.com"

# On 429 we retry once after this delay (or Retry-After if present, capped)
RATE_LIMIT_RETRY_DELAY_MIN = 30
RATE_LIMIT_RETRY_DELAY_MAX = 120


async def login(session: aiohttp.ClientSession, email: str, password: str) -> dict[str, Any]:
    """Login and return the full response (token, payload with babies, etc.).
    On 429 rate limit, retries once after a short backoff (or Retry-After if provided).
    """
    url = f"{API_URL}/public/v1/login"
    payload = {"email": email, "password": password}

    async def do_login() -> tuple[dict[str, Any] | None, int | None]:
        async with session.post(url, json=payload) as resp:
            if resp.status == 429:
                retry_after: int | None = None
                try:
                    ra = resp.headers.get("Retry-After")
                    if ra is not None:
                        retry_after = int(ra)
                except ValueError:
                    pass
                return None, retry_after
            text = await resp.text()
            if "application/json" not in (resp.content_type or ""):
                raise RuntimeError(
                    f"Hatch returned {resp.status} ({resp.content_type}); try again later."
                )
            try:
                data = json.loads(text)
            except ValueError:
                raise RuntimeError(f"Hatch returned non-JSON (status {resp.status}); try again later.")
            if data.get("status") != "success":
                raise RuntimeError(f"Login failed: {data.get('message', 'unknown')}")
            return data, None

    data, retry_after = await do_login()
    if data is not None:
        return data

    # 429: wait then retry once
    delay = retry_after if retry_after is not None else 60
    delay = max(RATE_LIMIT_RETRY_DELAY_MIN, min(RATE_LIMIT_RETRY_DELAY_MAX, delay))
    await asyncio.sleep(delay)
    data, _ = await do_login()
    if data is not None:
        return data
    raise RuntimeError("Hatch rate limit (429); try again in a few minutes.")


async def _fetch(
    session: aiohttp.ClientSession, path: str, token: str
) -> dict[str, Any] | None:
    """GET a Hatch API endpoint. Returns payload dict or None on error."""
    url = f"{API_URL}{path}"
    headers = {"X-HatchBaby-Auth": token}
    try:
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            if "application/json" in (resp.content_type or ""):
                try:
                    data = json.loads(text)
                    if data.get("status") == "success":
                        return data.get("payload")
                except ValueError:
                    pass
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
