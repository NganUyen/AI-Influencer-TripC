"""
Approval Activities (TripC v2)
================================
Handles human-in-the-loop: Telegram script approval + preview/publish.

Phase D: Script approval via Telegram before expensive media generation.
Phase E: Preview send after render, publish trigger via Postiz.
"""
from temporalio import activity
from typing import Dict, Any
import asyncio
import logging

from services.telegram_service import TelegramService
from services.script_service import ScriptService
from services.contracts import ScriptContract
from services.errors import ScriptGenerationError
from config.settings import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5   # seconds between approval status checks
APPROVAL_TIMEOUT = 1800  # 30 minutes max wait for human
LEGACY_APPROVAL_TIMEOUT = max(settings.APPROVAL_TIMEOUT_DAYS, 1) * 24 * 60 * 60


# ─── Phase D: Script Generation + Telegram Approval ─────────────────────────


@activity.defn
async def send_telegram_approval_request(user_id: str, strategy: Dict[str, Any]) -> str:
    """
    Legacy weekly-workflow approval activity kept for compatibility.
    """
    daily_content = strategy.get("strategy", {}).get("daily_content", [])
    preview_lines = []
    for day_idx, item in enumerate(daily_content[:7], start=1):
        theme = item.get("theme") or item.get("message") or "Untitled"
        preview_lines.append(f"{day_idx}. {theme}")

    preview_text = "\n".join(preview_lines) or "No daily content was generated."
    chat_id = (
        strategy.get("brand_config", {}).get("telegram_chat_id")
        or settings.TELEGRAM_CHAT_ID
        or user_id
    )

    tg = TelegramService()
    return await tg.send_approval_request(
        user_id=chat_id,
        message=(
            "📅 *Weekly Strategy Ready*\n\n"
            f"*User:* `{user_id}`\n"
            f"*Platforms:* {', '.join(strategy.get('platforms', [])) or 'N/A'}\n\n"
            f"*Plan Preview:*\n{preview_text}\n\n"
            "Approve to continue with media generation and scheduling."
        ),
        buttons=[
            {"text": "✅ Approve", "callback_data": f"approve_{chat_id}"},
            {"text": "❌ Reject", "callback_data": f"reject_{chat_id}"},
        ],
    )


@activity.defn
async def wait_for_approval(request_id: str) -> Dict[str, Any]:
    """
    Legacy polling helper kept for compatibility with the original worker
    activity registry.
    """
    tg = TelegramService()
    elapsed = 0

    while elapsed < LEGACY_APPROVAL_TIMEOUT:
        status = await tg.check_approval_status(request_id)
        if status.get("status") in ["approved", "rejected"]:
            return {
                "approved": status.get("approved", False),
                "feedback": status.get("feedback", ""),
                "status": status.get("status"),
            }

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(
        f"Approval timed out after {LEGACY_APPROVAL_TIMEOUT}s [{request_id}]"
    )

@activity.defn
async def generate_and_send_script_for_approval(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase D1: Generate script with Gemini and send to Telegram for operator approval.

    Input config:
        app_name: str
        topic: str
        persona_config: dict  (language_name, voice, etc.)
        telegram_chat_id: str
        model: str (optional)

    Returns:
        request_id: str     — track approval in check_script_approval
        script_json: dict   — serialized ScriptContract
        status: "sent"
    """
    app_name = config["app_name"]
    topic = config["topic"]
    persona = config.get("persona_config", {})
    chat_id = config["telegram_chat_id"]
    model = config.get("model", "models/gemini-2.0-flash")

    logger.info(f"Generating script | topic={topic} | persona={persona.get('language_name')}")

    svc = ScriptService()
    try:
        contract: ScriptContract = await svc.generate_script_for_persona(
            app_name=app_name,
            topic=topic,
            persona_config=persona,
            model=model,
        )
    except ScriptGenerationError as e:
        raise  # Let Temporal retry

    # Format approval message
    scenes_text = "\n".join(
        [f"  [{s.timestamp_start:.0f}s-{s.timestamp_end:.0f}s] {s.caption}" for s in contract.scenes]
    )
    approval_msg = (
        f"🎬 *Script Review — {app_name}*\n\n"
        f"📝 *Topic:* {topic}\n"
        f"⏱ *Duration:* {contract.duration_estimate:.0f}s\n\n"
        f"*Script Preview:*\n{contract.script[:300]}{'...' if len(contract.script) > 300 else ''}\n\n"
        f"*Scenes ({len(contract.scenes)}):*\n{scenes_text}\n\n"
        f"Approve to start media generation? This will call TTS + fal.ai + HeyGen."
    )

    tg = TelegramService()
    request_id = await tg.send_approval_request(
        user_id=chat_id,
        message=approval_msg,
        buttons=[
            {"text": "✅ Approve & Generate", "callback_data": f"approve_{chat_id}"},
            {"text": "❌ Reject", "callback_data": f"reject_{chat_id}"},
        ],
    )

    logger.info(f"Script sent for approval: request_id={request_id}")
    return {
        "request_id": request_id,
        "script_json": contract.model_dump(),
        "status": "sent",
    }


@activity.defn
async def wait_for_script_approval(request_id: str, chat_id: str) -> Dict[str, Any]:
    """
    Phase D2: Poll until operator approves or rejects.
    Raises TimeoutError if no response within APPROVAL_TIMEOUT.

    Returns:
        approved: bool
        feedback: str
    """
    tg = TelegramService()
    elapsed = 0

    while elapsed < APPROVAL_TIMEOUT:
        status = await tg.check_approval_status(request_id)

        if status.get("status") in ["approved", "rejected"]:
            logger.info(f"Approval decision: {status['status']} | request={request_id}")
            return {
                "approved": status.get("approved", False),
                "feedback": status.get("feedback", ""),
                "status": status.get("status"),
            }

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(f"Script approval timed out after {APPROVAL_TIMEOUT}s [{request_id}]")


# ─── Phase E: Send Preview + Trigger Publish ─────────────────────────────────

@activity.defn
async def send_preview_to_telegram(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase E1: Send final video preview link via Telegram.

    Input config:
        telegram_chat_id: str
        video_url: str
        topic: str
        persona_id: str

    Returns:
        status: "sent"
    """
    chat_id = config["telegram_chat_id"]
    video_url = config["video_url"]
    topic = config.get("topic", "")
    persona_id = config.get("persona_id", "")

    tg = TelegramService()

    preview_msg = (
        f"🎉 *Video Ready!*\n\n"
        f"📌 Topic: {topic}\n"
        f"👤 Persona: {persona_id}\n\n"
        f"🔗 [Watch Preview]({video_url})\n\n"
        f"Choose action to publish:"
    )

    request_id = await tg.send_approval_request(
        user_id=chat_id,
        message=preview_msg,
        buttons=[
            {"text": "🚀 Publish TikTok", "callback_data": f"publish_tiktok_{chat_id}"},
            {"text": "📺 Publish Shorts", "callback_data": f"publish_shorts_{chat_id}"},
            {"text": "⏰ Schedule Later", "callback_data": f"schedule_{chat_id}"},
            {"text": "🗑 Discard", "callback_data": f"discard_{chat_id}"},
        ],
    )

    logger.info(f"Preview sent for approval: {request_id}")
    return {"status": "sent", "request_id": request_id, "video_url": video_url}


@activity.defn
async def wait_for_publish_decision(request_id: str, chat_id: str) -> Dict[str, Any]:
    """
    Phase E2: Poll for publish action choice.

    Returns:
        action: "publish_tiktok" | "publish_shorts" | "schedule" | "discard"
    """
    tg = TelegramService()
    elapsed = 0

    while elapsed < APPROVAL_TIMEOUT:
        status = await tg.check_approval_status(request_id)

        if status.get("status") in ["approved", "rejected"]:
            # Infer action from callback_data (stored in status)
            feedback = status.get("feedback", "")
            action = "discard"
            if "tiktok" in feedback:
                action = "publish_tiktok"
            elif "shorts" in feedback:
                action = "publish_shorts"
            elif "schedule" in feedback:
                action = "schedule"
            elif status.get("approved"):
                action = "publish_tiktok"  # default if approved

            logger.info(f"Publish decision: {action}")
            return {"action": action, "video_url": status.get("feedback", "")}

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(f"Publish decision timed out [{request_id}]")
