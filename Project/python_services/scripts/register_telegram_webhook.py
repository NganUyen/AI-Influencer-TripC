"""
register_telegram_webhook.py
==============================
One-time script: registers the webhook URL with Telegram.

Run once after deployment (or whenever the public URL changes):
    python scripts/register_telegram_webhook.py

What it does:
  POST https://api.telegram.org/bot<TOKEN>/setWebhook
  {
    "url": "<BACKEND_PUBLIC_URL>/api/webhooks/telegram",
    "secret_token": "<TELEGRAM_WEBHOOK_SECRET>",
    "allowed_updates": ["message", "callback_query"]
  }

Telegram docs: https://core.telegram.org/bots/api#setwebhook

Requirements:
  - TELEGRAM_BOT_TOKEN must be set in .env.local or .env.production
  - BACKEND_PUBLIC_URL must be set (e.g. https://ai-influencer.tripc.ai/backend)
  - TELEGRAM_WEBHOOK_SECRET must be set (any random string, 1-256 chars, A-Za-z0-9_-)
"""

import asyncio
import sys
import os

# Make sure we can import from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from config.settings import settings


async def register_webhook() -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token.startswith("your_"):
        print("❌  TELEGRAM_BOT_TOKEN is not set. Aborting.")
        sys.exit(1)

    backend_url = (settings.BACKEND_PUBLIC_URL or "").rstrip("/")
    if not backend_url or "localhost" in backend_url:
        # Fallback: ask user
        backend_url = input(
            "BACKEND_PUBLIC_URL not set. Enter the public backend URL "
            "(e.g. https://ai-influencer.tripc.ai/backend): "
        ).strip().rstrip("/")

    webhook_url = f"{backend_url}/api/webhooks/telegram"
    tg_api_url = f"https://api.telegram.org/bot{token}/setWebhook"

    payload = {
        "url": webhook_url,
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,   # discard queued updates from before registration
    }

    secret = settings.TELEGRAM_WEBHOOK_SECRET
    if secret:
        payload["secret_token"] = secret
        print(f"🔒  Using secret_token: {secret[:6]}{'*' * (len(secret) - 6)}")
    else:
        print("⚠️   TELEGRAM_WEBHOOK_SECRET not set — webhook will be unauthenticated.")

    print(f"\n📡  Registering webhook:")
    print(f"    URL: {webhook_url}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(tg_api_url, json=payload)

    data = resp.json()
    if data.get("ok"):
        print(f"\n✅  Webhook registered successfully!")
        print(f"    Response: {data.get('description', 'OK')}")
    else:
        print(f"\n❌  Failed to register webhook:")
        print(f"    Error code: {data.get('error_code')}")
        print(f"    Description: {data.get('description')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(register_webhook())
