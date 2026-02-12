"""
hatch-sync: FastAPI API for Hatch Rest devices using the unofficial hatch-rest-api library.
Also syncs Hatch Grow data (diapers, feedings, sleep, weight) to Google Calendar.
"""
import os
from contextlib import asynccontextmanager

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.cache import (
    get_cached_login,
    get_cached_photos,
    redis_health,
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
from app.hatch_grow_service import fetch_photos, login as hatch_grow_login
from app.seed_data import get_seed_grow_data
from app.sync import run_sync


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check, including Redis cache status if configured."""
    redis_status = await redis_health()
    return {"status": "ok", "redis": redis_status}


@app.get("/grow/data")
async def grow_data():
    """Return seeded Hatch Grow-style data (babies, feedings, diapers, sleeps, weights)."""
    # For now this always returns local seed data. Later this can switch to live Hatch API
    # via app.hatch_grow_service while keeping the same response shape.
    return get_seed_grow_data()


@app.get("/grow/photos")
async def grow_photos():
    """Return daily photos from Hatch Grow (live API). Requires HATCH_EMAIL and HATCH_PASSWORD."""
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=503, detail="HATCH_EMAIL and HATCH_PASSWORD required")
    async with aiohttp.ClientSession() as session:
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
