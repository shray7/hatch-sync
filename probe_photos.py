"""
Probe for Hatch Grow daily photos API: GET /service/app/photo/v1/fetch/{baby_id}
"""
import asyncio
import json
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()

from app.hatch_grow_service import API_URL, login


async def main():
    email = os.environ.get("HATCH_EMAIL")
    password = os.environ.get("HATCH_PASSWORD")
    if not email or not password:
        print("Set HATCH_EMAIL and HATCH_PASSWORD in .env")
        return

    async with aiohttp.ClientSession() as session:
        print("Logging in...")
        login_data = await login(session, email, password)
        token = login_data["token"]
        babies = login_data.get("payload", {}).get("babies", [])
        if not babies:
            print("No babies in account.")
            return
        baby_id = babies[0]["id"]
        baby_name = babies[0].get("name", "Baby")
        print(f"Using baby: {baby_name} (id={baby_id})\n")

        path = f"/service/app/photo/v1/fetch/{baby_id}"
        url = f"{API_URL}{path}"
        headers = {"X-HatchBaby-Auth": token}
        print(f"GET {url}")
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            print(f"Status: {resp.status}")
            print(f"Response (raw): {text[:2000]}")
            if len(text) > 2000:
                print("... (truncated)")
            try:
                data = json.loads(text)
                print(f"\nParsed keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                if isinstance(data, dict) and "payload" in data:
                    payload = data["payload"]
                    if isinstance(payload, list):
                        print(f"Payload length: {len(payload)}")
                    elif isinstance(payload, dict):
                        print(f"Payload keys: {list(payload.keys())}")
            except json.JSONDecodeError:
                pass

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
