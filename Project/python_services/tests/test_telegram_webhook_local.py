import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET": "test-secret",
    "TELEGRAM_CHAT_ID": "999",
    "BACKEND_PUBLIC_URL": "http://localhost:8000",
    "FRONTEND_PUBLIC_URL": "http://localhost:3000",
    "CHATGPT_CONNECTOR_PUBLIC_URL": "http://localhost:8000",
    "DATABASE_URL": "postgresql://localhost/test",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "STORAGE_PROVIDER": "supabase",
    "SUPABASE_STORAGE_BUCKET": "media",
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

with patch.dict(os.environ, _TEST_ENV, clear=False):
    from api import telegram_webhook
    from api.telegram_webhook import (
        _escape_md,
        _handle_callback_query,
        _handle_message,
        send_photo,
    )
    from services.telegram_link_service import TelegramLinkError
    from services.skill_session_store import TelegramSkillSessionStore
    from skills.base import SkillControl, SkillResult, SkillSession, SkillStatus


@pytest.fixture
def tg_calls():
    calls = []

    async def fake_tg_call(method: str, payload: dict) -> dict:
        calls.append({"method": method, "payload": payload})
        return {"ok": True, "result": {"message_id": 1}}

    with patch("api.telegram_webhook._tg_call", side_effect=fake_tg_call):
        yield calls


@pytest.fixture(autouse=True)
def reset_telegram_skill_session_store():
    TelegramSkillSessionStore._redis_client = None
    TelegramSkillSessionStore._redis_enabled = False
    TelegramSkillSessionStore._redis_init_attempted = True
    TelegramSkillSessionStore._memory_sessions.clear()
    yield
    TelegramSkillSessionStore._memory_sessions.clear()


@pytest.fixture(autouse=True)
def stub_telegram_presence_updates():
    with (
        patch.object(
            telegram_webhook.TelegramSubscriberService,
            "touch",
            AsyncMock(),
        ),
        patch.object(
            telegram_webhook.TelegramLinkService,
            "touch_link",
            AsyncMock(),
        ),
    ):
        yield


@pytest.mark.asyncio
async def test_start_command_opens_studio_menu(tg_calls):
    message = {
        "text": "/start",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    await _handle_message(None, message)

    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert "Welcome to the TripC Media Studio" in send_call["payload"]["text"]
    restored = await TelegramSkillSessionStore.get_session(123456789)
    assert restored is None


@pytest.mark.asyncio
async def test_start_command_replaces_active_session_with_menu_only(tg_calls):
    session = SkillSession(
        skill_name="persona-creator",
        step_key="choose_language",
        collected={"persona_id": "tmp-persona"},
        artifacts={},
        control=SkillControl(status=SkillStatus.collecting),
    )
    await TelegramSkillSessionStore.set_session(123456789, session)

    message = {
        "text": "/start",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    await _handle_message(None, message)

    restored = await TelegramSkillSessionStore.get_session(123456789)
    assert restored is None


@pytest.mark.asyncio
async def test_create_video_command_starts_video_ai_directly(tg_calls):
    message = {
        "text": "/create_video",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    mock_skill_result = SkillResult(
        success=True,
        next_step="collect_objective",
        session=SkillSession(
            skill_name="video-ai",
            step_key="collect_objective",
            collected={},
            artifacts={},
            control=SkillControl(status=SkillStatus.collecting),
        ),
    )

    mock_openclaw = AsyncMock()
    mock_openclaw.execute_task = AsyncMock(
        return_value={"text": "Should not be called"}
    )
    mock_openclaw.close = AsyncMock()

    with (
        patch.object(
            telegram_webhook.SkillDispatcher,
            "start_skill",
            AsyncMock(return_value=mock_skill_result),
        ) as start_skill,
        patch(
            "api.telegram_webhook.OpenClawService",
            return_value=mock_openclaw,
        ),
    ):
        await _handle_message(FastAPI(), message)

    start_skill.assert_awaited_once()
    call_args = start_skill.call_args
    assert call_args[0][0] == 123456789
    assert call_args[0][1] == "video-ai"
    mock_openclaw.execute_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_video_planner_callback_aliases_to_video_ai(tg_calls):
    callback_query = {
        "id": "cq_skill_video_001",
        "data": "skill_video-planner",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 42,
            "chat": {"id": 123456789},
        },
    }

    mock_skill_result = SkillResult(
        success=True,
        next_step="collect_objective",
        session=SkillSession(
            skill_name="video-ai",
            step_key="collect_objective",
            collected={},
            artifacts={},
            control=SkillControl(status=SkillStatus.collecting),
        ),
    )

    with patch.object(
        telegram_webhook.SkillDispatcher,
        "start_skill",
        AsyncMock(return_value=mock_skill_result),
    ) as start_skill:
        await _handle_callback_query(FastAPI(), callback_query)

    start_skill.assert_awaited_once()
    call_args = start_skill.call_args
    assert call_args[0][0] == 123456789
    assert call_args[0][1] == "video-ai"


@pytest.mark.asyncio
async def test_start_command_without_token_does_not_register_or_link(tg_calls):
    message = {
        "text": "/start",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    with (
        patch.object(
            telegram_webhook.TelegramSubscriberService,
            "upsert",
            AsyncMock(),
        ) as upsert_subscriber,
        patch.object(
            telegram_webhook.TelegramLinkService,
            "consume_link_token",
            AsyncMock(),
        ) as consume_link_token,
    ):
        await _handle_message(None, message)

    upsert_subscriber.assert_not_awaited()
    consume_link_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_command_with_link_token_consumes_token_and_confirms_link(tg_calls):
    message = {
        "text": "/start secure-link-token",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    with (
        patch.object(
            telegram_webhook.TelegramSubscriberService,
            "upsert",
            AsyncMock(),
        ) as upsert_subscriber,
        patch.object(
            telegram_webhook.TelegramLinkService,
            "consume_link_token",
            AsyncMock(
                return_value={
                    "chat_id": 123456789,
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "telegram_username": "tripc",
                }
            ),
        ) as consume_link_token,
    ):
        await _handle_message(None, message)

    upsert_subscriber.assert_awaited_once()
    consume_link_token.assert_awaited_once_with(
        token="secure-link-token",
        chat_id=123456789,
        telegram_username="tripc",
    )
    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert (
        "Telegram is now linked to your customer workspace."
        in send_call["payload"]["text"]
    )
    assert "550e8400-e29b-41d4-a716-446655440000" in send_call["payload"]["text"]


@pytest.mark.asyncio
async def test_start_command_with_invalid_link_token_returns_friendly_error(tg_calls):
    message = {
        "text": "/start invalid-token",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    with (
        patch.object(
            telegram_webhook.TelegramSubscriberService,
            "upsert",
            AsyncMock(),
        ),
        patch.object(
            telegram_webhook.TelegramLinkService,
            "consume_link_token",
            AsyncMock(side_effect=TelegramLinkError("Telegram link token is invalid.")),
        ),
    ):
        await _handle_message(None, message)

    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert (
        "Telegram link failed: Telegram link token is invalid."
        in send_call["payload"]["text"]
    )
    assert "generate a fresh link token" in send_call["payload"]["text"]


@pytest.mark.asyncio
async def test_url_message_acknowledges_link_payload(tg_calls):
    message = {
        "text": "https://someapp.ai/landing",
        "chat": {"id": 123456789, "type": "private"},
    }

    await _handle_message(None, message)

    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert "URL pipelines coming soon." in send_call["payload"]["text"]


@pytest.mark.asyncio
async def test_plain_text_is_forwarded_to_openclaw(tg_calls):
    message = {
        "text": "Hello bot!",
        "chat": {"id": 123456789, "type": "private"},
    }

    mock_service = AsyncMock()
    mock_service.execute_task = AsyncMock(return_value={"text": "Hi from OpenClaw"})
    mock_service.close = AsyncMock()

    with patch("api.telegram_webhook.OpenClawService", return_value=mock_service):
        await _handle_message(None, message)

    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert send_call["payload"]["text"] == "Hi from OpenClaw"
    assert "parse_mode" not in send_call["payload"]
    mock_service.execute_task.assert_awaited_once()
    mock_service.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_plain_text_agent_can_start_skill(tg_calls):
    message = {
        "text": "create a weekly marketing plan for this week",
        "chat": {"id": 123456789, "type": "private"},
    }

    mock_service = AsyncMock()
    mock_service.execute_task = AsyncMock(
        return_value={
            "action": "start_skill",
            "skill_name": "weekly-planner",
            "reply": "Starting weekly planner",
        }
    )
    mock_service.close = AsyncMock()

    mock_skill_result = SkillResult(
        success=False,
        error="brand_config is required.",
    )

    with (
        patch("api.telegram_webhook.OpenClawService", return_value=mock_service),
        patch.object(
            telegram_webhook.SkillDispatcher,
            "start_skill",
            AsyncMock(return_value=mock_skill_result),
        ) as start_skill,
    ):
        await _handle_message(None, message)

    start_skill.assert_awaited_once_with(123456789, "weekly-planner", None)
    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert send_call["payload"]["text"] == "brand_config is required."
    mock_service.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_typed_text_can_advance_inline_keyboard_step(tg_calls):
    session = SkillSession(
        skill_name="persona-creator",
        step_key="choose_language",
        collected={"persona_id": "ronaldo-portugal"},
        artifacts={},
        control=SkillControl(status=SkillStatus.collecting),
    )
    await TelegramSkillSessionStore.set_session(123456789, session)

    message = {
        "text": "Vietnamese",
        "chat": {"id": 123456789, "type": "private"},
    }

    app = FastAPI()
    await _handle_message(app, message)

    updated = await TelegramSkillSessionStore.get_session(123456789)
    assert updated is not None
    assert updated.collected.get("language") == "Vietnamese"
    assert updated.step_key == "choose_voice"

    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    assert "select a voice" in send_call["payload"]["text"].lower()


@pytest.mark.asyncio
async def test_photo_message_routes_into_persona_creator_upload_flow(tg_calls):
    preview_url = "https://storage.example/persona-avatar.png"
    session = SkillSession(
        skill_name="persona-creator",
        step_key="collect_appearance",
        collected={
            "persona_id": "demo-persona",
            "language": "English",
            "voice": "male_friendly",
        },
        artifacts={},
        control=SkillControl(status=SkillStatus.collecting),
    )
    await TelegramSkillSessionStore.set_session(123456789, session)

    preview_result = SkillResult(
        success=True,
        next_step="preview",
        output={"preview_image_url": preview_url},
        session=SkillSession(
            skill_name="persona-creator",
            step_key="preview",
            collected={"persona_id": "demo-persona"},
            artifacts={
                "preview_image_url": preview_url,
                "avatar_image_url": preview_url,
                "avatar_media_asset_id": "asset-123",
                "persona_id": "demo-persona",
            },
            control=SkillControl(status=SkillStatus.preview_ready),
        ),
    )

    message = {
        "chat": {"id": 123456789, "type": "private"},
        "photo": [{"file_id": "photo-1"}],
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    with (
        patch.object(
            telegram_webhook,
            "_download_telegram_image",
            AsyncMock(return_value=(b"image-bytes", "image/png", "avatar.png")),
        ),
        patch.object(
            telegram_webhook.SkillDispatcher,
            "handle_image_upload",
            AsyncMock(return_value=preview_result),
        ) as handle_image_upload,
    ):
        await _handle_message(None, message)

    handle_image_upload.assert_awaited_once_with(
        123456789,
        data=b"image-bytes",
        content_type="image/png",
        filename="avatar.png",
        app=None,
    )
    methods = [call["method"] for call in tg_calls]
    assert methods[:2] == ["sendPhoto", "sendMessage"]
    assert tg_calls[0]["payload"]["photo"] == preview_url
    assert "Persona Preview Ready" in tg_calls[1]["payload"]["text"]
    assert "not production-ready until you save it" in tg_calls[1]["payload"]["text"]


@pytest.mark.asyncio
async def test_status_button_edits_message_with_help_text(tg_calls):
    callback_query = {
        "id": "cq_status_001",
        "data": "status_check",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 42,
            "chat": {"id": 123456789},
        },
    }

    await _handle_callback_query(None, callback_query)

    methods = [call["method"] for call in tg_calls]
    assert methods[:2] == ["answerCallbackQuery", "editMessageText"]
    assert "TripC Bot Status" in tg_calls[1]["payload"]["text"]
    assert "parse_mode" not in tg_calls[1]["payload"]


@pytest.mark.asyncio
async def test_send_photo_falls_back_to_multipart_upload_when_url_send_fails():
    initial_send = AsyncMock(
        return_value={
            "ok": False,
            "description": "Wrong file identifier/http url specified",
        }
    )
    multipart_send = AsyncMock(return_value={"ok": True, "result": {"message_id": 99}})

    class _FakeImageResponse:
        headers = {"content-type": "image/png"}
        content = b"png-bytes"

        def raise_for_status(self) -> None:
            return None

    fake_http_client = AsyncMock()
    fake_http_client.get = AsyncMock(return_value=_FakeImageResponse())
    fake_http_client.__aenter__.return_value = fake_http_client
    fake_http_client.__aexit__.return_value = False

    with (
        patch("api.telegram_webhook._tg_call", initial_send),
        patch("api.telegram_webhook._tg_call_multipart", multipart_send),
        patch("api.telegram_webhook.httpx.AsyncClient", return_value=fake_http_client),
    ):
        response = await send_photo(
            chat_id=123456789,
            photo="https://cdn.example/generated-image.png",
            caption="Generated preview.",
        )

    assert response["ok"] is True
    initial_send.assert_awaited_once()
    fake_http_client.get.assert_awaited_once_with(
        "https://cdn.example/generated-image.png"
    )
    multipart_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_skip_button_confirms_skip_without_temporal(tg_calls):
    callback_query = {
        "id": "cq_skip_001",
        "data": "skip_daily-story-2026-03-20",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 43,
            "chat": {"id": 123456789},
        },
    }

    with patch.object(telegram_webhook, "TemporalClient", None):
        await _handle_callback_query(None, callback_query)

    edit_call = next(call for call in tg_calls if call["method"] == "editMessageText")
    assert "Skipped for today." == edit_call["payload"]["text"]


@pytest.mark.asyncio
async def test_expired_option_callback_prompts_user_to_restart_flow(tg_calls):
    callback_query = {
        "id": "cq_option_001",
        "data": "option::clean",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 44,
            "chat": {"id": 123456789},
        },
    }

    await _handle_callback_query(None, callback_query)

    edit_call = next(call for call in tg_calls if call["method"] == "editMessageText")
    assert (
        edit_call["payload"]["text"]
        == "Skill session expired. Use /media to start again."
    )


@pytest.mark.asyncio
async def test_option_callback_sends_photo_preview_and_keeps_controls(tg_calls):
    callback_query = {
        "id": "cq_option_002",
        "data": "option::clean",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 45,
            "chat": {"id": 123456789},
        },
    }
    preview_url = "https://cdn.example/generated-image.png"
    preview_result = SkillResult(
        success=True,
        next_step="confirm_or_regenerate",
        output={"preview_image_url": preview_url},
        session=SkillSession(
            skill_name="image-scene",
            step_key="confirm_or_regenerate",
            collected={"topic_or_prompt": "beer scene", "style": "clean"},
            artifacts={
                "preview_image_url": preview_url,
                "final_image_url": preview_url,
            },
            control=SkillControl(status=SkillStatus.preview_ready),
        ),
    )

    with patch.object(
        telegram_webhook.SkillDispatcher,
        "handle_option",
        AsyncMock(return_value=preview_result),
    ):
        await _handle_callback_query(None, callback_query)

    methods = [call["method"] for call in tg_calls]
    assert methods[:3] == ["answerCallbackQuery", "editMessageText", "sendPhoto"]
    expected_text = (
        "🎨 *Image Generated Successfully!*\n\n"
        "• *Style*: clean\n"
        "• *Scene*: N/A\n"
        "• *Aspect Ratio*: 16:9\n"
        "• *Prompt*: beer scene\n\n"
        "Review the image below and choose an action."
    )
    assert tg_calls[1]["payload"]["text"] == expected_text
    assert (
        tg_calls[1]["payload"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        == "action::use_images"
    )
    assert tg_calls[2]["payload"]["photo"] == preview_url
    expected_caption = (
        "🎨 Style: clean | 📐 Ratio: 16:9\nReview the image and choose an action."
    )
    assert tg_calls[2]["payload"]["caption"] == expected_caption


@pytest.mark.asyncio
async def test_receive_telegram_update_requires_matching_secret():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/webhooks/telegram",
            "headers": [],
        }
    )

    with patch.object(
        telegram_webhook.settings, "TELEGRAM_WEBHOOK_SECRET", "test-secret"
    ):
        with pytest.raises(HTTPException) as exc_info:
            await telegram_webhook.receive_telegram_update(
                request,
                BackgroundTasks(),
                None,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid Telegram webhook secret"


def test_markdown_escape_handles_special_characters():
    raw = "https://app.ai/page-test.html is great!"
    escaped = _escape_md(raw)

    for ch in ["!", ".", "-"]:
        assert f"\\{ch}" in escaped


@pytest.mark.asyncio
async def test_manual_mobile_upload_routes_video_planner_uploads(tg_calls):
    chat_id = 123456789
    await TelegramSkillSessionStore.set_session(
        chat_id,
        SkillSession(
            skill_name="video-planner",
            step_key="upload_manual_video",
            artifacts={"telegram_chat_id": str(chat_id)},
            control=SkillControl(status=SkillStatus.collecting),
        ),
    )
    message = {
        "chat": {"id": chat_id, "type": "private"},
        "video": {"file_id": "telegram-video-1", "mime_type": "video/mp4"},
    }

    with (
        patch(
            "api.telegram_webhook._download_telegram_video",
            AsyncMock(return_value=(b"video-bytes", "video/mp4", "mobile.mp4")),
        ) as download_video,
        patch(
            "api.telegram_webhook.SkillDispatcher.handle_video_upload",
            AsyncMock(
                return_value=SkillResult(
                    success=True,
                    next_step="poll_status",
                    output={"message": "Upload processed."},
                    session=SkillSession(
                        skill_name="video-ai",
                        step_key="package_ready",
                        artifacts={},
                        control=SkillControl(status=SkillStatus.waiting_approval),
                    ),
                )
            ),
        ) as handle_upload,
    ):
        await _handle_message(None, message)

    download_video.assert_awaited_once()
    handle_upload.assert_awaited_once()
    kwargs = handle_upload.await_args.kwargs
    assert kwargs["file_id"] == "telegram-video-1"
    assert kwargs["content_type"] == "video/mp4"
    assert kwargs["filename"] == "mobile.mp4"
