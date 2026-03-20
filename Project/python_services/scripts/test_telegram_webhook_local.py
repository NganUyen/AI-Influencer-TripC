"""
test_telegram_webhook_local.py
================================
Lightweight local test for the Telegram webhook handler.
Does NOT need the full FastAPI stack, database, or any real API keys.

Run from the python_services directory:
    python scripts/test_telegram_webhook_local.py

What happens:
  - The handler code runs locally with fake env vars.
  - All Telegram API HTTP calls are intercepted and printed.
  - You'll see exactly what the bot WOULD send to Telegram.
"""

import asyncio
import sys
import os
import json
from unittest.mock import patch

# Force UTF-8 output on Windows (avoids charmap encode errors on emoji)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Inject minimal environment before any project code loads ──────────────────
# This lets pydantic-settings build Settings() without a real .env file.
_TEST_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET": "test-secret",
    "TELEGRAM_CHAT_ID": "999",
    "BACKEND_PUBLIC_URL": "http://localhost:8000",
    "DATABASE_URL": "postgresql://localhost/test",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "OPENAI_API_KEY": "sk-test",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "FAL_AI_API_KEY": "fal-test",
    "R2_ACCOUNT_ID": "test",
    "R2_ACCESS_KEY_ID": "test",
    "R2_SECRET_ACCESS_KEY": "test",
    "R2_BUCKET_NAME": "test",
    "R2_PUBLIC_URL": "https://test.r2.dev",
    "IPROYAL_USERNAME": "test",
    "IPROYAL_PASSWORD": "test",
    "ENVIRONMENT": "development",
    "DEBUG": "true",
    "CORS_ORIGINS": "http://localhost:3000",
    "JWT_SECRET_KEY": "test-jwt-secret",
    "APP_ADMIN_TOKEN": "test-admin-token",
    "INTERNAL_API_TOKEN": "test-internal-token",
}

# Patch os.environ BEFORE importing anything from the project
with patch.dict(os.environ, _TEST_ENV, clear=False):
    from api.telegram_webhook import (
        _handle_message,
        _handle_callback_query,
        _escape_md,
        inline_keyboard,
    )


# ── Captured outgoing calls ───────────────────────────────────────────────────
_calls: list = []

async def _mock_tg_call(method: str, payload: dict) -> dict:
    _calls.append({"method": method, "payload": payload})
    print(f"\n  [OUT] Telegram API call -> {method}")
    print(f"      {json.dumps(payload, ensure_ascii=True, indent=6)}")
    return {"ok": True}


# ── Test cases ────────────────────────────────────────────────────────────────

async def test_start_command():
    print("\n" + "=" * 60)
    print("TEST 1: /start command")
    print("=" * 60)
    _calls.clear()

    message = {
        "text": "/start",
        "chat": {"id": 123456789},
        "from": {"first_name": "TripC"},
    }

    with patch("api.telegram_webhook._tg_call", side_effect=_mock_tg_call):
        await _handle_message(message)

    assert any(c["method"] == "sendMessage" for c in _calls), "sendMessage not called!"
    assert any("AI Influencer Bot" in json.dumps(c) for c in _calls), "Welcome text missing!"
    print("\n  [PASS] Bot sent welcome message with inline keyboard")


async def test_url_message():
    print("\n" + "=" * 60)
    print("TEST 2: URL message (Pipeline 2 stub)")
    print("=" * 60)
    _calls.clear()

    message = {
        "text": "https://someapp.ai/landing",
        "chat": {"id": 123456789},
    }

    with patch("api.telegram_webhook._tg_call", side_effect=_mock_tg_call):
        await _handle_message(message)

    assert any(c["method"] == "sendMessage" for c in _calls), "sendMessage not called!"
    print("\n  [PASS] Bot acknowledged the URL")


async def test_plain_text():
    print("\n" + "=" * 60)
    print("TEST 3: Plain text message")
    print("=" * 60)
    _calls.clear()

    message = {
        "text": "Hello bot!",
        "chat": {"id": 123456789},
    }

    with patch("api.telegram_webhook._tg_call", side_effect=_mock_tg_call):
        await _handle_message(message)

    assert any(c["method"] == "sendMessage" for c in _calls), "sendMessage not called!"
    print("\n  [PASS] Bot replied to plain text")


async def test_button_tap_approve():
    print("\n" + "=" * 60)
    print("TEST 4: Inline button tap — approve")
    print("=" * 60)
    _calls.clear()

    callback_query = {
        "id": "cq_test_001",
        "data": "approve_daily-story-2026-03-20",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 42,
            "chat": {"id": 123456789},
        },
    }

    with patch("api.telegram_webhook._tg_call", side_effect=_mock_tg_call):
        await _handle_callback_query(callback_query)

    methods = [c["method"] for c in _calls]
    assert "answerCallbackQuery" in methods, "answerCallbackQuery not called! (must be within 10s)"
    assert "editMessageText" in methods, "editMessageText not called! (buttons should be removed)"
    print("\n  [PASS] answerCallbackQuery + editMessageText both called (buttons removed)")


async def test_button_tap_skip():
    print("\n" + "=" * 60)
    print("TEST 5: Inline button tap — skip")
    print("=" * 60)
    _calls.clear()

    callback_query = {
        "id": "cq_test_002",
        "data": "skip_daily-story-2026-03-20",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 43,
            "chat": {"id": 123456789},
        },
    }

    with patch("api.telegram_webhook._tg_call", side_effect=_mock_tg_call):
        await _handle_callback_query(callback_query)

    skip_call = next(
        (c for c in _calls if c["method"] == "editMessageText"), None
    )
    assert skip_call is not None
    assert "Skipped" in skip_call["payload"]["text"]
    print("\n  [PASS] 'Skipped' text sent in editMessageText")


async def test_markdown_escape():
    print("\n" + "=" * 60)
    print("TEST 6: MarkdownV2 escape helper")
    print("=" * 60)

    raw = "https://app.ai/page-test.html is great!"
    escaped = _escape_md(raw)
    # Per Telegram MarkdownV2 spec, these chars MUST be escaped:
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    for ch in ["!", ".", "-"]:
        if ch in raw:
            assert f"\\{ch}" in escaped, f"'{ch}' not escaped"
    print(f"  Input:   {raw}")
    print(f"  Escaped: {escaped}")
    print("\n  [PASS] Special chars escaped correctly")


# ── Main runner ───────────────────────────────────────────────────────────────

async def main():
    print("\nTelegram Webhook Handler - Local Tests")
    print("(No server needed, no real Telegram calls are made)\n")

    tests = [
        test_start_command,
        test_url_message,
        test_plain_text,
        test_button_tap_approve,
        test_button_tap_skip,
        test_markdown_escape,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            await test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  [FAIL] {e}")

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed / {failed} failed")
    print("=" * 60 + "\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
