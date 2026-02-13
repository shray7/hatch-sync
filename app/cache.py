"""
Redis-backed cache helpers for Hatch Grow data.

All functions are safe to call when Redis is not configured or unavailable:
operations will behave as cache misses / no-ops and the app falls back to
the existing behavior.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

# Timeout for Redis operations so request handlers never hang when Redis is unreachable
REDIS_OP_TIMEOUT_SECONDS = 3.0

logger = logging.getLogger(__name__)

try:
    from redis.asyncio import from_url as redis_from_url, Redis
except Exception:  # pragma: no cover - redis is optional
    redis_from_url = None
    Redis = Any  # type: ignore


REDIS_URL = os.environ.get("REDIS_URL")

# Default TTLs (can be overridden via env for data/photos)
DEFAULT_DATA_TTL_SECONDS = int(os.environ.get("HATCH_CACHE_TTL_SECONDS", "900"))
DEFAULT_LOGIN_TTL_SECONDS = 50 * 60  # 50 minutes

_redis: Optional[Redis] = None
_cache_enabled: bool = False


if REDIS_URL and redis_from_url is not None:
    try:
        # decode_responses=True so we work with str instead of bytes
        _redis = redis_from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        _cache_enabled = True
    except Exception as exc:  # pragma: no cover - connection only happens on first use
        logger.warning("Redis disabled due to connection error: %s", exc)
        _redis = None
        _cache_enabled = False
else:
    if not REDIS_URL:
        logger.info("REDIS_URL not set; Redis cache is disabled.")
    else:
        logger.info("redis package not available; Redis cache is disabled.")


async def _get(key: str) -> Optional[str]:
    """Low-level GET. Returns None on any error, timeout, or when cache is disabled."""
    if not _cache_enabled or _redis is None:
        return None
    try:
        return await asyncio.wait_for(_redis.get(key), timeout=REDIS_OP_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.debug("Redis GET %s timed out", key)
        return None
    except Exception as exc:  # pragma: no cover - network / runtime issues
        logger.debug("Redis GET %s failed: %s", key, exc)
        return None


async def _set(key: str, value: str, ttl_seconds: int) -> None:
    """Low-level SET with TTL. No-ops on error, timeout, or when cache is disabled."""
    if not _cache_enabled or _redis is None:
        return
    try:
        await asyncio.wait_for(_redis.set(key, value, ex=ttl_seconds), timeout=REDIS_OP_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.debug("Redis SET %s timed out", key)
    except Exception as exc:  # pragma: no cover - network / runtime issues
        logger.debug("Redis SET %s failed: %s", key, exc)


async def get_cached(key: str) -> Optional[str]:
    """Get a raw string value from cache."""
    return await _get(key)


async def set_cached(key: str, value: str, ttl_seconds: int) -> None:
    """Set a raw string value in cache."""
    await _set(key, value, ttl_seconds)


async def get_cached_json(key: str) -> Any:
    """Get a JSON-encoded value from cache."""
    raw = await _get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        # Treat decode errors as cache misses
        logger.debug("Failed to decode JSON from Redis key %s", key)
        return None


async def set_cached_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Set a JSON-encodable value in cache."""
    try:
        raw = json.dumps(value)
    except Exception as exc:
        logger.debug("Failed to JSON-encode value for key %s: %s", key, exc)
        return
    await _set(key, raw, ttl_seconds)


def _login_key() -> str:
    return "hatch:login"


def _grow_data_key(baby_id: int | str) -> str:
    return f"hatch:grow:{baby_id}:data"


def _photos_key(baby_id: int | str) -> str:
    return f"hatch:grow:{baby_id}:photos"


async def get_cached_login() -> Optional[dict[str, Any]]:
    """Return cached login data (token + babies) if present."""
    data = await get_cached_json(_login_key())
    if isinstance(data, dict):
        return data
    return None


async def set_cached_login(login_data: dict[str, Any], ttl_seconds: int | None = None) -> None:
    """Cache login data (token + babies)."""
    ttl = ttl_seconds or DEFAULT_LOGIN_TTL_SECONDS
    await set_cached_json(_login_key(), login_data, ttl)


async def get_cached_grow_data(baby_id: int | str) -> Optional[dict[str, Any]]:
    """Return cached Grow data bundle for a baby."""
    data = await get_cached_json(_grow_data_key(baby_id))
    if isinstance(data, dict):
        return data
    return None


async def set_cached_grow_data(
    baby_id: int | str,
    data: dict[str, Any],
    ttl_seconds: int | None = None,
) -> None:
    """Cache Grow data bundle for a baby."""
    ttl = ttl_seconds or DEFAULT_DATA_TTL_SECONDS
    await set_cached_json(_grow_data_key(baby_id), data, ttl)


async def get_cached_photos(baby_id: int | str) -> Optional[list[dict[str, Any]]]:
    """Return cached photos for a baby, if present."""
    data = await get_cached_json(_photos_key(baby_id))
    if isinstance(data, list):
        return data
    return None


async def set_cached_photos(
    baby_id: int | str,
    photos: list[dict[str, Any]],
    ttl_seconds: int | None = None,
) -> None:
    """Cache photos list for a baby."""
    ttl = ttl_seconds or DEFAULT_DATA_TTL_SECONDS
    await set_cached_json(_photos_key(baby_id), photos, ttl)


async def redis_health() -> str:
    """
    Lightweight health indicator for Redis.

    Returns:
        - "disabled" if Redis is not configured or client unavailable.
        - "ok" if a PING succeeds.
        - "unavailable" if a PING fails or times out (so /health never hangs).
    """
    if not _cache_enabled or _redis is None:
        return "disabled"
    try:
        await asyncio.wait_for(_redis.ping(), timeout=REDIS_OP_TIMEOUT_SECONDS)
        return "ok"
    except asyncio.TimeoutError:
        logger.debug("Redis PING timed out")
        return "unavailable"
    except Exception:
        return "unavailable"

