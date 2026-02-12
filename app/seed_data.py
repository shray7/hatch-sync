"""
Seed data for Hatch Grow analytics.

Provides realistic-looking sample data for:
- babies
- feedings
- diapers
- sleeps
- weights

The timestamps are generated relative to "today" so that dashboards
for "today" and "last 7 days" look meaningful.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List


def _days_ago(days: int, hour: int = 0, minute: int = 0) -> datetime:
    """Return a datetime `days` ago at a given hour/minute (UTC-naive)."""
    now = datetime.utcnow()
    base = datetime(year=now.year, month=now.month, day=now.day)
    return base - timedelta(days=days) + timedelta(hours=hour, minutes=minute)


def get_seed_grow_data() -> Dict[str, List[Dict[str, Any]]]:
    """
    Return seeded Hatch Grow-style data.

    Shape matches the live API enough for analytics and UI work:
    {
        "babies": [...],
        "feedings": [...],
        "diapers": [...],
        "sleeps": [...],
        "weights": [...],
    }
    """
    # Single baby for now
    baby_id = 1
    babies: List[Dict[str, Any]] = [
        {
            "id": baby_id,
            "name": "Uma",
            # A birth date slightly in the past so age makes sense
            "birthDate": (_days_ago(20).date().isoformat()),
        }
    ]

    feedings: List[Dict[str, Any]] = []
    diapers: List[Dict[str, Any]] = []
    sleeps: List[Dict[str, Any]] = []
    weights: List[Dict[str, Any]] = []

    feeding_id = 1
    diaper_id = 1
    sleep_id = 1
    weight_id = 1

    # Generate the last 14 days of activity (0 = today)
    for day_offset in range(0, 14):
        # Roughly 6 feedings per day at fixed times
        feeding_times = [7, 11, 15, 19, 22, 2]
        for hour in feeding_times:
            start = _days_ago(day_offset, hour=hour, minute=0)
            duration_min = 20 if hour in (7, 19, 22) else 15
            end = start + timedelta(minutes=duration_min)
            amount = 90 if hour in (7, 19) else 70
            method = "Bottle" if hour in (11, 15) else "Nursing"
            source = (
                "Both"
                if method == "Nursing"
                else ("Breastmilk" if hour in (7, 19, 22) else "Formula")
            )
            feedings.append(
                {
                    "id": feeding_id,
                    "babyId": baby_id,
                    "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
                    "endTime": end.strftime("%Y-%m-%d %H:%M:%S"),
                    "amount": amount,
                    "durationInSeconds": duration_min * 60,
                    "method": method,
                    "source": source,
                    "deleted": False,
                    "createDate": start.strftime("%Y-%m-%d %H:%M:%S"),
                    "updateDate": end.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            feeding_id += 1

        # 5–7 diapers per day, mix of Wet/Dirty/Both
        diaper_types = ["Wet", "Wet", "Dirty", "Both", "Wet", "Dirty"]
        for i, dtype in enumerate(diaper_types):
            t = _days_ago(day_offset, hour=6 + i * 3)
            diapers.append(
                {
                    "id": diaper_id,
                    "babyId": baby_id,
                    "diaperDate": t.strftime("%Y-%m-%d %H:%M:%S"),
                    "diaperType": dtype,
                    "details": "" if dtype != "Dirty" else "Messy",
                    "deleted": False,
                    "createDate": t.strftime("%Y-%m-%d %H:%M:%S"),
                    "updateDate": t.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            diaper_id += 1

        # Sleep: 2–3 naps plus night sleep block
        # Night sleep: 20:00 -> 06:00 (spanning to next day)
        night_start = _days_ago(day_offset + 1, hour=20)
        night_end = _days_ago(day_offset, hour=6)
        sleeps.append(
            {
                "id": sleep_id,
                "babyId": baby_id,
                "startTime": night_start.strftime("%Y-%m-%d %H:%M:%S"),
                "endTime": night_end.strftime("%Y-%m-%d %H:%M:%S"),
                "deleted": False,
                "createDate": night_start.strftime("%Y-%m-%d %H:%M:%S"),
                "updateDate": night_end.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        sleep_id += 1

        # Naps
        nap_specs = [(9, 1.0), (13, 1.5), (17, 0.75)]
        for hour, hours_len in nap_specs:
            start = _days_ago(day_offset, hour=hour)
            end = start + timedelta(hours=hours_len)
            sleeps.append(
                {
                    "id": sleep_id,
                    "babyId": baby_id,
                    "startTime": start.strftime("%Y-%m-%d %H:%M:%S"),
                    "endTime": end.strftime("%Y-%m-%d %H:%M:%S"),
                    "deleted": False,
                    "createDate": start.strftime("%Y-%m-%d %H:%M:%S"),
                    "updateDate": end.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            sleep_id += 1

        # Weight every 3 days
        if day_offset % 3 == 0:
            # Starting weight about 3.2kg, gain ~30g/day
            days_since_start = 20 - day_offset
            base_weight = 3200 + days_since_start * 30
            measured_at = _days_ago(day_offset, hour=10)
            weights.append(
                {
                    "id": weight_id,
                    "babyId": baby_id,
                    "weight": base_weight,
                    "weightDate": measured_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "createDate": measured_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updateDate": measured_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            weight_id += 1

    return {
        "babies": babies,
        "feedings": feedings,
        "diapers": diapers,
        "sleeps": sleeps,
        "weights": weights,
    }

