"""
Approval activities for Telegram-based human-in-the-loop steps.
"""

from typing import Any, Dict
import asyncio
import logging

from temporalio import activity

from services.contracts import ScriptContract
from services.errors import ScriptGenerationError
from services.script_service import ScriptService
from services.telegram_service import TelegramService
from config.settings import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5
APPROVAL_TIMEOUT = 1800
LEGACY_APPROVAL_TIMEOUT = max(settings.APPROVAL_TIMEOUT_DAYS, 1) * 24 * 60 * 60


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
            "Weekly Strategy Ready\n\n"
            f"User: `{user_id}`\n"
            f"Platforms: {', '.join(strategy.get('platforms', [])) or 'N/A'}\n\n"
            f"Plan Preview:\n{preview_text}\n\n"
            "Approve to continue with media generation and scheduling."
        ),
        buttons=[
            {"text": "Approve", "callback_data": f"approve_{chat_id}"},
            {"text": "Reject", "callback_data": f"reject_{chat_id}"},
        ],
    )


@activity.defn
async def wait_for_approval(request_id: str) -> Dict[str, Any]:
    """
    Legacy polling helper kept for compatibility with the original worker registry.
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
    Generate script and send it to Telegram for operator approval.
    """
    app_name = config["app_name"]
    topic = config["topic"]
    persona = config.get("persona_config", {})
    chat_id = config["telegram_chat_id"]
    model = config.get("model", "models/gemini-2.0-flash")

    logger.info(
        "Generating script | topic=%s | persona=%s",
        topic,
        persona.get("language_name"),
    )

    svc = ScriptService()
    try:
        contract: ScriptContract = await svc.generate_script_for_persona(
            app_name=app_name,
            topic=topic,
            persona_config=persona,
            model=model,
        )
    except ScriptGenerationError:
        raise

    scenes_text = "\n".join(
        [
            f"  [{scene.timestamp_start:.0f}s-{scene.timestamp_end:.0f}s] {scene.caption}"
            for scene in contract.scenes
        ]
    )
    approval_msg = (
        f"📝 *Script Review - {app_name}*\n\n"
        f"• *Topic*: {topic}\n"
        f"• *Duration*: {contract.duration_estimate:.0f}s\n\n"
        f"📖 *Script Preview*:\n`{contract.script[:300]}{'...' if len(contract.script) > 300 else ''}`\n\n"
        f"🎬 *Scenes* ({len(contract.scenes)}):\n```text\n{scenes_text}\n```\n"
        "Approve to start media generation? This will call TTS + fal.ai, and use HeyGen when a talking-head avatar is available."
    )

    tg = TelegramService()
    request_id = await tg.send_approval_request(
        user_id=chat_id,
        message=approval_msg,
        buttons=[
            {"text": "Approve & Generate", "callback_data": f"approve_{chat_id}"},
            {"text": "Reject", "callback_data": f"reject_{chat_id}"},
        ],
    )

    logger.info("Script sent for approval: request_id=%s", request_id)
    return {
        "request_id": request_id,
        "script_json": contract.model_dump(),
        "status": "sent",
    }


@activity.defn
async def wait_for_script_approval(request_id: str, chat_id: str) -> Dict[str, Any]:
    """
    Poll until operator approves or rejects.
    """
    tg = TelegramService()
    elapsed = 0

    while elapsed < APPROVAL_TIMEOUT:
        status = await tg.check_approval_status(request_id)

        if status.get("status") in ["approved", "rejected"]:
            logger.info(
                "Approval decision: %s | request=%s",
                status["status"],
                request_id,
            )
            return {
                "approved": status.get("approved", False),
                "feedback": status.get("feedback", ""),
                "status": status.get("status"),
            }

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(f"Script approval timed out after {APPROVAL_TIMEOUT}s [{request_id}]")


@activity.defn
async def send_preview_to_telegram(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send final video preview link via Telegram.
    """
    chat_id = config["telegram_chat_id"]
    video_url = config["video_url"]
    topic = config.get("topic", "N/A")
    persona_id = config.get("persona_id", "N/A")
    tone = config.get("tone", "N/A")
    platform = config.get("platform", "N/A")

    tg = TelegramService()
    preview_msg = (
        f"✨ *Final Video Ready!*\n\n"
        f"• *Persona*: {persona_id}\n"
        f"• *Topic*: {topic}\n"
        f"• *Tone*: {tone}\n"
        f"• *Platform*: {platform}\n\n"
        f"🔗 *Watch Preview*: {video_url}\n\n"
        "Choose final action:"
    )

    request_id = await tg.send_approval_request(
        user_id=chat_id,
        message=preview_msg,
        buttons=[
            {"text": "Save", "callback_data": f"save_{chat_id}"},
            {"text": "Discard", "callback_data": f"discard_{chat_id}"},
        ],
    )

    logger.info("Preview sent for decision: %s", request_id)
    return {"status": "sent", "request_id": request_id, "video_url": video_url}


@activity.defn
async def wait_for_publish_decision(request_id: str, chat_id: str) -> Dict[str, Any]:
    """
    Poll for final save/discard choice.
    """
    tg = TelegramService()
    elapsed = 0

    while elapsed < APPROVAL_TIMEOUT:
        status = await tg.check_approval_status(request_id)

        if status.get("status") in ["save", "discard"]:
            action = status.get("status")
            logger.info("Final video decision: %s", action)
            return {"action": action, "video_url": status.get("feedback", "")}

        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(f"Publish decision timed out [{request_id}]")
