"""
PostgreSQL layer for Hatch Grow data. Uses asyncpg; migrations run from
migrations/001_initial.sql. Set DATABASE_URL in the environment.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from app.hatch_time import format_hatch_dt, hatch_time_to_utc, parse_hatch_dt

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
_pool: Optional[Any] = None


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "migrations"


async def get_pool():
    """Return the global asyncpg pool; raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized; call init_pool() in lifespan first.")
    return _pool


async def init_pool() -> None:
    """Create connection pool and run migrations. No-op if DATABASE_URL is unset."""
    global _pool
    if not DATABASE_URL:
        logger.info("DATABASE_URL not set; database layer disabled.")
        return
    try:
        import asyncpg
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        await run_migrations()
    except Exception as e:
        logger.warning("Database pool init failed: %s", e)
        _pool = None


async def close_pool() -> None:
    """Close the global pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _parse_sql_statements(sql: str) -> list[str]:
    """Split SQL into executable statements (by semicolon), stripping comments and blanks."""
    statements = []
    for part in sql.split(";"):
        lines = [
            L.strip() for L in part.splitlines()
            if L.strip() and not L.strip().startswith("--")
        ]
        stmt = " ".join(lines).strip()
        if stmt:
            statements.append(stmt + ";")
    return statements


async def run_migrations() -> None:
    """Run all SQL files in migrations/ in sorted order. Executes each statement separately."""
    if not _pool:
        return
    mig_dir = _migrations_dir()
    if not mig_dir.exists():
        return
    paths = sorted(mig_dir.glob("*.sql"))
    async with _pool.acquire() as conn:
        for path in paths:
            sql = path.read_text()
            statements = _parse_sql_statements(sql)
            for stmt in statements:
                await conn.execute(stmt)
            logger.info("Ran migrations from %s", path.name)


def _dt(s: str):
    """Parse Hatch string to UTC for DB storage."""
    return hatch_time_to_utc(parse_hatch_dt(s))


# --- Upserts (from Hatch API dicts) ---


async def upsert_baby(hatch_id: int, name: str, birth_date: Optional[str] = None) -> int:
    """Insert or update baby by hatch_id; return internal id."""
    pool = await get_pool()
    birth = None
    if birth_date:
        try:
            from datetime import datetime
            birth = datetime.strptime(birth_date[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO babies (hatch_id, name, birth_date, updated_at)
            VALUES ($1, $2, $3, now())
            ON CONFLICT (hatch_id) DO UPDATE SET
                name = EXCLUDED.name,
                birth_date = EXCLUDED.birth_date,
                updated_at = now()
            RETURNING id
            """,
            hatch_id,
            name or None,
            birth,
        )
        return row["id"]


async def upsert_feedings(baby_id: int, hatch_baby_id: int, items: list[dict]) -> None:
    """Upsert feeding records by hatch_id."""
    if not items:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        for d in items:
            hid = d.get("id")
            if hid is None:
                continue
            start = _dt(d.get("startTime") or d.get("createDate") or "")
            end = _dt(d.get("endTime") or "") if d.get("endTime") else start
            await conn.execute(
                """
                INSERT INTO feedings (
                    baby_id, hatch_id, start_time, end_time, amount, duration_seconds,
                    method, source, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $3, $4)
                ON CONFLICT (hatch_id) DO UPDATE SET
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    amount = EXCLUDED.amount,
                    duration_seconds = EXCLUDED.duration_seconds,
                    method = EXCLUDED.method,
                    source = EXCLUDED.source,
                    updated_at = now()
                """,
                baby_id,
                hid,
                start,
                end,
                d.get("amount"),
                d.get("durationInSeconds"),
                d.get("method") or None,
                d.get("source") or None,
            )


async def upsert_diapers(baby_id: int, hatch_baby_id: int, items: list[dict]) -> None:
    if not items:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        for d in items:
            hid = d.get("id")
            if hid is None:
                continue
            dt = _dt(d.get("diaperDate") or d.get("createDate") or "")
            await conn.execute(
                """
                INSERT INTO diapers (baby_id, hatch_id, diaper_date, diaper_type, details, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $3, $3)
                ON CONFLICT (hatch_id) DO UPDATE SET
                    diaper_date = EXCLUDED.diaper_date,
                    diaper_type = EXCLUDED.diaper_type,
                    details = EXCLUDED.details,
                    updated_at = now()
                """,
                baby_id,
                hid,
                dt,
                d.get("diaperType") or None,
                d.get("details") or None,
            )


async def upsert_weights(baby_id: int, hatch_baby_id: int, items: list[dict]) -> None:
    if not items:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        for d in items:
            hid = d.get("id")
            if hid is None:
                continue
            w = d.get("weight") or d.get("weightInGrams")
            if w is None:
                continue
            dt = _dt(d.get("weightDate") or d.get("createDate") or "")
            await conn.execute(
                """
                INSERT INTO weights (baby_id, hatch_id, weight_grams, weight_date, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $4, $4)
                ON CONFLICT (hatch_id) DO UPDATE SET
                    weight_grams = EXCLUDED.weight_grams,
                    weight_date = EXCLUDED.weight_date,
                    updated_at = now()
                """,
                baby_id,
                hid,
                float(w),
                dt,
            )


async def upsert_photos(baby_id: int, hatch_baby_id: int, items: list[dict], make_photo_key) -> None:
    """Upsert photo metadata; make_photo_key(baby_id, entry) -> photo_key."""
    if not items:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        for d in items:
            key = make_photo_key(hatch_baby_id, d)
            create_dt = _dt(d.get("createDate") or d.get("weightDate") or "")
            url = d.get("cutDownloadUrl") or d.get("downloadUrl") or None
            await conn.execute(
                """
                INSERT INTO photos (baby_id, photo_key, create_date, hatch_download_url, source, media_type, created_at)
                VALUES ($1, $2, $3, $4, 'hatch', 'photo', now())
                ON CONFLICT (photo_key) DO UPDATE SET
                    create_date = EXCLUDED.create_date,
                    hatch_download_url = COALESCE(EXCLUDED.hatch_download_url, photos.hatch_download_url)
                """,
                baby_id,
                key,
                create_dt,
                url,
            )


async def upsert_google_refresh_token(email: str, refresh_token: str) -> None:
    """Store or update Google refresh token for the given admin email."""
    if not _pool:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_google_tokens (email, refresh_token, updated_at)
                VALUES ($1, $2, now())
                ON CONFLICT (email) DO UPDATE SET
                    refresh_token = EXCLUDED.refresh_token,
                    updated_at = now()
                """,
                email.strip().lower(),
                refresh_token,
            )
    except Exception as e:
        logger.warning("upsert_google_refresh_token failed: %s", e)


async def get_google_refresh_token(email: str) -> Optional[str]:
    """Return stored refresh token for the email, or None."""
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT refresh_token FROM user_google_tokens WHERE email = $1",
                email.strip().lower(),
            )
            return row["refresh_token"] if row else None
    except Exception as e:
        logger.warning("get_google_refresh_token failed: %s", e)
        return None


async def get_first_baby() -> Optional[tuple[int, int]]:
    """Return (internal_id, hatch_id) for the first baby, or None."""
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id, hatch_id FROM babies ORDER BY id LIMIT 1")
            if not row:
                return None
            return (row["id"], row["hatch_id"])
    except Exception as e:
        logger.warning("get_first_baby failed: %s", e)
        return None


async def insert_uploaded_photo(
    baby_id: int,
    photo_key: str,
    create_date: Any,
    source: str = "device",
    media_type: str = "photo",
) -> None:
    """Insert one uploaded photo/video row (source=device or google_photos). create_date is timezone-aware datetime."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO photos (baby_id, photo_key, create_date, hatch_download_url, source, media_type, created_at)
            VALUES ($1, $2, $3, NULL, $4, $5, now())
            ON CONFLICT (photo_key) DO NOTHING
            """,
            baby_id,
            photo_key,
            create_date,
            source,
            media_type,
        )


# --- API-shaped reads (for /grow/data and /grow/photos) ---


def _row_baby(r) -> dict:
    return {
        "id": r["hatch_id"],
        "name": r["name"] or "",
        "birthDate": r["birth_date"].isoformat() if r["birth_date"] else None,
    }


def _row_feeding(r, hatch_baby_id: int) -> dict:
    return {
        "id": r["hatch_id"],
        "babyId": hatch_baby_id,
        "startTime": format_hatch_dt(r["start_time"]),
        "endTime": format_hatch_dt(r["end_time"]),
        "amount": float(r["amount"]) if r["amount"] is not None else None,
        "durationInSeconds": r["duration_seconds"],
        "method": r["method"] or "",
        "source": r["source"] or "",
        "createDate": format_hatch_dt(r["created_at"]),
        "updateDate": format_hatch_dt(r["updated_at"]),
    }


def _row_diaper(r, hatch_baby_id: int) -> dict:
    return {
        "id": r["hatch_id"],
        "babyId": hatch_baby_id,
        "diaperDate": format_hatch_dt(r["diaper_date"]),
        "diaperType": r["diaper_type"] or "",
        "details": r["details"] or "",
        "createDate": format_hatch_dt(r["created_at"]),
        "updateDate": format_hatch_dt(r["updated_at"]),
    }


def _row_weight(r, hatch_baby_id: int) -> dict:
    return {
        "id": r["hatch_id"],
        "babyId": hatch_baby_id,
        "weight": float(r["weight_grams"]) if r["weight_grams"] is not None else None,
        "weightDate": format_hatch_dt(r["weight_date"]),
        "createDate": format_hatch_dt(r["created_at"]),
        "updateDate": format_hatch_dt(r["updated_at"]),
    }


def _row_photo(r, hatch_baby_id: int) -> dict:
    return {
        "photoKey": r["photo_key"],
        "babyId": hatch_baby_id,
        "createDate": format_hatch_dt(r["create_date"]),
        "cutDownloadUrl": r["hatch_download_url"],
        "downloadUrl": r["hatch_download_url"],
        "source": r.get("source") or "hatch",
        "mediaType": r.get("media_type") or "photo",
    }


async def get_grow_data() -> Optional[dict[str, Any]]:
    """
    Return { babies, feedings, diapers, sleeps, weights } in API shape.
    Uses first baby (by id) for feedings/diapers/weights. Returns None if DB not configured or empty.
    """
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            babies_rows = await conn.fetch("SELECT id, hatch_id, name, birth_date FROM babies ORDER BY id")
            if not babies_rows:
                return {"babies": [], "feedings": [], "diapers": [], "sleeps": [], "weights": []}
            babies = [_row_baby(r) for r in babies_rows]
            first_baby_id = babies_rows[0]["id"]
            hatch_baby_id = babies_rows[0]["hatch_id"]

            feedings = await conn.fetch(
                "SELECT hatch_id, start_time, end_time, amount, duration_seconds, method, source, created_at, updated_at FROM feedings WHERE baby_id = $1 ORDER BY start_time",
                first_baby_id,
            )
            diapers = await conn.fetch(
                "SELECT hatch_id, diaper_date, diaper_type, details, created_at, updated_at FROM diapers WHERE baby_id = $1 ORDER BY diaper_date",
                first_baby_id,
            )
            weights = await conn.fetch(
                "SELECT hatch_id, weight_grams, weight_date, created_at, updated_at FROM weights WHERE baby_id = $1 ORDER BY weight_date",
                first_baby_id,
            )
            return {
                "babies": babies,
                "feedings": [_row_feeding(r, hatch_baby_id) for r in feedings],
                "diapers": [_row_diaper(r, hatch_baby_id) for r in diapers],
                "sleeps": [],
                "weights": [_row_weight(r, hatch_baby_id) for r in weights],
            }
    except Exception as e:
        logger.warning("get_grow_data failed: %s", e)
        return None


async def get_photos() -> Optional[dict[str, Any]]:
    """Return { photos } in API shape (photoKey, babyId, createDate, ...). Uses first baby."""
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            first = await conn.fetchrow("SELECT id, hatch_id FROM babies ORDER BY id LIMIT 1")
            if not first:
                return {"photos": []}
            baby_id = first["id"]
            hatch_baby_id = first["hatch_id"]
            rows = await conn.fetch(
                "SELECT photo_key, create_date, hatch_download_url, source, media_type FROM photos WHERE baby_id = $1 ORDER BY create_date",
                baby_id,
            )
            return {"photos": [_row_photo(r, hatch_baby_id) for r in rows]}
    except Exception as e:
        logger.warning("get_photos failed: %s", e)
        return None


async def get_photos_for_baby_hatch_id(hatch_baby_id: int) -> Optional[list[dict]]:
    """Return list of photo dicts with photoKey, babyId, cutDownloadUrl, downloadUrl for /photos/image fallback."""
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            baby = await conn.fetchrow("SELECT id FROM babies WHERE hatch_id = $1", hatch_baby_id)
            if not baby:
                return None
            rows = await conn.fetch(
                "SELECT photo_key, create_date, hatch_download_url, source, media_type FROM photos WHERE baby_id = $1 ORDER BY create_date",
                baby["id"],
            )
            return [_row_photo(r, hatch_baby_id) for r in rows]
    except Exception as e:
        logger.warning("get_photos_for_baby_hatch_id failed: %s", e)
        return None


# --- Sync: unsynced records and mark synced (per baby for calendar association) ---


async def get_unsynced_feedings_for_baby(baby_id: int, hatch_baby_id: int) -> list[tuple[int, dict]]:
    """Return [(internal_row_id, api_shape_dict), ...] for this baby."""
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, hatch_id, start_time, end_time, amount, duration_seconds, method, source, created_at, updated_at FROM feedings WHERE baby_id = $1 AND synced_to_calendar_at IS NULL ORDER BY start_time",
            baby_id,
        )
        return [(r["id"], _row_feeding(r, hatch_baby_id)) for r in rows]


async def get_unsynced_diapers_for_baby(baby_id: int, hatch_baby_id: int) -> list[tuple[int, dict]]:
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, hatch_id, diaper_date, diaper_type, details, created_at, updated_at FROM diapers WHERE baby_id = $1 AND synced_to_calendar_at IS NULL ORDER BY diaper_date",
            baby_id,
        )
        return [(r["id"], _row_diaper(r, hatch_baby_id)) for r in rows]


async def get_unsynced_weights_for_baby(baby_id: int, hatch_baby_id: int) -> list[tuple[int, dict]]:
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, hatch_id, weight_grams, weight_date, created_at, updated_at FROM weights WHERE baby_id = $1 AND synced_to_calendar_at IS NULL ORDER BY weight_date",
            baby_id,
        )
        return [(r["id"], _row_weight(r, hatch_baby_id)) for r in rows]


async def mark_feedings_synced(ids: list[int]) -> None:
    if not _pool or not ids:
        return
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE feedings SET synced_to_calendar_at = now() WHERE id = ANY($1::int[])", ids)


async def mark_diapers_synced(ids: list[int]) -> None:
    if not _pool or not ids:
        return
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE diapers SET synced_to_calendar_at = now() WHERE id = ANY($1::int[])", ids)


async def mark_weights_synced(ids: list[int]) -> None:
    if not _pool or not ids:
        return
    async with _pool.acquire() as conn:
        await conn.execute("UPDATE weights SET synced_to_calendar_at = now() WHERE id = ANY($1::int[])", ids)


async def get_babies_for_sync() -> list[tuple[int, int, str]]:
    """Return [(internal_id, hatch_id, baby_name), ...] for calendar lookup and per-baby unsynced queries."""
    if not _pool:
        return []
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, hatch_id, name FROM babies ORDER BY id")
        return [(r["id"], r["hatch_id"], r["name"] or "Baby") for r in rows]
