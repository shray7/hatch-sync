"""
Shared Hatch API datetime parsing: interpret Hatch datetime strings as local time
in HATCH_TIMEZONE (default PST) and convert to UTC for storage. All API output
times are formatted in that same timezone (PST by default).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# All times are interpreted and displayed in this timezone (PST/PDT).
DISPLAY_TIMEZONE = "America/Los_Angeles"


def _display_tz() -> ZoneInfo:
    return ZoneInfo(os.environ.get("HATCH_TIMEZONE", "").strip() or DISPLAY_TIMEZONE)


def parse_hatch_dt(s: str) -> datetime:
    """Parse Hatch API datetime string to naive datetime."""
    if not s:
        return datetime.utcnow()
    s = s.strip().replace("Z", "").replace("T", " ")
    for size, fmt in [(19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M"), (10, "%Y-%m-%d")]:
        try:
            return datetime.strptime(s[:size], fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def hatch_time_to_utc(dt_naive: datetime) -> datetime:
    """
    Interpret naive datetime as local time in HATCH_TIMEZONE (default PST) and return UTC.
    """
    tz = _display_tz()
    return dt_naive.replace(tzinfo=tz).astimezone(timezone.utc)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    return dt + timedelta(minutes=minutes)


def format_hatch_dt(dt: datetime) -> str:
    """
    Format a timezone-aware datetime for API response in PST (or HATCH_TIMEZONE).
    Returns ISO 8601 with offset so the frontend can parse and display in PST, e.g.
    "2026-02-18T14:00:00-08:00".
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_display_tz())
    return local.isoformat(timespec="seconds")
