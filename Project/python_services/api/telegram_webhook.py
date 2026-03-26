"""Telegram webhook router for daily-story callbacks and menu-driven skills."""

from __future__ import annotations

import logging
import secrets
import json
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from config.settings import settings
from services.skill_dispatcher import SkillDispatcher
from services.skill_session_store import TelegramSkillSessionStore
from services.telegram_renderer import TelegramRenderer
from services.telegram_service import TelegramService
from services.telegram_subscriber_service import TelegramSubscriberService
from services.openclaw_service import OpenClawService
from skills import SKILL_REGISTRY
from skills.definitions import get_skill_definition

try:
    from temporalio.client import Client as TemporalClient
    from temporalio.service import RPCError
except ImportError:  # pragma: no cover
    TemporalClient = None  # type: ignore
    RPCError = Exception  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter()

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


async def _tg_call(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/{method}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
    data = response.json()
    if not data.get("ok"):
        logger.warning("Telegram API %s failed: %s", method, data.get("description"))
    return data


async def _tg_call_multipart(
    method: str,
    payload: Dict[str, Any],
    files: Dict[str, tuple[str, bytes, str]],
) -> Dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/{method}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, data=payload, files=files)
    data = response.json()
    if not data.get("ok"):
        logger.warning("Telegram API %s (multipart) failed: %s", method, data.get("description"))
    return data


async def answer_callback(callback_query_id: str, text: str = "") -> None:
    await _tg_call(
        "answerCallbackQuery",
        {"callback_query_id": callback_query_id, "text": text},
    )


async def edit_message_text(
    chat_id: int | str,
    message_id: int,
    text: str,
    *,
    parse_mode: Optional[str] = "MarkdownV2",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await _tg_call("editMessageText", payload)


async def send_message(
    chat_id: int | str,
    text: str,
    *,
    parse_mode: Optional[str] = "MarkdownV2",
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _tg_call("sendMessage", payload)


async def send_photo(
    chat_id: int | str,
    photo: str,
    *,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "photo": photo,
    }
    if caption:
        payload["caption"] = caption
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup

    response = await _tg_call("sendPhoto", payload)
    if response.get("ok"):
        return response

    if not photo.startswith(("http://", "https://")):
        return response

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            image_response = await client.get(photo)
        image_response.raise_for_status()

        content_type = image_response.headers.get("content-type", "image/jpeg")
        parsed = urlparse(photo)
        filename = parsed.path.rsplit("/", 1)[-1] or "preview.jpg"
        if "." not in filename:
            filename = "preview.jpg"

        upload_payload: Dict[str, Any] = {
            "chat_id": chat_id,
        }
        if caption:
            upload_payload["caption"] = caption
        if parse_mode:
            upload_payload["parse_mode"] = parse_mode
        if reply_markup:
            upload_payload["reply_markup"] = reply_markup

        return await _tg_call_multipart(
            "sendPhoto",
            upload_payload,
            {"photo": (filename, image_response.content, content_type)},
        )
    except Exception as exc:
        logger.warning("Telegram sendPhoto URL fallback download/upload failed: %s", exc)
        return response


def inline_keyboard(*rows: list[tuple[str, str]]) -> Dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


def _escape_md(text: str) -> str:
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in special else char for char in text)


def _verify_telegram_secret(presented: Optional[str]) -> None:
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    if not secret:
        if settings.is_production_like:
            logger.warning(
                "TELEGRAM_WEBHOOK_SECRET is not set in a production-like environment. "
                "Webhook is unauthenticated."
            )
        return

    if not presented or not secrets.compare_digest(presented, secret):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret")


async def _send_rendered_message(
    chat_id: int,
    rendered: Dict[str, Any],
    *,
    message_id: Optional[int] = None,
) -> None:
    photo_url = rendered.get("photo_url")
    if photo_url:
        if message_id is not None:
            await edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=rendered["text"],
                parse_mode=rendered.get("parse_mode"),
                reply_markup=rendered.get("reply_markup"),
            )

        photo_result = await send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=rendered.get("photo_caption"),
            parse_mode=rendered.get("photo_parse_mode"),
        )
        if not photo_result.get("ok"):
            await send_message(
                chat_id=chat_id,
                text=rendered.get("photo_fallback_text") or f"Preview image URL:\n{photo_url}",
                parse_mode=None,
            )

        if message_id is None:
            await send_message(
                chat_id=chat_id,
                text=rendered["text"],
                parse_mode=rendered.get("parse_mode"),
                reply_markup=rendered.get("reply_markup"),
            )
        return

    if message_id is not None:
        await edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=rendered["text"],
            parse_mode=rendered.get("parse_mode"),
            reply_markup=rendered.get("reply_markup"),
        )
        return

    await send_message(
        chat_id=chat_id,
        text=rendered["text"],
        parse_mode=rendered.get("parse_mode"),
        reply_markup=rendered.get("reply_markup"),
    )


async def _handle_skill_callback(
    app: Any,
    chat_id: int,
    message_id: int,
    data: str,
) -> bool:
    if data.startswith("menu_"):
        rendered = TelegramRenderer.render_menu(data)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    if data.startswith("skill_"):
        skill_name = data.split("skill_", 1)[1]
        result = await SkillDispatcher.start_skill(chat_id, skill_name, app)
        rendered = TelegramRenderer.render_skill_result(result)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    if data.startswith("option::"):
        value = data.split("::", 1)[1]
        result = await SkillDispatcher.handle_option(chat_id, value, app)
        rendered = TelegramRenderer.render_skill_result(result)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    if data.startswith("action::"):
        action = data.split("::", 1)[1]
        result = await SkillDispatcher.handle_action(chat_id, action, app)
        rendered = TelegramRenderer.render_skill_result(result)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    if data.startswith("info::"):
        skill_name = data.split("::", 1)[1]
        rendered = TelegramRenderer.render_catalog_info(skill_name)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    return False


def _system_status_text() -> str:
    return (
        "TripC Bot Status\n\n"
        "Live now:\n"
        "- Marketing Poster\n"
        "- Scene Batch\n"
        "- Carousel\n"
        "- Publish Queue\n"
        "- Persona create / inspect\n"
        "- Quota and Weekly Plan\n\n"
        "Beta / partial:\n"
        "- AI Influencer video\n"
        "- Avatar-related persona tooling\n\n"
        "Planned next:\n"
        "- Tutorial video\n"
        "- Long post workflow\n\n"
        "Use /media to open the studio."
    )


def _help_text() -> str:
    return (
        "TripC Bot Help\n\n"
        "Use /media to open the studio menu.\n"
        "Or send a normal message to chat with OpenClaw AI.\n"
        "Images: poster or scene batch.\n"
        "Video: AI influencer lane.\n"
        "Content: carousel and publish queue.\n"
        "Manage: personas, quota, weekly planning.\n\n"
        "Telegram also stays active for workflow approvals and daily story actions."
    )


def _extract_openclaw_reply(result: Any) -> str:
    if isinstance(result, dict):
        text = result.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

        output = result.get("output")
        if isinstance(output, str) and output.strip():
            return output.strip()

        nested_result = result.get("result")
        if isinstance(nested_result, str) and nested_result.strip():
            return nested_result.strip()
        if isinstance(nested_result, dict):
            nested_text = nested_result.get("text")
            if isinstance(nested_text, str) and nested_text.strip():
                return nested_text.strip()

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if isinstance(result, str) and result.strip():
        return result.strip()

    return "I could not generate a response. Please try again."


def _skill_catalog_for_agent() -> list[Dict[str, str]]:
    catalog: list[Dict[str, str]] = []
    for skill_name in sorted(SKILL_REGISTRY.keys()):
        definition = get_skill_definition(skill_name) or {}
        catalog.append(
            {
                "skill_name": skill_name,
                "description": str(definition.get("description") or "").strip(),
            }
        )
    return catalog


def _extract_agent_decision(result: Any) -> Optional[Dict[str, str]]:
    payload: Dict[str, Any] | None = result if isinstance(result, dict) else None

    if payload is None and isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = None

    if payload is None:
        return None

    action = payload.get("action")
    skill_name = payload.get("skill_name")
    reply = payload.get("reply")

    if isinstance(action, str) and action in {"chat", "start_skill"}:
        return {
            "action": action,
            "skill_name": str(skill_name or "").strip(),
            "reply": str(reply or "").strip(),
        }

    text = payload.get("text")
    if isinstance(text, str):
        try:
            parsed_text = json.loads(text)
            if isinstance(parsed_text, dict):
                parsed_action = parsed_text.get("action")
                if isinstance(parsed_action, str) and parsed_action in {"chat", "start_skill"}:
                    return {
                        "action": parsed_action,
                        "skill_name": str(parsed_text.get("skill_name") or "").strip(),
                        "reply": str(parsed_text.get("reply") or "").strip(),
                    }
        except json.JSONDecodeError:
            return None

    return None


async def _handle_openclaw_message(chat_id: int, text: str, app: Any) -> None:
    service = OpenClawService()
    try:
        catalog_json = json.dumps(_skill_catalog_for_agent(), ensure_ascii=False)
        agent_prompt = (
            "You are the Telegram orchestrator for TripC. "
            "Decide whether to start one of the available skills or answer in chat.\n\n"
            "Return ONLY strict JSON with this exact schema:\n"
            "{\"action\":\"chat|start_skill\",\"skill_name\":\"<skill-or-empty>\",\"reply\":\"<short-plain-text-reply>\"}\n\n"
            "Rules:\n"
            "- Use action=start_skill only when user clearly asks for task execution/content generation.\n"
            "- If starting skill, choose one from available_skills exactly.\n"
            "- Keep reply concise and plain text.\n"
            "- Never output markdown fences.\n\n"
            f"available_skills={catalog_json}\n"
            f"user_message={text}"
        )
        result = await service.execute_task(
            task_type="telegram_agent_router",
            prompt=agent_prompt,
            user_id=f"telegram:{chat_id}",
            context={"source": "telegram", "chat_id": str(chat_id)},
        )

        decision = _extract_agent_decision(result)
        if decision and decision.get("action") == "start_skill":
            skill_name = decision.get("skill_name", "")
            if skill_name in SKILL_REGISTRY:
                skill_result = await SkillDispatcher.start_skill(chat_id, skill_name, app)
                rendered = TelegramRenderer.render_skill_result(skill_result)
                await _send_rendered_message(chat_id, rendered)
                return

        if decision and decision.get("reply"):
            reply = decision["reply"]
        else:
            reply = _extract_openclaw_reply(result)

        if len(reply) > 3500:
            reply = f"{reply[:3500]}\n\n…(truncated)"
        await send_message(chat_id, reply, parse_mode=None)
    except Exception:
        logger.exception("OpenClaw Telegram chat failed for chat_id=%s", chat_id)
        await send_message(
            chat_id,
            "AI assistant is temporarily unavailable. Please try again in a moment.",
            parse_mode=None,
        )
    finally:
        await service.close()


async def _handle_system_callback(
    chat_id: int,
    message_id: int,
    data: str,
) -> bool:
    if data == "status_check":
        await edit_message_text(
            chat_id,
            message_id,
            _system_status_text(),
            parse_mode=None,
            reply_markup=inline_keyboard(
                [("Open Studio", "menu_main"), ("Help", "help")],
            ),
        )
        return True

    if data == "help":
        await edit_message_text(
            chat_id,
            message_id,
            _help_text(),
            parse_mode=None,
            reply_markup=inline_keyboard(
                [("Open Studio", "menu_main"), ("Status", "status_check")],
            ),
        )
        return True

    return False


async def _handle_approval_callback(
    chat_id: int,
    message_id: int,
    data: str,
) -> bool:
    if not data.startswith(("approve_", "reject_", "edit_", "save_", "discard_")):
        return False

    request_id = f"{chat_id}_{message_id}"
    text = await TelegramService.apply_callback_payload(request_id, data)
    await edit_message_text(
        chat_id,
        message_id,
        text or "Approval request not found.",
        parse_mode=None,
    )
    return True


async def _handle_story_callback(
    chat_id: int,
    message_id: int,
    data: str,
) -> bool:
    if data in {"status_check", "help"}:
        help_text = (
            "AI Influencer Bot Help\n\n"
            "Every morning I send a travel story. "
            "Tap Post to TikTok, Post to Shorts, or Skip Today."
        )
        await edit_message_text(chat_id, message_id, help_text, parse_mode=None)
        return True

    parts = data.split("_", 2)
    known_two_word_actions = {"post_tiktok", "post_shorts"}
    if len(parts) >= 3 and f"{parts[0]}_{parts[1]}" in known_two_word_actions:
        action = f"{parts[0]}_{parts[1]}"
        workflow_id_suffix = parts[2]
    else:
        action = parts[0]
        workflow_id_suffix = "_".join(parts[1:]) if len(parts) > 1 else ""

    story_actions = {"post_tiktok", "post_shorts", "skip"}
    if action not in story_actions:
        return False

    workflow_id = (
        f"daily-story-{workflow_id_suffix}"
        if workflow_id_suffix and not workflow_id_suffix.startswith("daily-story")
        else workflow_id_suffix
    )
    feedback_text = {
        "post_tiktok": "Posting to TikTok...",
        "post_shorts": "Posting to YouTube Shorts...",
        "skip": "Skipped for today.",
    }[action]
    await edit_message_text(chat_id, message_id, feedback_text, parse_mode=None)

    if TemporalClient is not None and workflow_id:
        try:
            client = await TemporalClient.connect(
                settings.TEMPORAL_ADDRESS,
                namespace=settings.TEMPORAL_NAMESPACE,
            )
            handle = client.get_workflow_handle(workflow_id)
            await handle.signal("story_decision", {"action": action, "chat_id": chat_id})
            logger.info("Signalled workflow %s with action=%s", workflow_id, action)
        except RPCError as exc:
            logger.warning("Could not signal workflow %s: %s", workflow_id, exc)
        except Exception as exc:
            logger.error("Unexpected error signalling workflow %s: %s", workflow_id, exc)
    else:
        logger.warning("Temporal unavailable or workflow_id empty; story signal skipped.")
    return True


async def _handle_callback_query(app: Any, callback_query: Dict[str, Any]) -> None:
    callback_id = callback_query["id"]
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"]["message_id"]
    data = callback_query.get("data", "")

    await answer_callback(callback_id)
    logger.info("callback_query: chat=%s data=%s", chat_id, data)

    if await _handle_skill_callback(app, chat_id, message_id, data):
        return
    if await _handle_system_callback(chat_id, message_id, data):
        return
    if await _handle_approval_callback(chat_id, message_id, data):
        return
    if await _handle_story_callback(chat_id, message_id, data):
        return

    logger.warning("Unknown callback action: %s", data)
    await edit_message_text(
        chat_id,
        message_id,
        f"Action received: `{_escape_md(data)}`",
    )


async def _handle_message(app: Any, message: Dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    chat_type = message["chat"].get("type", "private")
    text = message.get("text", "")
    sender = message.get("from", {})
    username: Optional[str] = sender.get("username")
    first_name: Optional[str] = sender.get("first_name") or message["chat"].get("title")

    try:
        await TelegramSubscriberService.touch(chat_id)
    except Exception:
        pass

    has_file = any(key in message for key in ("document", "photo", "video", "audio"))
    if has_file:
        await send_message(
            chat_id,
            "File received. Content pipelines coming soon.",
            parse_mode=None,
        )
        return

    if text.startswith("/start"):
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

        greeting = "Welcome!" if is_new else "Welcome back!"
        await send_message(
            chat_id,
            (
                f"{greeting} AI Influencer Bot is online.\n\n"
                "Use /media to open the studio menu, or wait for daily story approvals."
            ),
            parse_mode=None,
            reply_markup=inline_keyboard(
                [("Open Studio", "menu_main"), ("Status", "status_check")],
                [("Help", "help")],
            ),
        )
        return

    if text.startswith("/media"):
        await TelegramSkillSessionStore.clear_session(chat_id)
        rendered = TelegramRenderer.render_menu("menu_main")
        await _send_rendered_message(chat_id, rendered)
        return

    if text.startswith("/cancel"):
        await TelegramSkillSessionStore.clear_session(chat_id)
        await send_message(chat_id, "Cancelled the active skill session.", parse_mode=None)
        return

    skill_result = await SkillDispatcher.handle_text(chat_id, text, app)
    if skill_result is not None:
        rendered = TelegramRenderer.render_skill_result(skill_result)
        await _send_rendered_message(chat_id, rendered)
        return

    if text.startswith("http"):
        await send_message(
            chat_id,
            f"URL received. URL pipelines coming soon.\n{text[:60]}",
            parse_mode=None,
        )
        return

    if text.strip():
        await _handle_openclaw_message(chat_id, text.strip(), app)
        return

    await send_message(chat_id, "Please send a text message.", parse_mode=None)


@router.post("/telegram")
async def receive_telegram_update(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
) -> Dict[str, Any]:
    _verify_telegram_secret(x_telegram_bot_api_secret_token)

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if "callback_query" in payload:
        background_tasks.add_task(_handle_callback_query, request.app, payload["callback_query"])
    elif "message" in payload:
        background_tasks.add_task(_handle_message, request.app, payload["message"])
    else:
        logger.debug("Unhandled Telegram update type: %s", list(payload.keys()))

    return {"ok": True}
