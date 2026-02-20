"""
hatch-sync: FastAPI API for Hatch Rest devices using the unofficial hatch-rest-api library.
Also syncs Hatch Grow data (diapers, feedings, weight) to Google Calendar.
"""
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel

from fastapi import Depends, File, FastAPI, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth import (
    build_google_auth_url,
    clear_session_response,
    exchange_code_for_tokens,
    get_allowlist_emails,
    get_google_client_config,
    get_session_email,
    refresh_access_token,
    set_session_response,
    verify_google_id_token,
)
from app.cache import redis_health
from app.azure_blob import upload_blob
from app.db import (
    get_first_baby,
    get_google_refresh_token,
    get_grow_data,
    get_photos as get_photos_from_db,
    get_photos_for_baby_hatch_id,
    init_pool,
    close_pool,
    insert_uploaded_photo,
    upsert_baby,
    upsert_diapers,
    upsert_feedings,
    upsert_google_refresh_token,
    upsert_photos,
    upsert_weights,
)
from app.hatch_service import (
    get_credentials,
    get_device_by_id,
    get_devices,
    set_audio_track,
    set_volume,
)
from app.google_photos import (
    batch_get_media_items,
    download_media_bytes,
    get_download_url,
    list_media_items,
)
from app.hatch_grow_service import (
    fetch_diapers,
    fetch_feedings,
    fetch_photos,
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

# Extension -> (content_type, media_type) for uploads
_UPLOAD_CONTENT_TYPES = {
    ".jpg": ("image/jpeg", "photo"),
    ".jpeg": ("image/jpeg", "photo"),
    ".png": ("image/png", "photo"),
    ".heic": ("image/heic", "photo"),
    ".gif": ("image/gif", "photo"),
    ".webp": ("image/webp", "photo"),
    ".mp4": ("video/mp4", "video"),
    ".mov": ("video/quicktime", "video"),
    ".webm": ("video/webm", "video"),
}


def _content_type_from_key(key: str) -> tuple[str, str]:
    """Return (content_type, media_type) from blob key extension. Default image/jpeg, photo."""
    ext = ""
    for e in _UPLOAD_CONTENT_TYPES:
        if key.lower().endswith(e):
            ext = e
            break
    if not ext:
        # try generic extension
        if "." in key:
            ext = "." + key.rsplit(".", 1)[-1].lower()
    return _UPLOAD_CONTENT_TYPES.get(ext, ("image/jpeg", "photo"))

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
                diapers, feedings, weights = await asyncio.gather(
                    safe_fetch(fetch_diapers(session, token, hatch_baby_id), []),
                    safe_fetch(fetch_feedings(session, token, hatch_baby_id), []),
                    safe_fetch(fetch_weight(session, token, hatch_baby_id), []),
                )
                await upsert_feedings(internal_baby_id, hatch_baby_id, feedings)
                await upsert_diapers(internal_baby_id, hatch_baby_id, diapers)
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
    Serve a photo or video from Azure Blob Storage by internal key.

    If the blob is missing, look up the photo in the database for this baby to get its
    download URL; download once from Hatch, store in Blob, and stream back.
    Content-Type is set from key extension (e.g. video/mp4 for .mp4). Videos get Accept-Ranges.
    """
    key_normalized = normalize_photo_key_for_lookup(key)
    log = logging.getLogger(__name__)

    # 1. Try Blob first (try raw key then normalized key for backwards compatibility)
    data = await get_photo_bytes(key)
    if data is None and key_normalized != key:
        data = await get_photo_bytes(key_normalized)
    if data is not None:
        content_type, media_type = _content_type_from_key(key)
        headers = {}
        if media_type == "video":
            headers["Accept-Ranges"] = "bytes"
        return Response(content=data, media_type=content_type, headers=headers)

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
    content_type, _ = _content_type_from_key(key)
    return Response(content=data, media_type=content_type)

def require_admin(request: Request) -> str:
    """Dependency: return admin email or raise 401/403."""
    return get_session_email(request)


def _oauth_redirect_base(request: Request) -> str:
    """Base URL for OAuth redirect_uri. Prefer API_BASE_URL; else request URL forced to https when not localhost (e.g. behind Azure TLS termination)."""
    base = os.environ.get("API_BASE_URL", "").strip()
    if base:
        return base.rstrip("/")
    url = str(request.base_url).rstrip("/")
    parsed = urlparse(url)
    if parsed.scheme == "http" and "localhost" not in (parsed.hostname or "") and parsed.hostname != "127.0.0.1":
        return f"https://{parsed.hostname or parsed.netloc}"
    return url


@app.get("/auth/config")
async def auth_config():
    """Return public auth config (e.g. Google OAuth client_id for frontend Picker). No secrets."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    return {"google_client_id": client_id or ""}


@app.get("/auth/google")
async def auth_google(request: Request, next_url: str = Query("", alias="next")):
    """Redirect to Google OAuth. Optional 'next' is passed through state to redirect after login."""
    try:
        # redirect_uri must be the backend callback URL (https in production)
        base = _oauth_redirect_base(request)
        redirect_uri = f"{base}/auth/callback"
        state = next_url if next_url else ""
        url = build_google_auth_url(redirect_uri, state=state or None)
        return RedirectResponse(url=url)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(""),
):
    """Exchange code for tokens, verify, set session cookie, redirect to frontend."""
    base = _oauth_redirect_base(request)
    redirect_uri = f"{base}/auth/callback"
    try:
        tokens = await exchange_code_for_tokens(code, redirect_uri)
    except Exception as e:
        logger.exception("auth_callback: token exchange failed")
        raise HTTPException(status_code=400, detail="Token exchange failed")
    id_token_str = tokens.get("id_token")
    if not id_token_str:
        raise HTTPException(status_code=400, detail="No id_token in response")
    try:
        client_id, _ = get_google_client_config()
        claims = verify_google_id_token(id_token_str, client_id)
    except Exception as e:
        logger.warning("auth_callback: invalid id_token: %s", e)
        raise HTTPException(status_code=400, detail="Invalid token")
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="No email in token")
    allowlist = get_allowlist_emails()
    if not allowlist or email not in allowlist:
        raise HTTPException(status_code=403, detail="Not in admin allowlist")
    if tokens.get("refresh_token"):
        await upsert_google_refresh_token(email, tokens["refresh_token"])
    frontend_base = os.environ.get("FRONTEND_URL", "https://shray7.github.io/hatch-sync").rstrip("/")
    path = (state.strip() or "/admin")
    if not path.startswith("/"):
        path = "/" + path
    redirect_to = f"{frontend_base}{path}"
    redirect_response = RedirectResponse(url=redirect_to, status_code=302)
    # Attach session cookie to the redirect response so the browser stores it.
    set_session_response(redirect_response, email)
    return redirect_response


@app.get("/auth/me")
async def auth_me(request: Request):
    """Return current user email if session valid (for admin UI)."""
    email = get_session_email(request)
    return {"email": email}


@app.post("/auth/logout")
async def auth_logout(response: Response):
    """Clear session cookie."""
    clear_session_response(response)
    return {"ok": True}


async def _process_uploaded_files(files: list[UploadFile], source: str) -> int:
    """Process multipart files and store in blob + DB. Returns count uploaded."""
    baby = await get_first_baby()
    if not baby:
        raise HTTPException(status_code=503, detail="No baby in database; add Hatch credentials and run sync first.")
    internal_id, hatch_id = baby
    uploaded = 0
    for uf in files:
        if not uf.filename:
            continue
        ext = "." + uf.filename.rsplit(".", 1)[-1].lower() if "." in uf.filename else ".jpg"
        content_type, media_type = _UPLOAD_CONTENT_TYPES.get(ext, ("application/octet-stream", "photo"))
        key = f"baby/{hatch_id}/uploads/{uuid.uuid4().hex}{ext}"
        try:
            data = await uf.read()
            if not data:
                continue
            await upload_blob(key, data, content_type=content_type)
            await insert_uploaded_photo(
                internal_id,
                key,
                datetime.now(timezone.utc),
                source=source,
                media_type=media_type,
            )
            uploaded += 1
        except Exception as e:
            logger.warning("upload: failed %s: %s", uf.filename, e)
    return uploaded


@app.post("/admin/upload")
async def admin_upload(
    _: str = Depends(require_admin),
    files: list[UploadFile] = File(...),
):
    """Upload one or more photos/videos from device. Admin only."""
    uploaded = await _process_uploaded_files(files, "device")
    return {"uploaded": uploaded}


@app.post("/admin/upload-companion")
async def admin_upload_companion(
    request: Request,
    files: list[UploadFile] = File(...),
):
    """Accept uploads from Uppy Companion (Google Photos Picker). Requires X-Companion-Secret header."""
    secret = os.environ.get("COMPANION_UPLOAD_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Companion upload not configured")
    if request.headers.get("X-Companion-Secret") != secret:
        raise HTTPException(status_code=403, detail="Invalid or missing Companion secret")
    n = await _process_uploaded_files(files, "google_photos")
    return {"uploaded": n}


class GooglePhotosImportBody(BaseModel):
    media_item_ids: list[str]


@app.get("/admin/google-photos/list")
async def admin_google_photos_list(
    email: str = Depends(require_admin),
    page_size: int = Query(50, le=100),
    page_token: Optional[str] = Query(None),
):
    """List media items from the user's Google Photos library. Admin only."""
    refresh = await get_google_refresh_token(email)
    if not refresh:
        raise HTTPException(
            status_code=400,
            detail="No Google Photos access. Sign out and sign in again with Google to grant access.",
        )
    try:
        access = await refresh_access_token(refresh)
    except Exception as e:
        logger.warning("admin_google_photos_list: refresh failed: %s", e)
        raise HTTPException(status_code=503, detail="Could not get Google access token")
    try:
        data = await list_media_items(access, page_size=page_size, page_token=page_token)
        return data
    except httpx.HTTPStatusError as e:
        # Surface the underlying Google Photos error message to the client.
        detail = str(e)
        try:
            err_json = e.response.json()
            detail = err_json.get("error", {}).get("message") or detail
        except Exception:
            pass
        logger.warning("admin_google_photos_list: Google Photos API failed: %s", detail)
        raise HTTPException(status_code=e.response.status_code, detail=f"Google Photos API error: {detail}")
    except Exception as e:
        logger.warning("admin_google_photos_list: API failed: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/admin/google-photos/import")
async def admin_google_photos_import(
    body: GooglePhotosImportBody,
    email: str = Depends(require_admin),
):
    """Import selected media items from Google Photos into the baby timeline. Admin only."""
    if not body.media_item_ids:
        return {"imported": 0}
    baby = await get_first_baby()
    if not baby:
        raise HTTPException(status_code=503, detail="No baby in database.")
    internal_id, hatch_id = baby
    refresh = await get_google_refresh_token(email)
    if not refresh:
        raise HTTPException(status_code=400, detail="No Google Photos access. Sign in again with Google.")
    try:
        access = await refresh_access_token(refresh)
    except Exception as e:
        raise HTTPException(status_code=503, detail="Could not get Google access token")
    items = await batch_get_media_items(access, body.media_item_ids)
    imported = 0
    for item in items:
        mid = item.get("id")
        base_url = item.get("baseUrl")
        mime = item.get("mimeType") or ""
        filename = item.get("filename") or "import"
        if not base_url:
            continue
        url = get_download_url(base_url, mime)
        data = await download_media_bytes(url)
        if not data:
            continue
        ext = ".jpg"
        if "video" in mime.lower():
            ext = ".mp4" if "mp4" in mime.lower() else ".mov"
        else:
            if "png" in mime.lower():
                ext = ".png"
            elif "gif" in mime.lower():
                ext = ".gif"
            elif "webp" in mime.lower():
                ext = ".webp"
        key = f"baby/{hatch_id}/uploads/{uuid.uuid4().hex}{ext}"
        content_type = mime if mime else "image/jpeg"
        media_type = "video" if "video" in mime.lower() else "photo"
        try:
            await upload_blob(key, data, content_type=content_type)
            creation = item.get("mediaMetadata", {}).get("creationTime")
            create_dt = datetime.now(timezone.utc)
            if creation:
                try:
                    # Google returns ISO format e.g. 2024-01-15T12:00:00Z
                    ts = creation.replace("Z", "+00:00")
                    create_dt = datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    pass
            await insert_uploaded_photo(
                internal_id,
                key,
                create_dt,
                source="google_photos",
                media_type=media_type,
            )
            imported += 1
        except Exception as e:
            logger.warning("admin_google_photos_import: failed %s: %s", mid, e)
    return {"imported": imported}


@app.post("/sync")
async def trigger_sync(_: str = Depends(require_admin)):
    """Run Hatch Grow → Google Calendar sync once. Returns summary (events_created, errors). Admin only."""
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
