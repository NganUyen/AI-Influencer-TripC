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
async def generate_and_send_script_for_approval(
    config: Dict[str, Any],
) -> Dict[str, Any]:
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

    raise TimeoutError(
        f"Script approval timed out after {APPROVAL_TIMEOUT}s [{request_id}]"
    )


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

    [SAFETY-5] WARNING: This activity polls TelegramService for approval state.
    If Redis is not configured and the webhook/worker run in different processes,
    the callback will never reach this polling loop and the workflow will timeout.
    Ensure REDIS_URL is set in production for distributed deployments.
    """
    tg = TelegramService()

    # [SAFETY-5] Log warning if Redis is disabled
    if not TelegramService._redis_enabled:
        logger.warning(
            "APPROVAL STATE WARNING: Redis disabled for request_id=%s. "
            "If webhook and worker are separate processes, approval callbacks may not reach this activity. "
            "Set REDIS_URL to enable distributed approval state.",
            request_id,
        )

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


@activity.defn
async def generate_script_from_approved_package_activity(config: dict) -> dict:
    """
    Generate script from an approved package. Does NOT require human approval.

    [SAFETY] Validates package structure before processing to provide clear errors.
    """
    from services.script_service import ScriptService

    # [SAFETY] Validate required config keys
    if "approved_package" not in config:
        logger.error("Missing 'approved_package' in config: %s", list(config.keys()))
        raise ValueError("Missing 'approved_package' in activity config")

    app_name = config.get("app_name", "TripC")
    package = config["approved_package"]
    persona_config = config.get("persona_config", {})

    # [SAFETY] Validate package structure
    if not isinstance(package, dict):
        logger.error("approved_package is not a dict: type=%s", type(package).__name__)
        raise TypeError(f"approved_package must be dict, got {type(package).__name__}")

    beat_sheet = package.get("beat_sheet")
    if not beat_sheet:
        logger.error("Missing 'beat_sheet' in package: %s", list(package.keys()))
        raise ValueError("Missing 'beat_sheet' in approved_package")

    if not isinstance(beat_sheet, dict):
        logger.error("beat_sheet is not a dict: type=%s", type(beat_sheet).__name__)
        raise TypeError(f"beat_sheet must be dict, got {type(beat_sheet).__name__}")

    beats = beat_sheet.get("beats")
    if not beats:
        logger.error("Missing or empty 'beats' in beat_sheet")
        raise ValueError("Missing or empty 'beats' in beat_sheet")

    if not isinstance(beats, list):
        logger.error("beats is not a list: type=%s", type(beats).__name__)
        raise TypeError(f"beats must be list, got {type(beats).__name__}")

    concept_brief = package.get("concept_brief") or {}

    logger.info(
        "Generating script from approved package | app=%s | beats=%s | language=%s | has_reference_url=%s",
        app_name,
        len(beats),
        persona_config.get("language_name"),
        bool(concept_brief.get("reference_url")),
    )

    svc = ScriptService()
    try:
        contract = await svc.generate_script_from_package(
            app_name=app_name, package=package, persona_config=persona_config
        )
    except Exception as exc:
        logger.exception(
            "Failed to generate script from approved package | app=%s | beats=%s | reference_url=%s | error_type=%s",
            app_name,
            len(beats),
            concept_brief.get("reference_url"),
            type(exc).__name__,
        )
        raise

    return {"script_json": contract.model_dump(), "status": "ready"}


@activity.defn
async def send_telegram_progress_update(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a best-effort Telegram progress update for long-running video workflows.
    """
    chat_id = config.get("telegram_chat_id")
    if not chat_id:
        logger.warning("No telegram_chat_id provided — skipping progress notification")
        return {"status": "skipped", "reason": "no_chat_id"}

    workflow_id = config.get("workflow_id", "unknown")
    stage_label = str(config.get("stage_label") or "Workflow update").strip()
    details = str(config.get("details") or "").strip()

    progress_lines = [
        f"⏳ *{stage_label}*",
        f"• *Workflow ID*: `{workflow_id}`",
    ]
    if details:
        progress_lines.extend(["", details])

    tg = TelegramService()
    try:
        await tg.bot.send_message(
            chat_id=chat_id,
            text="\n".join(progress_lines),
            parse_mode="Markdown",
        )
        logger.info(
            "Progress notification sent | workflow_id=%s | stage=%s",
            workflow_id,
            stage_label,
        )
        return {"status": "sent", "chat_id": chat_id, "stage_label": stage_label}
    except Exception as exc:
        logger.warning(
            "Failed to send progress notification | workflow_id=%s | stage=%s | error=%s",
            workflow_id,
            stage_label,
            exc,
        )
        return {"status": "failed", "error": str(exc), "stage_label": stage_label}


@activity.defn
async def send_telegram_error_notification(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send error notification to user when workflow fails.
    Best-effort delivery — should not block workflow completion.
    """
    chat_id = config.get("telegram_chat_id")
    workflow_id = config.get("workflow_id", "unknown")
    topic = config.get("topic", "N/A")
    error_type = config.get("error_type", "UnknownError")
    error_summary = config.get("error_summary", "An unexpected error occurred")

    if not chat_id:
        logger.warning("No telegram_chat_id provided — skipping error notification")
        return {"status": "skipped", "reason": "no_chat_id"}

    tg = TelegramService()
    error_msg = (
        f"⚠️ *Video Generation Failed*\n\n"
        f"• *Topic*: {topic}\n"
        f"• *Workflow ID*: `{workflow_id}`\n"
        f"• *Error*: {error_type}\n\n"
        f"📝 *Details*: {error_summary}\n\n"
        "Our team has been notified. Please try again or contact support."
    )

    try:
        await tg.bot.send_message(
            chat_id=chat_id,
            text=error_msg,
            parse_mode="Markdown",
        )
        logger.info("Error notification sent to chat_id=%s", chat_id)
        return {"status": "sent", "chat_id": chat_id}
    except Exception as e:
        logger.error("Failed to send error notification: %s", e)
        return {"status": "failed", "error": str(e)}
