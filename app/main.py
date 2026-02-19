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

from app.cache import redis_health
from app.db import (
    get_grow_data,
    get_photos as get_photos_from_db,
    get_photos_for_baby_hatch_id,
    init_pool,
    close_pool,
    upsert_baby,
    upsert_diapers,
    upsert_feedings,
    upsert_photos,
    upsert_sleeps,
    upsert_weights,
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
from app.photo_store import (
    fetch_and_store_photo,
    get_photo_bytes,
    make_photo_key,
    normalize_photo_key_for_lookup,
)

# Timeout for outbound requests to Hatch API so /grow/data and /grow/photos don't hang
HATCH_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=50, connect=15)

# How often to refresh the grow data cache in the background (keeps page loads fast)
CACHE_REFRESH_INTERVAL_MINUTES = int(os.environ.get("HATCH_CACHE_REFRESH_MINUTES", "15"))

logger = logging.getLogger(__name__)

async def refresh_grow_cache() -> None:
    """
    Fetch latest grow data from Hatch and upsert into PostgreSQL. Runs on a schedule
    so the database stays up to date; API reads from DB only.
    """
    email = os.environ.get("HATCH_EMAIL", "").strip()
    password = os.environ.get("HATCH_PASSWORD", "").strip()
    if not email or not password:
        return
    try:
        async with aiohttp.ClientSession(timeout=HATCH_HTTP_TIMEOUT) as session:
            try:
                login_data = await hatch_grow_login(session, email, password)
            except Exception as e:
                logger.warning("refresh_grow_cache: login failed: %s", e)
                return
            babies = login_data.get("payload", {}).get("babies", [])
            if not babies:
                return
            token = login_data["token"]

            async def safe_fetch(coro, default):
                try:
                    return await coro
                except Exception:
                    return default

            for baby in babies:
                hatch_baby_id = baby["id"]
                name = baby.get("name") or "Baby"
                birth_date = baby.get("birthDate")
                try:
                    internal_baby_id = await upsert_baby(hatch_baby_id, name, birth_date)
                except RuntimeError:
                    # DB not configured
                    return
                diapers, feedings, sleeps, weights = await asyncio.gather(
                    safe_fetch(fetch_diapers(session, token, hatch_baby_id), []),
                    safe_fetch(fetch_feedings(session, token, hatch_baby_id), []),
                    safe_fetch(fetch_sleep(session, token, hatch_baby_id), []),
                    safe_fetch(fetch_weight(session, token, hatch_baby_id), []),
                )
                await upsert_feedings(internal_baby_id, hatch_baby_id, feedings)
                await upsert_diapers(internal_baby_id, hatch_baby_id, diapers)
                await upsert_sleeps(internal_baby_id, hatch_baby_id, sleeps)
                await upsert_weights(internal_baby_id, hatch_baby_id, weights)
                photos = await safe_fetch(fetch_photos(session, token, hatch_baby_id), [])
                if photos:
                    await upsert_photos(internal_baby_id, hatch_baby_id, photos, make_photo_key)
            logger.info(
                "refresh_grow_cache: updated DB (babies=%s)",
                len(babies),
            )
    except asyncio.TimeoutError:
        logger.warning("refresh_grow_cache: Hatch API timed out")
    except Exception as e:
        logger.warning("refresh_grow_cache: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB pool and run migrations
    await init_pool()
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
    asyncio.create_task(refresh_grow_cache())
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await close_pool()


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
    """Return Hatch Grow data from the database. No Hatch API or Redis; data is updated by background job."""
    content = await get_grow_data()
    if content is None:
        return JSONResponse(
            content={"babies": [], "feedings": [], "diapers": [], "sleeps": [], "weights": []},
            headers={"X-Grow-Data-Source": "db"},
        )
    return JSONResponse(content=content, headers={"X-Grow-Data-Source": "db"})


@app.get("/grow/photos")
async def grow_photos():
    """Return daily photos from the database. No Hatch API or Redis."""
    content = await get_photos_from_db()
    if content is None:
        return JSONResponse(content={"photos": []}, headers={"X-Grow-Data-Source": "db"})
    return JSONResponse(content=content, headers={"X-Grow-Data-Source": "db"})


@app.get("/photos/image")
async def photo_image(baby_id: int, key: str):
    """
    Serve a photo image from Azure Blob Storage by internal key.

    If the blob is missing, look up the photo in the database for this baby to get its
    download URL; download once from Hatch, store in Blob, and stream back.
    """
    key_normalized = normalize_photo_key_for_lookup(key)
    log = logging.getLogger(__name__)

    # 1. Try Blob first (try raw key then normalized key for backwards compatibility)
    data = await get_photo_bytes(key)
    if data is None and key_normalized != key:
        data = await get_photo_bytes(key_normalized)
    if data is not None:
        return Response(content=data, media_type="image/jpeg")

    # 2. Fallback: find photo metadata from DB (baby_id is Hatch baby id)
    photos_list = await get_photos_for_baby_hatch_id(baby_id)
    if not photos_list:
        log.warning("photos/image: no photos in DB for baby_id=%s key=%s", baby_id, key)
        raise HTTPException(status_code=404, detail="Photo not found")

    entry = None
    for p in photos_list:
        p_key = p.get("photoKey") or ""
        if p_key == key or p_key == key_normalized:
            entry = p
            break
    if not entry:
        log.warning(
            "photos/image: no matching photo for baby_id=%s key=%s (tried normalized=%s)",
            baby_id,
            key,
            key_normalized,
        )
        raise HTTPException(status_code=404, detail="Photo not found")

    url = entry.get("cutDownloadUrl") or entry.get("downloadUrl") or ""
    if not url:
        raise HTTPException(status_code=404, detail="Photo URL not available")

    data = await fetch_and_store_photo(url, key_normalized)
    if data is None:
        log.warning("photos/image: failed to fetch from Hatch for baby_id=%s key=%s", baby_id, key)
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
