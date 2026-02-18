"""
hatch-sync: FastAPI API for Hatch Rest devices using the unofficial hatch-rest-api library.
Also syncs Hatch Grow data (diapers, feedings, sleep, weight) to Google Calendar.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.cache import (
    get_cached_grow_data,
    get_cached_login,
    get_cached_photos,
    redis_health,
    set_cached_grow_data,
    set_cached_login,
    set_cached_photos,
)
from app.hatch_service import (
    get_credentials,
    get_device_by_id,
    get_devices,
    set_audio_track,
    set_volume,
)
from app.hatch_grow_service import (
    fetch_diapers,
    fetch_feedings,
    fetch_photos,
    fetch_sleep,
    fetch_weight,
    login as hatch_grow_login,
)
from app.sync import run_sync
from app.photo_store import fetch_and_store_photo, get_photo_bytes, make_photo_key

# Timeout for outbound requests to Hatch API so /grow/data and /grow/photos don't hang
HATCH_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=50, connect=15)

# How often to refresh the grow data cache in the background (keeps page loads fast)
CACHE_REFRESH_INTERVAL_MINUTES = int(os.environ.get("HATCH_CACHE_REFRESH_MINUTES", "15"))

logger = logging.getLogger(__name__)

# Single-flight login: when cache is empty, only one request calls Hatch login; others wait.
# Avoids parallel /grow/data + /grow/photos both logging in and triggering 429.
_login_lock = asyncio.Lock()


async def _get_login_or_fetch(session, email: str, password: str):
    """Return cached login or perform a single login (other waiters reuse result)."""
    login_data = await get_cached_login()
    if login_data:
        return login_data
    async with _login_lock:
        login_data = await get_cached_login()
        if login_data:
            return login_data
        login_data = await hatch_grow_login(session, email, password)
        await set_cached_login(login_data)
        return login_data


async def refresh_grow_cache() -> None:
    """
    Fetch latest grow data from Hatch and update the cache. Runs on a schedule so the cache
    stays warm and page loads are fast; we update the cache with new data instead of
    invalidating and waiting for the next request.
    """
    email = os.environ.get("HATCH_EMAIL", "").strip()
    password = os.environ.get("HATCH_PASSWORD", "").strip()
    if not email or not password:
        return
    try:
        async with aiohttp.ClientSession(timeout=HATCH_HTTP_TIMEOUT) as session:
            login_data = await get_cached_login()
            if not login_data:
                try:
                    login_data = await hatch_grow_login(session, email, password)
                    await set_cached_login(login_data)
                except Exception as e:
                    logger.warning("refresh_grow_cache: login failed: %s", e)
                    return
            babies = login_data.get("payload", {}).get("babies", [])
            if not babies:
                return
            baby_id = babies[0]["id"]
            token = login_data["token"]

            async def safe_fetch(coro, default):
                try:
                    return await coro
                except Exception:
                    return default

            diapers, feedings, sleeps, weights = await asyncio.gather(
                safe_fetch(fetch_diapers(session, token, baby_id), []),
                safe_fetch(fetch_feedings(session, token, baby_id), []),
                safe_fetch(fetch_sleep(session, token, baby_id), []),
                safe_fetch(fetch_weight(session, token, baby_id), []),
            )
            await set_cached_grow_data(
                baby_id,
                {"diapers": diapers, "feedings": feedings, "sleeps": sleeps, "weights": weights},
            )
            logger.info(
                "refresh_grow_cache: updated cache (diapers=%s feedings=%s sleeps=%s weights=%s)",
                len(diapers), len(feedings), len(sleeps), len(weights),
            )
    except asyncio.TimeoutError:
        logger.warning("refresh_grow_cache: Hatch API timed out")
    except Exception as e:
        logger.warning("refresh_grow_cache: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: optional pre-check that credentials are set
    try:
        get_credentials()
    except ValueError:
        pass  # Allow app to run; endpoints will return 503 until .env is set

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_sync, "interval", minutes=15, id="grow_calendar_sync")
    scheduler.add_job(
        refresh_grow_cache,
        "interval",
        minutes=CACHE_REFRESH_INTERVAL_MINUTES,
        id="grow_cache_refresh",
    )
    scheduler.start()
    # Warm cache on startup so first page load is fast
    asyncio.create_task(refresh_grow_cache())
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="hatch-sync",
    description="API for Hatch Rest devices via hatch-rest-api (unofficial)",
    version="0.1.0",
    lifespan=lifespan,
)
# Explicit origins so CORS works with credentials (browsers reject "*" when credentials are true).
# Set CORS_ORIGINS (comma-separated) to add more; default includes GitHub Pages and local dev.
_default_origins = [
    "https://shray7.github.io",
    "http://localhost:5173",
    "http://localhost:8000",
]
_cors_origins = os.environ.get("CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins else _default_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root path for probes and discovery; use /health for health checks."""
    return {"app": "hatch-sync", "health": "/health"}


@app.get("/health")
async def health():
    """Health check, including Redis cache status and whether Hatch env vars are set (no values exposed)."""
    redis_status = await redis_health()
    email = os.environ.get("HATCH_EMAIL", "").strip()
    password = os.environ.get("HATCH_PASSWORD", "").strip()
    hatch_configured = bool(email and password)
    return {
        "status": "ok",
        "redis": redis_status,
        "hatch_configured": hatch_configured,
    }


@app.get("/grow/data")
async def grow_data():
    """Return live Hatch Grow data. Always checks cache first; only calls Hatch API on cache miss."""
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=503, detail="HATCH_EMAIL and HATCH_PASSWORD required")
    try:
        async with aiohttp.ClientSession(timeout=HATCH_HTTP_TIMEOUT) as session:
            # 1. Cache first: login (single-flight so parallel /data + /photos don't both call Hatch)
            try:
                login_data = await _get_login_or_fetch(session, email, password)
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Login failed: {e}")
            babies = login_data.get("payload", {}).get("babies", [])
            if not babies:
                return JSONResponse(
                    content={"babies": [], "feedings": [], "diapers": [], "sleeps": [], "weights": []},
                    headers={"X-Grow-Data-Source": "hatch"},
                )
            baby_id = babies[0]["id"]
            token = login_data["token"]

            # 2. Cache first: grow data (diapers, feedings, sleep, weights)
            cached = await get_cached_grow_data(baby_id)
            if cached and isinstance(cached, dict):
                return JSONResponse(
                    content={
                        "babies": babies,
                        "feedings": cached.get("feedings") or [],
                        "diapers": cached.get("diapers") or [],
                        "sleeps": cached.get("sleeps") or [],
                        "weights": cached.get("weights") or [],
                    },
                    headers={"X-Grow-Data-Source": "cache"},
                )

            # 3. Cache miss: fetch from Hatch then update cache
            async def safe_fetch(coro, default):
                try:
                    return await coro
                except Exception:
                    return default

            diapers, feedings, sleeps, weights = await asyncio.gather(
                safe_fetch(fetch_diapers(session, token, baby_id), []),
                safe_fetch(fetch_feedings(session, token, baby_id), []),
                safe_fetch(fetch_sleep(session, token, baby_id), []),
                safe_fetch(fetch_weight(session, token, baby_id), []),
            )
            asyncio.create_task(
                set_cached_grow_data(
                    baby_id,
                    {"diapers": diapers, "feedings": feedings, "sleeps": sleeps, "weights": weights},
                )
            )
            return JSONResponse(
                content={
                    "babies": babies,
                    "feedings": feedings,
                    "diapers": diapers,
                    "sleeps": sleeps,
                    "weights": weights,
                },
                headers={"X-Grow-Data-Source": "hatch"},
            )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Hatch API timed out; try again in a moment.")


@app.get("/grow/photos")
async def grow_photos():
    """Return daily photos. Always checks cache first; only calls Hatch API on cache miss."""
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=503, detail="HATCH_EMAIL and HATCH_PASSWORD required")
    try:
        async with aiohttp.ClientSession(timeout=HATCH_HTTP_TIMEOUT) as session:
            # 1. Cache first: login (single-flight so parallel /data + /photos don't both call Hatch)
            try:
                login_data = await _get_login_or_fetch(session, email, password)
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Login failed: {e}")
            token = login_data["token"]
            babies = login_data.get("payload", {}).get("babies", [])
            if not babies:
                return JSONResponse(content={"photos": []}, headers={"X-Grow-Data-Source": "hatch"})
            baby_id = babies[0]["id"]

            # 2. Cache first: photos
            cached_photos = await get_cached_photos(baby_id)
            if cached_photos is not None:
                # Augment each photo with a stable internal photoKey for Blob-backed storage
                enriched = []
                for entry in cached_photos:
                    key = make_photo_key(baby_id, entry)
                    enriched.append({**entry, "photoKey": key, "babyId": baby_id})
                return JSONResponse(
                    content={"photos": enriched},
                    headers={"X-Grow-Data-Source": "cache"},
                )

            # 3. Cache miss: fetch from Hatch then update cache
            photos = await fetch_photos(session, token, baby_id)
            asyncio.create_task(set_cached_photos(baby_id, photos))
            enriched = []
            for entry in photos:
                key = make_photo_key(baby_id, entry)
                enriched.append({**entry, "photoKey": key, "babyId": baby_id})
            return JSONResponse(
                content={"photos": enriched},
                headers={"X-Grow-Data-Source": "hatch"},
            )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Hatch API timed out; try again in a moment.")


@app.get("/photos/image")
async def photo_image(baby_id: int, key: str):
    """
    Serve a photo image from Azure Blob Storage by internal key.

    If the blob is missing, fall back to Hatch:
    - Look up the photo in cached /grow/photos data for this baby to get its URL.
    - Download once from Hatch, store in Blob, and stream back to the client.
    """
    # 1. Try Blob first
    data = await get_photo_bytes(key)
    if data is not None:
        return Response(content=data, media_type="image/jpeg")

    # 2. Fallback: try to find the photo URL from cached photos metadata
    cached_photos = await get_cached_photos(baby_id)
    if not cached_photos:
        raise HTTPException(status_code=404, detail="Photo not found")

    entry = None
    for p in cached_photos:
        if make_photo_key(baby_id, p) == key:
            entry = p
            break
    if not entry:
        raise HTTPException(status_code=404, detail="Photo not found")

    url = entry.get("cutDownloadUrl") or entry.get("downloadUrl") or ""
    if not url:
        raise HTTPException(status_code=404, detail="Photo URL not available")

    data = await fetch_and_store_photo(url, key)
    if data is None:
        raise HTTPException(status_code=502, detail="Failed to fetch photo from Hatch")
    return Response(content=data, media_type="image/jpeg")

@app.post("/sync")
async def trigger_sync():
    """Run Hatch Grow → Google Calendar sync once. Returns summary (events_created, errors)."""
    try:
        summary = await run_sync()
        return summary
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/devices")
async def list_devices():
    """List all Hatch Rest devices for the configured account."""
    try:
        devices = await get_devices()
        return {"devices": devices}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/devices/{device_id}")
async def device_detail(device_id: str):
    """Get one device by ID."""
    try:
        device = await get_device_by_id(device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return device
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/devices/{device_id}/volume")
async def device_set_volume(device_id: str, volume: float):
    """Set volume (0.0–1.0)."""
    if not 0 <= volume <= 1:
        raise HTTPException(status_code=400, detail="volume must be between 0 and 1")
    try:
        result = await set_volume(device_id, volume)
        if result is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/devices/{device_id}/audio_track")
async def device_set_audio_track(
    device_id: str,
    track_name: str = Query(..., description="e.g. Ocean, Rain"),
):
    """Set audio track by name (e.g. Ocean, Rain)."""
    try:
        result = await set_audio_track(device_id, track_name)
        if result is None:
            raise HTTPException(status_code=404, detail="Device not found")
        return result
    except ValueError as e:
        msg = str(e)
        if "Unknown audio track" in msg:
            raise HTTPException(status_code=400, detail=msg)
        raise HTTPException(status_code=503, detail=msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
