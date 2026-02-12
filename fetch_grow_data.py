"""
Fetch feedings, diapers, and sleep data from the Hatch Baby (Grow) API.

Uses the same HATCH_EMAIL / HATCH_PASSWORD credentials from .env.
API base: https://data.hatchbaby.com
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

import aiohttp
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://data.hatchbaby.com"


async def login(session: aiohttp.ClientSession, email: str, password: str) -> dict:
    """Login and return the full payload (includes token, babies, etc.)."""
    url = f"{API_URL}/public/v1/login"
    async with session.post(url, json={"email": email, "password": password}) as resp:
        data = await resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Login failed: {data.get('message')}")
    return data


async def fetch_endpoint(
    session: aiohttp.ClientSession, path: str, token: str
) -> dict | None:
    """GET a Hatch API endpoint. Returns parsed JSON or None on error."""
    url = f"{API_URL}{path}"
    headers = {"X-HatchBaby-Auth": token}
    try:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            if data.get("status") == "success":
                return data.get("payload")
            else:
                print(f"  [{path}] API returned: {data.get('message', data.get('status'))}")
                return None
    except Exception as e:
        print(f"  [{path}] Request error: {e}")
        return None


async def main():
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        print("Set HATCH_EMAIL and HATCH_PASSWORD in .env")
        return

    async with aiohttp.ClientSession() as session:
        # --- Login ---
        print(f"Logging in as {email}...")
        login_data = await login(session, email, password)
        token = login_data["token"]
        member = login_data["payload"]
        babies = member.get("babies", [])

        print(f"Login OK. Found {len(babies)} baby profile(s):\n")
        for baby in babies:
            print(f"  - {baby['name']} (id={baby['id']}, born={baby.get('birthDate', '?')})")

        # --- Fetch data for each baby ---
        for baby in babies:
            baby_id = baby["id"]
            baby_name = baby["name"]
            print(f"\n{'='*60}")
            print(f"Data for {baby_name} (id={baby_id})")
            print(f"{'='*60}")

            # Feedings
            print("\n--- Feedings ---")
            feedings = await fetch_endpoint(
                session, f"/service/app/feeding/v2/fetch/{baby_id}", token
            )
            if feedings and "feedings" in feedings:
                entries = [f for f in feedings["feedings"] if not f.get("deleted")]
                print(f"  {len(entries)} feeding record(s) (excluding deleted)")
                for f in entries[-10:]:  # show last 10
                    ts = f.get("startTime", f.get("createDate", "?"))
                    amount_g = f.get("amount")
                    method = f.get("method") or "?"
                    source = f.get("source") or "?"
                    duration = f.get("durationInSeconds")
                    dur_str = f"  {duration//60}m{duration%60}s" if duration else ""
                    amt_str = f"  {amount_g}g" if amount_g else ""
                    print(f"  {ts}  method={method}  source={source}{amt_str}{dur_str}")
                if len(entries) > 10:
                    print(f"  ... ({len(entries) - 10} earlier records not shown)")
            else:
                print("  No feeding data returned.")

            # Diapers
            print("\n--- Diapers ---")
            diapers = await fetch_endpoint(
                session, f"/service/app/diaper/v1/fetch/{baby_id}", token
            )
            if diapers and "diapers" in diapers:
                entries = [d for d in diapers["diapers"] if not d.get("deleted")]
                print(f"  {len(entries)} diaper record(s) (excluding deleted)")
                for d in entries[-10:]:  # show last 10
                    ts = d.get("diaperDate", d.get("createDate", "?"))
                    dtype = d.get("diaperType", "?")
                    details = d.get("details", "")
                    det_str = f'  "{details}"' if details else ""
                    print(f"  {ts}  type={dtype}{det_str}")
                if len(entries) > 10:
                    print(f"  ... ({len(entries) - 10} earlier records not shown)")
            else:
                print("  No diaper data returned.")

            # Sleep — try several possible endpoint patterns
            print("\n--- Sleep ---")
            sleep_data = None
            sleep_paths = [
                f"/service/app/sleep/v1/fetch/{baby_id}",
                f"/service/app/sleep/v2/fetch/{baby_id}",
                f"/service/app/sleepSession/v1/fetch/{baby_id}",
                f"/service/app/sleepSession/v2/fetch/{baby_id}",
            ]
            for path in sleep_paths:
                result = await fetch_endpoint(session, path, token)
                if result is not None:
                    sleep_data = result
                    print(f"  (found at {path})")
                    break
            if sleep_data:
                # Try to print whatever structure comes back
                print(f"  Raw keys: {list(sleep_data.keys()) if isinstance(sleep_data, dict) else type(sleep_data)}")
                print(f"  {json.dumps(sleep_data, indent=2, default=str)[:2000]}")
            else:
                print("  No sleep endpoint responded successfully.")

            # Weight — also try this since Grow is a scale
            print("\n--- Weight ---")
            weight_paths = [
                f"/service/app/weight/v1/fetch/{baby_id}",
                f"/service/app/weight/v2/fetch/{baby_id}",
            ]
            weight_data = None
            for path in weight_paths:
                result = await fetch_endpoint(session, path, token)
                if result is not None:
                    weight_data = result
                    print(f"  (found at {path})")
                    break
            if weight_data:
                print(f"  Raw keys: {list(weight_data.keys()) if isinstance(weight_data, dict) else type(weight_data)}")
                print(f"  {json.dumps(weight_data, indent=2, default=str)[:2000]}")
            else:
                print("  No weight endpoint responded successfully.")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
