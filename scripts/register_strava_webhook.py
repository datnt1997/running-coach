#!/usr/bin/env python3
"""One-time script to register a Strava webhook subscription.

Strava will immediately send a GET validation request to /strava/webhook —
your server must be running and publicly reachable before you run this script.
For local dev, use a tunnel such as ngrok and set STRAVA_REDIRECT_URI to the
tunnel URL.

Usage:
    python scripts/register_strava_webhook.py
"""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_WEBHOOK_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN")
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI", "")


async def register() -> None:
    callback_url = STRAVA_REDIRECT_URI.replace("/strava/callback", "/strava/webhook")
    print(f"Registering webhook → {callback_url}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.strava.com/api/v3/push_subscriptions",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "callback_url": callback_url,
                "verify_token": STRAVA_WEBHOOK_VERIFY_TOKEN,
            },
        )
        print(f"Status {resp.status_code}: {resp.json()}")


if __name__ == "__main__":
    asyncio.run(register())
