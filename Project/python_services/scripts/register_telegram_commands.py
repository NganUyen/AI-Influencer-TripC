"""
Register the canonical command menu for the Telegram bot.

Run after deployment, or whenever the public command surface changes:

    python scripts/register_telegram_commands.py

Telegram's Bot API accepts command names containing lowercase letters, digits,
and underscores. Keep this list aligned with api.telegram_webhook._help_text.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Dict, List

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings


TELEGRAM_BOT_COMMANDS: List[Dict[str, str]] = [
    {"command": "start", "description": "Open the AI Influencer studio"},
    {"command": "media", "description": "Open the media creation menu"},
    {"command": "create_video", "description": "Start video planning"},
    {"command": "create_image", "description": "Create marketing images"},
    {"command": "personas", "description": "Inspect your personas"},
    {"command": "quota", "description": "Check provider usage quota"},
    {"command": "cancel", "description": "Cancel the active flow"},
]


async def register_commands() -> None:
    token = str(settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token or token.startswith("your_"):
        raise SystemExit("TELEGRAM_BOT_TOKEN is not configured.")

    endpoint = f"https://api.telegram.org/bot{token}/setMyCommands"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            endpoint,
            json={"commands": TELEGRAM_BOT_COMMANDS},
        )

    payload = response.json()
    if not response.is_success or not payload.get("ok"):
        description = payload.get("description") or response.text
        raise SystemExit(f"Telegram command registration failed: {description}")

    print(f"Registered {len(TELEGRAM_BOT_COMMANDS)} Telegram commands.")


if __name__ == "__main__":
    asyncio.run(register_commands())
