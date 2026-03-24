import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Load your .env.local (adjust path if needed)
project_dir = Path(__file__).parent.parent.parent.absolute()
load_dotenv(project_dir / ".env.local")

token = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def main():
    print("Deleting any active webhook...")
    result = await bot.delete_webhook(drop_pending_updates=True)
    
    if result:
        print("✅ Webhook successfully deleted!")
        print("You can now safely run your bot with long polling.")
    else:
        print("Webhook was already deleted or something went wrong.")

asyncio.run(main())