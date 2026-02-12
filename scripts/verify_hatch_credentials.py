#!/usr/bin/env python3
"""
Verify HATCH_EMAIL and HATCH_PASSWORD are set and that Hatch Grow login succeeds.
Does not print or log credentials. Run from repo root: python scripts/verify_hatch_credentials.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Allow importing app when run as scripts/verify_hatch_credentials.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Import after path is set
from app.hatch_grow_service import login as hatch_grow_login


async def main() -> int:
    email = (os.environ.get("HATCH_EMAIL") or "").strip()
    password = (os.environ.get("HATCH_PASSWORD") or "").strip()

    if not email or not password:
        print("HATCH_EMAIL and HATCH_PASSWORD are not both set (check .env or environment).")
        return 1

    import aiohttp
    async with aiohttp.ClientSession() as session:
        try:
            data = await hatch_grow_login(session, email, password)
            babies = (data.get("payload") or {}).get("babies") or []
            print("Hatch credentials OK. Login succeeded." + (f" ({len(babies)} baby/babies.)" if babies else ""))
            return 0
        except Exception as e:
            print(f"Hatch login failed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
