"""
Sync Hatch Grow data (diapers, feedings, sleep, weight) to Google Calendar.
Tracks last-seen record IDs per baby per type so only new entries become events.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import aiohttp

from app.cache import (
    get_cached_grow_data,
    get_cached_login,
    set_cached_grow_data,
    set_cached_login,
)
from app.gcal_service import (
    create_event,
    diaper_to_event,
    feeding_to_event,
    get_calendar_service,
    get_or_create_baby_calendar,
    sleep_to_event,
    weight_to_event,
)
from app.hatch_grow_service import (
    fetch_diapers,
    fetch_feedings,
    fetch_sleep,
    fetch_weight,
    login,
)

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "sync_state.json"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load sync state: %s", e)
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _state_key(baby_id: int, data_type: str) -> str:
    return f"baby_{baby_id}_{data_type}"


def _get_seen_ids(state: dict, baby_id: int, data_type: str) -> set[int | str]:
    key = _state_key(baby_id, data_type)
    return set(state.get(key, []))


def _set_seen_ids(state: dict, baby_id: int, data_type: str, ids: list[int | str]) -> None:
    key = _state_key(baby_id, data_type)
    state[key] = list(ids)


async def run_sync() -> dict:
    """
    One full sync: login to Hatch, fetch all data, create GCal events for new
    records, update state. Returns a small summary dict (e.g. created counts).
    """
    summary = {"events_created": 0, "errors": []}
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    gcal_share_email = os.environ.get("GOOGLE_CALENDAR_SHARE_EMAIL", "").strip()
    service_account_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")

    if not email or not password:
        summary["errors"].append("HATCH_EMAIL and HATCH_PASSWORD required")
        return summary
    path = None
    if service_account_file:
        path = Path(service_account_file)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / service_account_file
    if not path or not path.is_file():
        path = Path(__file__).resolve().parent.parent / "service_account.json"
    if not path.is_file():
        summary["errors"].append("GOOGLE_SERVICE_ACCOUNT_FILE not set or file missing")
        return summary

    state = _load_state()

    try:
        service = get_calendar_service()
    except Exception as e:
        summary["errors"].append(f"Google Calendar auth: {e}")
        return summary

    async with aiohttp.ClientSession() as session:
        login_data = await get_cached_login()
        if not login_data:
            try:
                login_data = await login(session, email, password)
            except Exception as e:
                summary["errors"].append(f"Hatch login: {e}")
                return summary
            # Cache full login payload (token + babies)
            await set_cached_login(login_data)

        token = login_data["token"]
        babies = login_data.get("payload", {}).get("babies", [])

        for baby in babies:
            baby_id = baby["id"]
            baby_name = baby.get("name", "Baby")
            try:
                cal_id = get_or_create_baby_calendar(service, baby_name, gcal_share_email)
            except Exception as e:
                summary["errors"].append(f"Calendar for {baby_name}: {e}")
                continue

            # Try to use cached Grow data for this baby first
            cached = await get_cached_grow_data(baby_id)
            if cached and isinstance(cached, dict):
                diapers = cached.get("diapers") or []
                feedings = cached.get("feedings") or []
                sleeps = cached.get("sleeps") or []
                weights = cached.get("weights") or []
            else:
                # Diapers
                try:
                    diapers = await fetch_diapers(session, token, baby_id)
                except Exception as e:
                    summary["errors"].append(f"Diapers fetch: {e}")
                    diapers = []

                # Feedings
                try:
                    feedings = await fetch_feedings(session, token, baby_id)
                except Exception as e:
                    summary["errors"].append(f"Feedings fetch: {e}")
                    feedings = []

                # Sleep
                try:
                    sleeps = await fetch_sleep(session, token, baby_id)
                except Exception as e:
                    summary["errors"].append(f"Sleep fetch: {e}")
                    sleeps = []

                # Weight
                try:
                    weights = await fetch_weight(session, token, baby_id)
                except Exception as e:
                    summary["errors"].append(f"Weight fetch: {e}")
                    weights = []

                # Cache whatever we managed to fetch (even if some lists are empty)
                await set_cached_grow_data(
                    baby_id,
                    {
                        "diapers": diapers,
                        "feedings": feedings,
                        "sleeps": sleeps,
                        "weights": weights,
                    },
                )

            # Diapers → events
            seen = _get_seen_ids(state, baby_id, "diaper")
            for d in diapers:
                rid = d.get("id")
                if rid is not None and rid not in seen:
                    try:
                        summy, desc, start, end = diaper_to_event(d)
                        create_event(service, cal_id, summy, desc, start, end)
                        summary["events_created"] += 1
                        seen.add(rid)
                    except Exception as e:
                        summary["errors"].append(f"Diaper event {rid}: {e}")
            _set_seen_ids(state, baby_id, "diaper", list(seen))

            # Feedings → events
            seen = _get_seen_ids(state, baby_id, "feeding")
            for f in feedings:
                rid = f.get("id")
                if rid is not None and rid not in seen:
                    try:
                        summy, desc, start, end = feeding_to_event(f)
                        create_event(service, cal_id, summy, desc, start, end)
                        summary["events_created"] += 1
                        seen.add(rid)
                    except Exception as e:
                        summary["errors"].append(f"Feeding event {rid}: {e}")
            _set_seen_ids(state, baby_id, "feeding", list(seen))

            # Sleep → events
            seen = _get_seen_ids(state, baby_id, "sleep")
            for s in sleeps:
                rid = s.get("id")
                if rid is not None and rid not in seen:
                    try:
                        summy, desc, start, end = sleep_to_event(s)
                        create_event(service, cal_id, summy, desc, start, end)
                        summary["events_created"] += 1
                        seen.add(rid)
                    except Exception as e:
                        summary["errors"].append(f"Sleep event {rid}: {e}")
            _set_seen_ids(state, baby_id, "sleep", list(seen))

            # Weight → events
            seen = _get_seen_ids(state, baby_id, "weight")
            for w in weights:
                rid = w.get("id")
                if rid is not None and rid not in seen:
                    try:
                        summy, desc, start, end = weight_to_event(w)
                        create_event(service, cal_id, summy, desc, start, end)
                        summary["events_created"] += 1
                        seen.add(rid)
                    except Exception as e:
                        summary["errors"].append(f"Weight event {rid}: {e}")
            _set_seen_ids(state, baby_id, "weight", list(seen))

    _save_state(state)
    return summary
