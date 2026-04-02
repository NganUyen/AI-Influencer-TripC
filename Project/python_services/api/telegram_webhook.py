"""Telegram webhook router for daily-story callbacks and menu-driven skills."""

from __future__ import annotations

import logging
import secrets
import json
import asyncio
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
from services.telegram_link_service import TelegramLinkError, TelegramLinkService
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
_TELEGRAM_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


def _get_telegram_http_client() -> httpx.AsyncClient:
    global _TELEGRAM_HTTP_CLIENT
    if _TELEGRAM_HTTP_CLIENT is None:
        _TELEGRAM_HTTP_CLIENT = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            follow_redirects=False,
        )
    return _TELEGRAM_HTTP_CLIENT


async def _tg_call(method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/{method}"
    client = _get_telegram_http_client()
    response = await client.post(url, json=payload, timeout=10.0)
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
    client = _get_telegram_http_client()
    response = await client.post(url, data=payload, files=files, timeout=20.0)
    data = response.json()
    if not data.get("ok"):
        logger.warning(
            "Telegram API %s (multipart) failed: %s", method, data.get("description")
        )
    return data


async def send_chat_action(chat_id: int | str, action: str = "typing") -> None:
    await _tg_call(
        "sendChatAction",
        {
            "chat_id": chat_id,
            "action": action,
        },
    )


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
        client = _get_telegram_http_client()
        image_response = await client.get(photo, timeout=20.0, follow_redirects=True)
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
        logger.warning(
            "Telegram sendPhoto URL fallback download/upload failed: %s", exc
        )
        return response


def _telegram_file_download_url(file_path: str) -> str:
    return f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path.lstrip('/')}"


async def _download_telegram_image(
    message: Dict[str, Any],
) -> Optional[tuple[bytes, str, str]]:
    photo_entries = message.get("photo") or []
    document = message.get("document")

    file_id: Optional[str] = None
    filename = "telegram-upload.jpg"
    content_type = "image/jpeg"

    if isinstance(photo_entries, list) and photo_entries:
        largest = photo_entries[-1]
        file_id = largest.get("file_id")
        unique_id = largest.get("file_unique_id") or largest.get("file_id") or "upload"
        filename = f"telegram-{unique_id}.jpg"
        content_type = "image/jpeg"
    elif isinstance(document, dict):
        document_mime = str(document.get("mime_type") or "").strip().lower()
        if not document_mime.startswith("image/"):
            return None
        file_id = document.get("file_id")
        filename = document.get("file_name") or "telegram-upload"
        content_type = document_mime or "image/jpeg"
    else:
        return None

    if not file_id:
        return None

    file_response = await _tg_call("getFile", {"file_id": file_id})
    file_path = file_response.get("result", {}).get("file_path")
    if not file_path:
        logger.warning("Telegram getFile returned no file_path for file_id=%s", file_id)
        return None

    download_url = _telegram_file_download_url(file_path)
    client = _get_telegram_http_client()
    response = await client.get(download_url, timeout=30.0, follow_redirects=True)
    response.raise_for_status()
    return response.content, content_type, filename


async def _download_telegram_video(
    message: Dict[str, Any],
) -> Optional[tuple[bytes, str, str]]:
    """
    Download video file from Telegram message.

    Returns:
        tuple of (file_content, content_type, filename) or None if no video found
    """
    video = message.get("video")
    document = message.get("document")

    file_id: Optional[str] = None
    filename = "telegram-video.mp4"
    content_type = "video/mp4"

    if isinstance(video, dict):
        file_id = video.get("file_id")
        unique_id = video.get("file_unique_id") or video.get("file_id") or "upload"
        filename = f"telegram-video-{unique_id}.mp4"
        content_type = video.get("mime_type") or "video/mp4"
    elif isinstance(document, dict):
        document_mime = str(document.get("mime_type") or "").strip().lower()
        if not document_mime.startswith("video/"):
            return None
        file_id = document.get("file_id")
        filename = document.get("file_name") or "telegram-video"
        content_type = document_mime or "video/mp4"
    else:
        return None

    if not file_id:
        return None

    file_response = await _tg_call("getFile", {"file_id": file_id})
    file_path = file_response.get("result", {}).get("file_path")
    if not file_path:
        logger.warning(
            "Telegram getFile returned no file_path for video file_id=%s", file_id
        )
        return None

    download_url = _telegram_file_download_url(file_path)
    client = _get_telegram_http_client()

    # Use longer timeout for video files (they can be larger)
    response = await client.get(download_url, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    return response.content, content_type, filename


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
    text = rendered.get("text") or "Done."
    reply_markup = rendered.get("reply_markup")
    parse_mode = rendered.get("parse_mode")

    # 1. Clear placeholder if present
    if message_id is not None:
        try:
            # We prefer deleting the "Processing..." text for a cleaner look when photos arrive
            await _tg_call(
                "deleteMessage", {"chat_id": chat_id, "message_id": message_id}
            )
            message_id = None  # Message is gone, future calls should use send_message
        except Exception:
            # Fallback: Edit the text to a neutral state if delete fails
            try:
                await edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="✨ Processing done...",
                )
            except Exception:
                pass

    # 2. Try sending photo if present
    photo_sent = False
    if photo_url:
        try:
            photo_result = await send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=rendered.get("photo_caption") or text[:1024],
                parse_mode=rendered.get("photo_parse_mode") or parse_mode,
                reply_markup=reply_markup if not text or len(text) < 200 else None,
            )
            if photo_result.get("ok"):
                photo_sent = True
        except Exception as exc:
            logger.warning("Failed to send photo: %s", exc)

    # 3. Send text message if photo failed, or if text is long, or if no photo at all
    # We always send the full text message if it's long or if photo wasn't sent
    if not photo_sent or (text and len(text) > 200):
        if message_id is not None:
            try:
                await edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
            except Exception:
                await send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                )
        else:
            await send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )


async def _await_with_callback_progress(
    chat_id: int,
    message_id: int,
    work_coro: Any,
    *,
    timeout_seconds: float = 0.6,
) -> Any:
    task = asyncio.create_task(work_coro)
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        await edit_message_text(
            chat_id,
            message_id,
            "Processing your request...",
            parse_mode=None,
        )
        try:
            return await task
        except Exception as exc:
            logger.exception(
                "Skill callback processing failed for chat_id=%s: %s", chat_id, exc
            )
            await edit_message_text(
                chat_id,
                message_id,
                "Something went wrong while processing this step. Please try again or send /cancel.",
                parse_mode=None,
            )
            return None
    except Exception as exc:
        logger.exception(
            "Skill callback processing failed for chat_id=%s: %s", chat_id, exc
        )
        await edit_message_text(
            chat_id,
            message_id,
            "Something went wrong while processing this step. Please try again or send /cancel.",
            parse_mode=None,
        )
        return None


async def _await_with_message_progress(
    chat_id: int,
    work_coro: Any,
    *,
    timeout_seconds: float = 0.8,
) -> tuple[Any, Optional[int]]:
    task = asyncio.create_task(work_coro)
    try:
        result = await asyncio.wait_for(asyncio.shield(task), timeout=timeout_seconds)
        return result, None
    except asyncio.TimeoutError:
        waiting_message_id: Optional[int] = None
        try:
            waiting = await send_message(
                chat_id,
                "Processing your request...",
                parse_mode=None,
            )
            waiting_message_id = waiting.get("result", {}).get("message_id")
        except Exception:
            logger.debug("Failed to send progress message for chat_id=%s", chat_id)
        try:
            result = await task
            return result, waiting_message_id
        except Exception as exc:
            logger.exception(
                "Skill text processing failed for chat_id=%s: %s", chat_id, exc
            )
            if waiting_message_id is not None:
                try:
                    await edit_message_text(
                        chat_id,
                        waiting_message_id,
                        "Something went wrong while processing your request. Please try again or send /cancel.",
                        parse_mode=None,
                    )
                except Exception:
                    await send_message(
                        chat_id,
                        "Something went wrong while processing your request. Please try again or send /cancel.",
                        parse_mode=None,
                    )
            else:
                await send_message(
                    chat_id,
                    "Something went wrong while processing your request. Please try again or send /cancel.",
                    parse_mode=None,
                )
            return None, waiting_message_id
    except Exception as exc:
        logger.exception(
            "Skill text processing failed for chat_id=%s: %s", chat_id, exc
        )
        try:
            await send_message(
                chat_id,
                "Something went wrong while processing your request. Please try again or send /cancel.",
                parse_mode=None,
            )
        except Exception:
            logger.debug(
                "Failed to send fallback error message for chat_id=%s", chat_id
            )
        return None, None


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

        # All skills (including video-ai) start directly for deterministic UI actions.
        # OpenClaw routing is reserved for free-text conversational input only.
        await TelegramSkillSessionStore.clear_session(chat_id)
        result = await _await_with_callback_progress(
            chat_id,
            message_id,
            SkillDispatcher.start_skill(chat_id, skill_name, app),
        )
        if result is None:
            return True
        rendered = TelegramRenderer.render_skill_result(result)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    if data.startswith("option::"):
        value = data.split("::", 1)[1]
        result = await _await_with_callback_progress(
            chat_id,
            message_id,
            SkillDispatcher.handle_option(chat_id, value, app),
        )
        if result is None:
            return True
        rendered = TelegramRenderer.render_skill_result(result)
        await _send_rendered_message(chat_id, rendered, message_id=message_id)
        return True

    if data.startswith("action::"):
        action = data.split("::", 1)[1]
        result = await _await_with_callback_progress(
            chat_id,
            message_id,
            SkillDispatcher.handle_action(chat_id, action, app),
        )
        if result is None:
            return True
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
        "Or send a normal message to chat with OpenClaw AI.\n\n"
        "Commands:\n"
        "  /start — Welcome / onboarding\n"
        "  /media — Open studio\n"
        "  /create_video — Start AI video creation\n"
        "  /create_image — Create marketing images\n"
        "  /personas — Inspect your personas\n"
        "  /quota — Check usage quota\n"
        "  /cancel — Cancel active flow\n\n"
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
                if isinstance(parsed_action, str) and parsed_action in {
                    "chat",
                    "start_skill",
                }:
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
            '{"action":"chat|start_skill","skill_name":"<skill-or-empty>","reply":"<short-plain-text-reply>"}\n\n'
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
                skill_result = await SkillDispatcher.start_skill(
                    chat_id, skill_name, app
                )
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
            await handle.signal(
                "story_decision", {"action": action, "chat_id": chat_id}
            )
            logger.info("Signalled workflow %s with action=%s", workflow_id, action)
        except RPCError as exc:
            logger.warning("Could not signal workflow %s: %s", workflow_id, exc)
        except Exception as exc:
            logger.error(
                "Unexpected error signalling workflow %s: %s", workflow_id, exc
            )
    else:
        logger.warning(
            "Temporal unavailable or workflow_id empty; story signal skipped."
        )
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

    touch_results = await asyncio.gather(
        TelegramSubscriberService.touch(chat_id),
        TelegramLinkService.touch_link(
            chat_id=chat_id,
            telegram_username=username,
        ),
        return_exceptions=True,
    )
    for touch_result in touch_results:
        if isinstance(touch_result, Exception):
            logger.debug("Telegram touch failed: %s", touch_result)

    has_file = any(key in message for key in ("document", "photo", "video", "audio"))
    if has_file:
        # Check if this is a video upload for video-ai skill
        has_video = "video" in message or (
            isinstance(message.get("document"), dict)
            and str(message["document"].get("mime_type", "")).startswith("video/")
        )

        if has_video:
            active_session = await TelegramSkillSessionStore.get_session(chat_id)
            if (
                active_session is not None
                and active_session.skill_name == "video-ai"
                and active_session.step_key == "upload_demo_video"
            ):
                await send_chat_action(chat_id, action="upload_video")
                try:
                    telegram_video = await _download_telegram_video(message)
                except Exception as exc:
                    logger.warning(
                        "Telegram video download failed for chat_id=%s: %s",
                        chat_id,
                        exc,
                    )
                    telegram_video = None

                if telegram_video is not None:
                    video_bytes, content_type, filename = telegram_video

                    # Extract file_id for storage
                    video_obj = message.get("video")
                    document_obj = message.get("document")
                    file_id = None
                    if video_obj:
                        file_id = video_obj.get("file_id")
                    elif document_obj:
                        file_id = document_obj.get("file_id")

                    if not file_id:
                        await send_message(
                            chat_id,
                            "Could not process video file. Please try uploading again.",
                            parse_mode=None,
                        )
                        return

                    skill_result = await SkillDispatcher.handle_video_upload(
                        chat_id,
                        file_id=file_id,
                        data=video_bytes,
                        content_type=content_type,
                        filename=filename,
                        app=app,
                    )
                    if skill_result is not None:
                        rendered = TelegramRenderer.render_skill_result(skill_result)
                        await _send_rendered_message(chat_id, rendered)
                        return

                await send_message(
                    chat_id,
                    "Video download failed. Please try uploading again or send /cancel to restart.",
                    parse_mode=None,
                )
                return

        # Handle image uploads
        await send_chat_action(chat_id, action="upload_photo")
        try:
            telegram_image = await _download_telegram_image(message)
        except Exception as exc:
            logger.warning(
                "Telegram image download failed for chat_id=%s: %s", chat_id, exc
            )
            telegram_image = None

        if telegram_image is not None:
            image_bytes, content_type, filename = telegram_image
            skill_result = await SkillDispatcher.handle_image_upload(
                chat_id,
                data=image_bytes,
                content_type=content_type,
                filename=filename,
                app=app,
            )
            if skill_result is not None:
                rendered = TelegramRenderer.render_skill_result(skill_result)
                await _send_rendered_message(chat_id, rendered)
                return

        active_session = await TelegramSkillSessionStore.get_session(chat_id)
        if (
            active_session is not None
            and active_session.skill_name == "persona-creator"
            and active_session.step_key == "collect_appearance"
        ):
            await send_message(
                chat_id,
                "Please send a photo or image file for the persona appearance step, or type a description.",
                parse_mode=None,
            )
            return

        await send_message(
            chat_id,
            "File received. Content pipelines coming soon.",
            parse_mode=None,
        )
        return

    if text.startswith("/start"):
        await TelegramSkillSessionStore.clear_session(chat_id)
        start_parts = text.split(maxsplit=1)
        start_token = start_parts[1].strip() if len(start_parts) > 1 else None
        if start_token:
            try:
                await TelegramSubscriberService.upsert(
                    chat_id=chat_id,
                    chat_type=chat_type,
                    username=username,
                    first_name=first_name,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to upsert subscriber chat_id=%s during token start: %s",
                    chat_id,
                    exc,
                )
            try:
                link_result = await TelegramLinkService.consume_link_token(
                    token=start_token,
                    chat_id=chat_id,
                    telegram_username=username,
                )
                await send_message(
                    chat_id,
                    (
                        "Telegram is now linked to your customer workspace.\n\n"
                        f"Linked user: {link_result['user_id']}\n"
                        "You can return to the dashboard and continue persona setup."
                    ),
                    parse_mode=None,
                    reply_markup=inline_keyboard(
                        [("Open Studio", "menu_main"), ("Status", "status_check")],
                    ),
                )
                return
            except TelegramLinkError as exc:
                await send_message(
                    chat_id,
                    (
                        f"Telegram link failed: {exc}\n\n"
                        "Open the dashboard and generate a fresh link token."
                    ),
                    parse_mode=None,
                    reply_markup=inline_keyboard(
                        [("Open Studio", "menu_main"), ("Status", "status_check")],
                    ),
                )
                return
        await send_message(
            chat_id,
            (
                "Welcome! AI Influencer Bot is online.\n\n"
                "Use /media to open the studio menu, or wait for daily story approvals.\n\n"
                "To link this Telegram account to a customer workspace, start from the web dashboard or auth page and open the secure bot link there."
            ),
            parse_mode=None,
            reply_markup=inline_keyboard(
                [("Open Studio", "menu_main"), ("Status", "status_check")],
                [("Help", "help")],
            ),
        )
        return

    # ── Shortcut slash commands ───────────────────────────────────────────
    # Canonical commands (exposed in Telegram Menu via setMyCommands):
    #   /start, /media, /create_video, /create_image, /personas, /quota, /cancel
    # Legacy aliases (parser-only, not in Telegram UI):
    #   /create-video, /create-image, /create_persona, /create-persona,
    #   /inspect_persona, /inspect-persona
    _SHORTCUT_MENU_MAP = {
        "/create_image": "menu_image",
        "/create-image": "menu_image",
    }
    _SHORTCUT_SKILL_MAP = {
        # Canonical video command - starts video-ai directly (deterministic)
        "/create_video": "video-ai",
        # Legacy aliases for video
        "/create-video": "video-ai",
        # Canonical persona inspection command
        "/personas": "persona-inspector",
        # Legacy aliases for persona
        "/create_persona": "persona-creator",
        "/create-persona": "persona-creator",
        "/inspect_persona": "persona-inspector",
        "/inspect-persona": "persona-inspector",
        # Quota inspector
        "/quota": "quota-inspector",
    }

    # ── Plain text shortcuts (case-insensitive) ────────────────────────────
    # These are deterministic triggers that bypass OpenClaw routing
    _TEXT_SKILL_MAP = {
        "create video": "video-ai",
        "make video": "video-ai",
        "video": "video-ai",
        "create persona": "persona-creator",
        "new persona": "persona-creator",
        "inspect persona": "persona-inspector",
        "check persona": "persona-inspector",
        "quota": "quota-inspector",
    }
    _TEXT_MENU_MAP = {
        "create image": "menu_image",
        "make image": "menu_image",
        "image": "menu_image",
    }

    text_cmd = text.strip().lower().split()[0] if text.strip() else ""
    text_lower = text.strip().lower()

    # Check plain text shortcuts - all deterministic, bypass OpenClaw
    if text_lower in _TEXT_SKILL_MAP:
        skill_name = _TEXT_SKILL_MAP[text_lower]
        await TelegramSkillSessionStore.clear_session(chat_id)
        skill_result, pending_message_id = await _await_with_message_progress(
            chat_id,
            SkillDispatcher.start_skill(chat_id, skill_name, app),
        )
        if skill_result is None:
            return
        rendered = TelegramRenderer.render_skill_result(skill_result)
        await _send_rendered_message(chat_id, rendered, message_id=pending_message_id)
        return

    if text_lower in _TEXT_MENU_MAP:
        await TelegramSkillSessionStore.clear_session(chat_id)
        rendered = TelegramRenderer.render_menu(_TEXT_MENU_MAP[text_lower])
        await _send_rendered_message(chat_id, rendered)
        return

    if text_cmd in _SHORTCUT_MENU_MAP:
        await TelegramSkillSessionStore.clear_session(chat_id)
        rendered = TelegramRenderer.render_menu(_SHORTCUT_MENU_MAP[text_cmd])
        await _send_rendered_message(chat_id, rendered)
        return

    # Slash command shortcuts - all deterministic, bypass OpenClaw
    if text_cmd in _SHORTCUT_SKILL_MAP:
        skill_name = _SHORTCUT_SKILL_MAP[text_cmd]
        await TelegramSkillSessionStore.clear_session(chat_id)
        skill_result, pending_message_id = await _await_with_message_progress(
            chat_id,
            SkillDispatcher.start_skill(chat_id, skill_name, app),
        )
        if skill_result is None:
            return
        rendered = TelegramRenderer.render_skill_result(skill_result)
        await _send_rendered_message(chat_id, rendered, message_id=pending_message_id)
        return

    if text.startswith("/media"):
        await TelegramSkillSessionStore.clear_session(chat_id)
        rendered = TelegramRenderer.render_menu("menu_main")
        await _send_rendered_message(chat_id, rendered)
        return

    if text.startswith("/cancel"):
        await TelegramSkillSessionStore.clear_session(chat_id)
        await send_message(
            chat_id, "Cancelled the active skill session.", parse_mode=None
        )
        return

    skill_result, pending_message_id = await _await_with_message_progress(
        chat_id,
        SkillDispatcher.handle_text(chat_id, text, app),
    )
    if skill_result is not None:
        rendered = TelegramRenderer.render_skill_result(skill_result)
        await _send_rendered_message(chat_id, rendered, message_id=pending_message_id)
        return
    if await TelegramSkillSessionStore.get_session(chat_id) is not None:
        # Error feedback was already sent; avoid routing this message to OpenClaw.
        return

    if text.startswith("http"):
        await send_message(
            chat_id,
            f"URL received. URL pipelines coming soon.\n{text[:60]}",
            parse_mode=None,
        )
        return

    if text.strip():
        await send_chat_action(chat_id, action="typing")
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
        background_tasks.add_task(
            _handle_callback_query, request.app, payload["callback_query"]
        )
    elif "message" in payload:
        background_tasks.add_task(_handle_message, request.app, payload["message"])
    else:
        logger.debug("Unhandled Telegram update type: %s", list(payload.keys()))

    return {"ok": True}
