"""
check_telegram_webhook.py
===========================
Diagnostic script: shows the current Telegram webhook status.

Run anytime to verify state:
    python scripts/check_telegram_webhook.py

Telegram docs: https://core.telegram.org/bots/api#getwebhookinfo
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from config.settings import settings


async def check_webhook() -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token.startswith("your_"):
        print("❌  TELEGRAM_BOT_TOKEN is not set.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/getWebhookInfo"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)

    data = resp.json()
    if not data.get("ok"):
        print(f"❌  Telegram API error: {data.get('description')}")
        sys.exit(1)

    info = data.get("result", {})

    print("\n📋  Telegram Webhook Status")
    print("=" * 40)
    print(f"  URL               : {info.get('url') or '(not set)'}")
    print(f"  Has custom cert   : {info.get('has_custom_certificate', False)}")
    print(f"  Pending updates   : {info.get('pending_update_count', 0)}")
    print(f"  Max connections   : {info.get('max_connections', 'default')}")
    print(f"  Allowed updates   : {info.get('allowed_updates', 'all')}")
    print(f"  Last error date   : {info.get('last_error_date', 'none')}")
    print(f"  Last error msg    : {info.get('last_error_message', 'none')}")

    if not info.get("url"):
        print("\n⚠️   No webhook registered yet.")
        print("    Run: python scripts/register_telegram_webhook.py")
    else:
        print(f"\n✅  Webhook is active at: {info['url']}")


if __name__ == "__main__":
    asyncio.run(check_webhook())
