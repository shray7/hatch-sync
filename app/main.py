"""
hatch-sync: FastAPI API for Hatch Rest devices using the unofficial hatch-rest-api library.
Also syncs Hatch Grow data (diapers, feedings, sleep, weight) to Google Calendar.
"""
import asyncio
import os
from contextlib import asynccontextmanager

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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

# Timeout for outbound requests to Hatch API so /grow/data and /grow/photos don't hang
HATCH_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=50, connect=15)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: optional pre-check that credentials are set
    try:
        get_credentials()
    except ValueError:
        pass  # Allow app to run; endpoints will return 503 until .env is set

    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_sync, "interval", minutes=15, id="grow_calendar_sync")
    scheduler.start()
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
    """Return live Hatch Grow data (babies, feedings, diapers, sleeps, weights). Uses cache when available."""
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=503, detail="HATCH_EMAIL and HATCH_PASSWORD required")
    try:
        async with aiohttp.ClientSession(timeout=HATCH_HTTP_TIMEOUT) as session:
            login_data = await get_cached_login()
            if not login_data:
                try:
                    login_data = await hatch_grow_login(session, email, password)
                except Exception as e:
                    raise HTTPException(status_code=503, detail=f"Login failed: {e}")
                await set_cached_login(login_data)
            babies = login_data.get("payload", {}).get("babies", [])
            if not babies:
                return {"babies": [], "feedings": [], "diapers": [], "sleeps": [], "weights": []}
            baby_id = babies[0]["id"]
            token = login_data["token"]
            cached = await get_cached_grow_data(baby_id)
            if cached and isinstance(cached, dict):
                return {
                    "babies": babies,
                    "feedings": cached.get("feedings") or [],
                    "diapers": cached.get("diapers") or [],
                    "sleeps": cached.get("sleeps") or [],
                    "weights": cached.get("weights") or [],
                }
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
            return {
                "babies": babies,
                "feedings": feedings,
                "diapers": diapers,
                "sleeps": sleeps,
                "weights": weights,
            }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Hatch API timed out; try again in a moment.")


@app.get("/grow/photos")
async def grow_photos():
    """Return daily photos from Hatch Grow (live API). Requires HATCH_EMAIL and HATCH_PASSWORD."""
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=503, detail="HATCH_EMAIL and HATCH_PASSWORD required")
    try:
        async with aiohttp.ClientSession(timeout=HATCH_HTTP_TIMEOUT) as session:
            # Try cached login (token + babies) first
            login_data = await get_cached_login()
            if not login_data:
                try:
                    login_data = await hatch_grow_login(session, email, password)
                except Exception as e:
                    raise HTTPException(status_code=503, detail=f"Login failed: {e}")
                await set_cached_login(login_data)

            token = login_data["token"]
            babies = login_data.get("payload", {}).get("babies", [])
            if not babies:
                return {"photos": []}
            baby_id = babies[0]["id"]
            # Try cached photos for this baby
            cached_photos = await get_cached_photos(baby_id)
            if cached_photos is not None:
                return {"photos": cached_photos}

            photos = await fetch_photos(session, token, baby_id)
            await set_cached_photos(baby_id, photos)
            return {"photos": photos}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Hatch API timed out; try again in a moment.")


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
