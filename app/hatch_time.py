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
    """
    Parse Hatch API datetime string.
    If the string is UTC (ends with Z or +00:00), returns timezone-aware UTC.
    Otherwise treats as local time in HATCH_TIMEZONE and returns naive datetime.
    """
    if not s:
        return datetime.now(timezone.utc)
    s = s.strip()
    # UTC: Hatch may send "2026-02-18T22:00:00Z" or "...+00:00"
    if s.endswith("Z") or s.endswith("+00:00"):
        s_iso = s.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s_iso)
        except ValueError:
            pass
    # Local (naive) format: "2026-02-18 14:00:00" or "2026-02-18T14:00:00"
    s_plain = s.replace("T", " ")
    for size, fmt in [(19, "%Y-%m-%d %H:%M:%S"), (16, "%Y-%m-%d %H:%M"), (10, "%Y-%m-%d")]:
        try:
            return datetime.strptime(s_plain[:size], fmt)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def hatch_time_to_utc(dt: datetime) -> datetime:
    """
    Convert to UTC. If dt is timezone-aware, convert as-is. If naive, interpret as
    local time in HATCH_TIMEZONE (default PST) and return UTC.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    tz = _display_tz()
    return dt.replace(tzinfo=tz).astimezone(timezone.utc)


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
