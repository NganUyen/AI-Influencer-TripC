import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Load your .env.local
project_root = Path(__file__).parent.parent.parent.absolute()
load_dotenv(project_root / ".env.local")

token = os.getenv("TELEGRAM_BOT_TOKEN")
secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")

ngrok_url = "https://3bfc-2001-ee0-4b77-a740-4c80-45d1-57c9-c2ae.ngrok-free.app/api/webhooks/telegram"

webhook_url = f"{ngrok_url}"

bot = Bot(
    token=token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

async def main():
    print("🧹 Deleting any old webhook first...")
    await bot.delete_webhook(drop_pending_updates=True)

    print(f"🔗 Setting webhook to: {webhook_url}")
    await bot.set_webhook(
        url=webhook_url,
        secret_token=secret,
        drop_pending_updates=True
    )

    print("✅ Webhook successfully set to ngrok!")
    print("You can now test your bot by sending /start or waiting for the daily story.")

asyncio.run(main())