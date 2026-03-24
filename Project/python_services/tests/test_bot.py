import asyncio
import logging
import os
from dotenv import load_dotenv
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# ====================== Find .env.local correctly ======================
# This script is inside: .../python_services/tests/
script_dir = Path(__file__).parent.absolute()

# Go UP TWO levels to reach the Project folder
project_dir = script_dir.parent.parent.absolute()   # ← This is the key change
env_path = project_dir / ".env.local"

print(f"Looking for .env.local at: {env_path}")

if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"✅ Successfully loaded .env.local from: {env_path}")
else:
    print(f"❌ Could not find .env.local at: {env_path}")
    print("\nCurrent folder structure:")
    print(f"   Script is in : {script_dir}")
    print(f"   Looking in   : {project_dir}")


# ====================== Get Token ======================
token = os.getenv("TELEGRAM_BOT_TOKEN")

if not token:
    raise ValueError(
        f"❌ TELEGRAM_BOT_TOKEN is missing!\n\n"
        f"Please make sure the file exists here:\n"
        f"   {project_dir}\\.env.local\n\n"
        "and contains this line:\n"
        "TELEGRAM_BOT_TOKEN=your_actual_bot_token_here"
    )

print(f"✅ Token loaded successfully! (length: {len(token)})")


# ====================== Initialize Bot ======================
bot = Bot(
    token=token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    print("🚀 Bot is starting with long polling... (Press Ctrl+C to stop)")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())