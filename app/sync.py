"""
Sync Hatch Grow data (diapers, feedings, sleep, weight) from the database to Google Calendar.
Only records with synced_to_calendar_at IS NULL are synced; after creating an event we set
synced_to_calendar_at so they are not duplicated.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from app.db import (
    get_babies_for_sync,
    get_unsynced_diapers_for_baby,
    get_unsynced_feedings_for_baby,
    get_unsynced_sleeps_for_baby,
    get_unsynced_weights_for_baby,
    mark_diapers_synced,
    mark_feedings_synced,
    mark_sleeps_synced,
    mark_weights_synced,
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

logger = logging.getLogger(__name__)


async def run_sync() -> dict:
    """
    One full sync: load babies and unsynced records from PostgreSQL, create GCal events,
    mark rows as synced. Returns a small summary dict (e.g. created counts).
    """
    summary = {"events_created": 0, "errors": []}
    gcal_share_email = os.environ.get("GOOGLE_CALENDAR_SHARE_EMAIL", "").strip()
    service_account_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")

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

    try:
        service = get_calendar_service()
    except Exception as e:
        summary["errors"].append(f"Google Calendar auth: {e}")
        return summary

    babies = await get_babies_for_sync()
    if not babies:
        return summary

    for internal_baby_id, hatch_baby_id, baby_name in babies:
        try:
            cal_id = get_or_create_baby_calendar(service, baby_name, gcal_share_email)
        except Exception as e:
            summary["errors"].append(f"Calendar for {baby_name}: {e}")
            continue

        # Diapers
        diapers_list = await get_unsynced_diapers_for_baby(internal_baby_id, hatch_baby_id)
        diaper_ids = []
        for row_id, d in diapers_list:
            try:
                summy, desc, start, end = diaper_to_event(d)
                create_event(service, cal_id, summy, desc, start, end)
                summary["events_created"] += 1
                diaper_ids.append(row_id)
            except Exception as e:
                summary["errors"].append(f"Diaper event {d.get('id')}: {e}")
        if diaper_ids:
            await mark_diapers_synced(diaper_ids)

        # Feedings
        feedings_list = await get_unsynced_feedings_for_baby(internal_baby_id, hatch_baby_id)
        feeding_ids = []
        for row_id, f in feedings_list:
            try:
                summy, desc, start, end = feeding_to_event(f)
                create_event(service, cal_id, summy, desc, start, end)
                summary["events_created"] += 1
                feeding_ids.append(row_id)
            except Exception as e:
                summary["errors"].append(f"Feeding event {f.get('id')}: {e}")
        if feeding_ids:
            await mark_feedings_synced(feeding_ids)

        # Sleeps
        sleeps_list = await get_unsynced_sleeps_for_baby(internal_baby_id, hatch_baby_id)
        sleep_ids = []
        for row_id, s in sleeps_list:
            try:
                summy, desc, start, end = sleep_to_event(s)
                create_event(service, cal_id, summy, desc, start, end)
                summary["events_created"] += 1
                sleep_ids.append(row_id)
            except Exception as e:
                summary["errors"].append(f"Sleep event {s.get('id')}: {e}")
        if sleep_ids:
            await mark_sleeps_synced(sleep_ids)

        # Weights
        weights_list = await get_unsynced_weights_for_baby(internal_baby_id, hatch_baby_id)
        weight_ids = []
        for row_id, w in weights_list:
            try:
                summy, desc, start, end = weight_to_event(w)
                create_event(service, cal_id, summy, desc, start, end)
                summary["events_created"] += 1
                weight_ids.append(row_id)
            except Exception as e:
                summary["errors"].append(f"Weight event {w.get('id')}: {e}")
        if weight_ids:
            await mark_weights_synced(weight_ids)

    return summary
