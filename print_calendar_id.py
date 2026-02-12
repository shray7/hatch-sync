"""
One-off: print the "Baby - Baby Tracker" calendar ID so you can add it in Google Calendar
via Other calendars → Add → Subscribe to calendar → paste the ID.
"""
import asyncio
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

from app.gcal_service import get_calendar_service, get_or_create_baby_calendar
from app.hatch_grow_service import login


async def main():
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    share_email = os.environ.get("GOOGLE_CALENDAR_SHARE_EMAIL", "").strip()
    if not email or not password:
        print("Set HATCH_EMAIL and HATCH_PASSWORD in .env")
        return
    path = Path(__file__).parent / os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    if not path.is_file():
        print("Set GOOGLE_SERVICE_ACCOUNT_FILE and ensure the JSON file exists.")
        return

    service = get_calendar_service()
    async with aiohttp.ClientSession() as session:
        login_data = await login(session, email, password)
    babies = login_data.get("payload", {}).get("babies", [])
    if not babies:
        print("No baby profiles found in Hatch account.")
        return
    baby_name = babies[0].get("name", "Baby")
    cal_id = get_or_create_baby_calendar(service, baby_name, share_email)

    print()
    print("Calendar created/found and shared with:", share_email or "(none)")
    print()
    print("To add it in Google Calendar if you don't see it:")
    print("  1. In the left sidebar, under 'Other calendars', click the +")
    print("  2. Choose 'Subscribe to calendar'")
    print("  3. Paste this Calendar ID:")
    print()
    print(f"   {cal_id}")
    print()
    print("Then click Add. The 'Uma - Baby Tracker' (or your baby's name) calendar should appear.")
    print()
    if share_email:
        print("Make sure GOOGLE_CALENDAR_SHARE_EMAIL in .env is the same Gmail you're signed into")
        print("in Google Calendar. If it's different, update .env and run sync again.")
    else:
        print("Set GOOGLE_CALENDAR_SHARE_EMAIL in .env to your Gmail so the calendar is shared with you.")


if __name__ == "__main__":
    asyncio.run(main())
