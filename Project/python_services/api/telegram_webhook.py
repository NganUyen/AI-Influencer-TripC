"""
Telegram Bot Webhook Router
============================
Receives all incoming Telegram updates via webhook (POST).
Handles:
  - callback_query  : button taps (inline keyboard)
  - message.text    : plain text messages
  - message.document / photo / video : file uploads (future pipelines)

Telegram docs:
  - setWebhook: https://core.telegram.org/bots/api#setwebhook
  - Update:     https://core.telegram.org/bots/api#update
  - answerCallbackQuery: Must be called within 10s of button tap.
  - editMessageText: Replaces message content + removes buttons after decision.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from config.settings import settings
from services.telegram_subscriber_service import TelegramSubscriberService

try:
    from temporalio.client import Client as TemporalClient
    from temporalio.service import RPCError
except ImportError:  # pragma: no cover
    TemporalClient = None  # type: ignore
    RPCError = Exception  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def _tg_call(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Fire-and-forget call to Telegram Bot API."""
    url = f"{TELEGRAM_API_BASE}/{method}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
    data = resp.json()
    if not data.get("ok"):
        logger.warning("Telegram API %s failed: %s", method, data.get("description"))
    return data


async def answer_callback(callback_query_id: str, text: str = "") -> None:
    """
    Must be called within 10 seconds of receiving a callback_query.
    Clears the 'loading' spinner on the button.
    """
    await _tg_call(
        "answerCallbackQuery",
        {"callback_query_id": callback_query_id, "text": text},
    )


async def edit_message_text(
    chat_id: str | int,
    message_id: int,
    text: str,
    parse_mode: str = "MarkdownV2",
) -> None:
    """Replace message text and remove inline keyboard (no reply_markup sent)."""
    await _tg_call(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        },
    )


async def send_message(
    chat_id: str | int,
    text: str,
    parse_mode: str = "MarkdownV2",
    reply_markup: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Send a text message, optionally with inline keyboard."""
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _tg_call("sendMessage", payload)


def inline_keyboard(*rows: list[tuple[str, str]]) -> Dict[str, Any]:
    """
    Build an InlineKeyboardMarkup dict.

    Usage:
        inline_keyboard(
            [("✅ Yes", "approve_123"), ("❌ No", "reject_123")],
            [("⏭ Skip", "skip_123")],
        )
    """
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


# ---------------------------------------------------------------------------
# Secret verification
# ---------------------------------------------------------------------------

def _verify_telegram_secret(presented: Optional[str]) -> None:
    """
    Verify the X-Telegram-Bot-Api-Secret-Token header.

    Telegram sends this header with the value set during setWebhook.
    In dev (no secret configured) we skip verification.
    In production the header must match.
    """
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    if not secret:
        # Secret not configured — skip in dev, warn in production
        if settings.is_production_like:
            logger.warning(
                "TELEGRAM_WEBHOOK_SECRET is not set in a production-like environment. "
                "Webhook is unauthenticated."
            )
        return

    if not presented or not secrets.compare_digest(presented, secret):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")


# ---------------------------------------------------------------------------
# Update dispatcher
# ---------------------------------------------------------------------------

async def _handle_callback_query(callback_query: Dict[str, Any]) -> None:
    """
    Handle inline keyboard button taps.

    callback_data format: "<action>_<workflow_id_suffix>"
    Examples:
        post_tiktok_daily-story-2026-03-20
        post_shorts_daily-story-2026-03-20
        skip_daily-story-2026-03-20

    Known actions that route to DailyStoryWorkflow:
        post_tiktok, post_shorts, skip

    Other actions (status_check, help) are handled locally.
    """
    cq_id: str = callback_query["id"]
    chat_id: int = callback_query["message"]["chat"]["id"]
    message_id: int = callback_query["message"]["message_id"]
    data: str = callback_query.get("data", "")

    # ── 1. Answer immediately (10-second Telegram deadline) ─────────────────
    await answer_callback(cq_id)

    logger.info("callback_query: chat=%s data=%s", chat_id, data)

    # ── 2. Parse action + workflow_id ────────────────────────────────────────
    # Convention: "<action>_<wf_id>" where action can itself contain underscores
    # e.g. "post_tiktok_daily-story-2026-03-20"
    # Known two-word actions: post_tiktok, post_shorts
    KNOWN_TWO_WORD_ACTIONS = {"post_tiktok", "post_shorts"}
    parts = data.split("_", 2)  # max 3 parts
    if len(parts) >= 3 and f"{parts[0]}_{parts[1]}" in KNOWN_TWO_WORD_ACTIONS:
        action = f"{parts[0]}_{parts[1]}"
        workflow_id_suffix = parts[2] if len(parts) > 2 else ""
    else:
        action = parts[0]
        workflow_id_suffix = "_".join(parts[1:]) if len(parts) > 1 else ""

    # ── 3. Handle non-workflow actions locally ───────────────────────────────
    if action in ("status_check", "help"):
        help_text = (
            "*AI Influencer Bot Help*\n\n"
            "Every morning I send a travel story\. "
            "Tap *Post to TikTok*, *Post to Shorts*, or *Skip Today*\."
        )
        await edit_message_text(chat_id, message_id, help_text)
        return

    # ── 4. Story decision — signal the Temporal workflow ─────────────────────
    STORY_ACTIONS = {"post_tiktok", "post_shorts", "skip"}
    if action in STORY_ACTIONS:
        # Build the full workflow_id used when the cron was registered.
        # By convention: "daily-story-<workflow_id_suffix>"
        # If the suffix IS the full workflow_id (embedded by send_story_for_approval)
        # we use it directly.
        workflow_id = (
            f"daily-story-{workflow_id_suffix}"
            if workflow_id_suffix and not workflow_id_suffix.startswith("daily-story")
            else workflow_id_suffix
        )

        # Visual feedback first — don't wait for Temporal
        feedback_text = {
            "post_tiktok": "Posting to TikTok\.\.\.",
            "post_shorts": "Posting to YouTube Shorts\.\.\.",
            "skip":        "Skipped for today \u23ed",
        }[action]
        await edit_message_text(chat_id, message_id, feedback_text)

        if TemporalClient is not None and workflow_id:
            try:
                client = await TemporalClient.connect(
                    settings.TEMPORAL_ADDRESS,
                    namespace=settings.TEMPORAL_NAMESPACE,
                )
                handle = client.get_workflow_handle(workflow_id)
                await handle.signal(
                    "story_decision",
                    {"action": action, "chat_id": chat_id},
                )
                logger.info(
                    "Signalled workflow %s with action=%s", workflow_id, action
                )
            except RPCError as exc:
                logger.warning(
                    "Could not signal workflow %s: %s", workflow_id, exc
                )
            except Exception as exc:
                logger.error(
                    "Unexpected error signalling workflow %s: %s", workflow_id, exc
                )
        else:
            logger.warning(
                "Temporal client not available or workflow_id empty — signal skipped"
            )
        return

    # ── 5. Unknown action — acknowledge and log ──────────────────────────────
    logger.warning("Unknown callback action: %s (data=%s)", action, data)
    await edit_message_text(
        chat_id, message_id,
        f"Action received: `{_escape_md(data)}`",
    )


async def _handle_message(message: Dict[str, Any]) -> None:
    """
    Handle incoming messages (text, files, etc.).
    """
    chat_id: int = message["chat"]["id"]
    chat_type: str = message["chat"].get("type", "private")
    text: str = message.get("text", "")
    sender = message.get("from", {})
    username: Optional[str] = sender.get("username")
    first_name: Optional[str] = sender.get("first_name") or message["chat"].get("title")

    # ── Always update last_seen_at on any message ────────────────────────────
    try:
        await TelegramSubscriberService.touch(chat_id)
    except Exception:
        pass  # DB unavailable — still respond to user

    # File uploads
    has_file = any(k in message for k in ("document", "photo", "video", "audio"))

    if has_file:
        logger.info("File message received from chat=%s (pipeline pending)", chat_id)
        # TODO (Pipeline 1): IntakeWorkflow
        await send_message(
            chat_id,
            "File received\! Content pipelines coming soon\.",
        )
        return

    if text.startswith("/start"):
        # ── Upsert subscriber into DB ────────────────────────────────────────
        is_new = False
        try:
            existing = await TelegramSubscriberService.get_by_chat_id(chat_id)
            await TelegramSubscriberService.upsert(
                chat_id=chat_id,
                chat_type=chat_type,
                username=username,
                first_name=first_name,
            )
            is_new = existing is None
        except Exception as exc:
            logger.warning("Failed to upsert subscriber chat_id=%s: %s", chat_id, exc)

        greeting = "Welcome\!" if is_new else "Welcome back\!"
        await send_message(
            chat_id,
            (
                f"{greeting} *AI Influencer Bot* is online\!\n\n"
                "I will send you daily content for approval\. "
                "Tap a button when you receive a story to post it or skip it\.\n\n"
                "Your account has been registered \u2705"
            ),
            reply_markup=inline_keyboard(
                [("Status", "status_check"), ("Help", "help")],
            ),
        )
        return

    if text.startswith("http"):
        logger.info("URL received from chat=%s: %s (pipeline pending)", chat_id, text[:80])
        # TODO (Pipeline 2/3): AppReviewWorkflow or DriveEditWorkflow
        await send_message(
            chat_id,
            f"URL received\! URL pipelines coming soon\.\n`{_escape_md(text[:60])}`",
        )
        return

    logger.info("Text message from chat=%s: %s", chat_id, text[:80])
    await send_message(chat_id, "Message received\. Pipelines coming soon\!")


def _escape_md(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/telegram")
async def receive_telegram_update(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(
        default=None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
) -> Dict[str, Any]:
    """
    Main Telegram webhook endpoint.

    Telegram POSTs JSON Update objects here on every bot event.
    We respond with HTTP 200 immediately and process in the background
    (Telegram will retry if we don't respond within a few seconds).
    """
    _verify_telegram_secret(x_telegram_bot_api_secret_token)

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    update_id = payload.get("update_id")
    logger.debug("Telegram update received: update_id=%s", update_id)

    # Dispatch in background so we return 200 immediately
    if "callback_query" in payload:
        background_tasks.add_task(_handle_callback_query, payload["callback_query"])
    elif "message" in payload:
        background_tasks.add_task(_handle_message, payload["message"])
    else:
        logger.debug("Unhandled update type: %s", list(payload.keys()))

    # Telegram requires a 200 OK response; body content doesn't matter
    return {"ok": True}
