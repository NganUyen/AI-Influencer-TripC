import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

# ====================== Setup Python Path ======================
script_dir = Path(__file__).parent.absolute()
python_services_dir = script_dir.parent.absolute()

sys.path.insert(0, str(python_services_dir))

print(f"✅ Python path set to: {python_services_dir}")

# ====================== Load .env.local ======================
project_root = python_services_dir.parent.absolute()
load_dotenv(project_root / ".env.local")

# ====================== Import the router ======================
from api.telegram_webhook import router

# ====================== Create FastAPI app for testing ======================
app = FastAPI(title="Telegram Bot Local Test")

# Mount exactly like in main.py (with prefix)
app.include_router(
    router,
    prefix="/api/webhooks",
    tags=["Telegram"],
)

print("✅ Telegram router mounted at /api/webhooks/telegram")

# ====================== Run the server ======================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    PORT = 8000
    
    print(f"\n🚀 Local webhook server running on http://localhost:{PORT}")
    print(f"   Full Telegram endpoint → http://localhost:{PORT}/api/webhooks/telegram")
    print("\nNow start ngrok with: ngrok http 8000\n")

    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT, 
        reload=False,
        log_level="info"
    )