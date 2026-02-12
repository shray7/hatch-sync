"""
Google Calendar helpers: service account auth, get/create baby calendar, create events.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Required for calendar creation and ACL (sharing)
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    """Build Calendar API v3 service using service account JSON."""
    path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    if not os.path.isabs(path):
        path = Path(__file__).resolve().parent.parent / path
    creds = service_account.Credentials.from_service_account_file(
        str(path), scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def get_or_create_baby_calendar(service, baby_name: str, share_with_email: str) -> str:
    """
    Find a calendar named "{baby_name} - Baby Tracker" or create it,
    share it with share_with_email, and return its calendar_id.
    """
    title = f"{baby_name} - Baby Tracker"
    # List calendars this account owns or has access to
    page = service.calendarList().list().execute()
    for item in page.get("items", []):
        if item.get("summary") == title:
            cal_id = item["id"]
            _ensure_shared(service, cal_id, share_with_email)
            return cal_id
    # Create new calendar
    body = {"summary": title, "description": "Hatch Grow sync: diapers, feedings, sleep, weight"}
    created = service.calendars().insert(body=body).execute()
    cal_id = created["id"]
    _ensure_shared(service, cal_id, share_with_email)
    return cal_id


def _ensure_shared(service, calendar_id: str, email: str) -> None:
    """Share the calendar with the given email (writer). Idempotent."""
    if not email:
        return
    acl = service.acl().list(calendarId=calendar_id).execute()
    for rule in acl.get("items", []):
        if rule.get("scope", {}).get("type") == "user" and rule.get("scope", {}).get("value") == email:
            return  # already shared
    service.acl().insert(
        calendarId=calendar_id,
        body={
            "scope": {"type": "user", "value": email},
            "role": "writer",
        },
    ).execute()


def create_event(service, calendar_id: str, summary: str, description: str, start_dt: datetime, end_dt: datetime) -> dict:
    """Insert a single all-day or timed event. Returns the created event."""
    # Use datetime for timed events; calendar API wants RFC3339 or date
    body = {
        "summary": summary,
        "description": description or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
    }
    return service.events().insert(calendarId=calendar_id, body=body).execute()


# --- Helpers to format Hatch entries as calendar event (summary, description, start, end) ---


def diaper_to_event(entry: dict) -> tuple[str, str, datetime, datetime]:
    """(summary, description, start, end) for a diaper entry."""
    raw = entry.get("diaperDate") or entry.get("createDate") or ""
    dt = _parse_hatch_dt(raw)
    dtype = entry.get("diaperType") or "Diaper"
    details = (entry.get("details") or "").strip()
    summary = f"Diaper - {dtype}"
    desc = details or ""
    # Event is a short block (e.g. 5 min) so it shows at that time
    end = _add_minutes(dt, 5)
    return summary, desc, dt, end


def feeding_to_event(entry: dict) -> tuple[str, str, datetime, datetime]:
    """(summary, description, start, end) for a feeding entry."""
    raw = entry.get("startTime") or entry.get("createDate") or ""
    dt = _parse_hatch_dt(raw)
    method = entry.get("method") or "Feeding"
    source = entry.get("source") or ""
    amount = entry.get("amount")
    duration_sec = entry.get("durationInSeconds")
    parts = [method]
    if source:
        parts.append(source)
    if amount is not None:
        parts.append(f"{amount}g")
    summary = "Feeding - " + " ".join(str(p) for p in parts)
    desc_parts = []
    if duration_sec is not None:
        desc_parts.append(f"Duration: {duration_sec // 60}m {duration_sec % 60}s")
    description = "\n".join(desc_parts) if desc_parts else ""
    end_raw = entry.get("endTime")
    end = _parse_hatch_dt(end_raw) if end_raw else _add_minutes(dt, 30)
    return summary, description, dt, end


def sleep_to_event(entry: dict) -> tuple[str, str, datetime, datetime]:
    """(summary, description, start, end) for a sleep entry. Adapt to actual API shape."""
    # Common fields might be startTime/endTime or start/end
    raw_start = entry.get("startTime") or entry.get("start") or entry.get("createDate") or ""
    raw_end = entry.get("endTime") or entry.get("end") or entry.get("updateDate") or ""
    start_dt = _parse_hatch_dt(raw_start)
    end_dt = _parse_hatch_dt(raw_end) if raw_end else _add_minutes(start_dt, 60)
    duration_min = int((end_dt - start_dt).total_seconds() / 60)
    summary = f"Sleep - {duration_min}m"
    return summary, "", start_dt, end_dt


def weight_to_event(entry: dict) -> tuple[str, str, datetime, datetime]:
    """(summary, description, start, end) for a weight entry."""
    raw = entry.get("createDate") or entry.get("weightDate") or ""
    dt = _parse_hatch_dt(raw)
    weight_g = entry.get("weight") or entry.get("weightInGrams")
    if weight_g is not None:
        summary = f"Weight - {weight_g}g"
    else:
        summary = "Weight"
    end = _add_minutes(dt, 5)
    return summary, "", dt, end


def _parse_hatch_dt(s: str) -> datetime:
    """Parse Hatch API datetime string to datetime (naive UTC)."""
    if not s:
        return datetime.utcnow()
    s = s.strip().replace("Z", "").replace("T", " ")
    for size, fmt in [(19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M"), (10, "%Y-%m-%d")]:
        try:
            return datetime.strptime(s[:size], fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def _add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)
