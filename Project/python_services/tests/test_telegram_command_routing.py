"""
Tests for deterministic Telegram command routing.

These tests verify that:
1. Canonical commands are handled correctly
2. Video-ai starts directly (no OpenClaw hop) for deterministic entrypoints
3. /start is welcome only, not video-ai
4. /personas maps to persona-inspector
5. Help text lists the canonical commands
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI

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
        _handle_callback_query,
        _handle_message,
        _help_text,
    )
    from services.skill_session_store import TelegramSkillSessionStore
    from skills.base import SkillControl, SkillResult, SkillSession, SkillStatus

# Import the command registration constants
with patch.dict(os.environ, _TEST_ENV, clear=False):
    from scripts.register_telegram_commands import TELEGRAM_BOT_COMMANDS


@pytest.fixture
def tg_calls():
    """Capture all Telegram API calls."""
    calls = []

    async def fake_tg_call(method: str, payload: dict) -> dict:
        calls.append({"method": method, "payload": payload})
        return {"ok": True, "result": {"message_id": 1}}

    with patch("api.telegram_webhook._tg_call", side_effect=fake_tg_call):
        yield calls


@pytest.fixture(autouse=True)
def reset_telegram_skill_session_store():
    """Reset session store between tests."""
    TelegramSkillSessionStore._redis_client = None
    TelegramSkillSessionStore._redis_enabled = False
    TelegramSkillSessionStore._redis_init_attempted = True
    TelegramSkillSessionStore._memory_sessions.clear()
    yield
    TelegramSkillSessionStore._memory_sessions.clear()


@pytest.fixture(autouse=True)
def stub_telegram_presence_updates():
    """Stub out presence tracking."""
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


# -----------------------------------------------------------------------------
# Test: /start returns welcome, not video-ai
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_start_command_returns_welcome_not_video_ai(tg_calls):
    """
    /start should return the welcome/studio message, NOT start video-ai skill.
    """
    message = {
        "text": "/start",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    await _handle_message(None, message)

    send_call = next(call for call in tg_calls if call["method"] == "sendMessage")
    text = send_call["payload"]["text"]

    # Should be welcome message
    assert "AI Influencer Bot is online" in text
    # Should NOT contain video-ai mode selection
    assert "idea_brief" not in text.lower()
    assert "recorded_demo_video" not in text.lower()
    # Should have Open Studio button
    reply_markup = send_call["payload"].get("reply_markup", {})
    buttons = reply_markup.get("inline_keyboard", [])
    assert any(
        btn.get("callback_data") == "menu_main" for row in buttons for btn in row
    )


# -----------------------------------------------------------------------------
# Test: /create_video starts video-ai directly
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_video_command_starts_video_planner_directly(tg_calls):
    """
    /create_video should start video-ai directly without OpenClaw routing.
    """
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

    with patch.object(
        telegram_webhook.SkillDispatcher,
        "start_skill",
        AsyncMock(return_value=mock_skill_result),
    ) as start_skill:
        await _handle_message(FastAPI(), message)

    # Should call start_skill directly with video-ai
    start_skill.assert_awaited_once()
    call_args = start_skill.call_args
    assert call_args[0][0] == 123456789  # chat_id
    assert call_args[0][1] == "video-ai"  # skill_name


@pytest.mark.asyncio
async def test_create_video_command_does_not_call_openclaw(tg_calls):
    """
    /create_video should NOT route through OpenClaw service.
    """
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
        ),
        patch(
            "api.telegram_webhook.OpenClawService",
            return_value=mock_openclaw,
        ),
    ):
        await _handle_message(FastAPI(), message)

    # OpenClaw should NOT be called
    mock_openclaw.execute_task.assert_not_awaited()


# -----------------------------------------------------------------------------
# Test: /personas starts persona-inspector
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_personas_command_starts_persona_inspector(tg_calls):
    """
    /personas should start persona-inspector skill.
    """
    message = {
        "text": "/personas",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    mock_skill_result = SkillResult(
        success=True,
        next_step="list_personas",
        session=SkillSession(
            skill_name="persona-inspector",
            step_key="list_personas",
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
        await _handle_message(FastAPI(), message)

    start_skill.assert_awaited_once()
    call_args = start_skill.call_args
    assert call_args[0][0] == 123456789  # chat_id
    assert call_args[0][1] == "persona-inspector"  # skill_name


# -----------------------------------------------------------------------------
# Test: skill_video-ai callback starts video-ai directly
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_skill_video_planner_callback_starts_directly(tg_calls):
    """
    Callback data 'skill_video-ai' should start video-ai directly without OpenClaw.
    """
    callback_query = {
        "id": "cq_skill_video_001",
        "data": "skill_video-ai",
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

    # Should call start_skill directly
    start_skill.assert_awaited_once()
    call_args = start_skill.call_args
    assert call_args[0][0] == 123456789  # chat_id
    assert call_args[0][1] == "video-ai"  # skill_name


@pytest.mark.asyncio
async def test_skill_video_planner_callback_does_not_call_openclaw(tg_calls):
    """
    Callback 'skill_video-ai' should NOT route through OpenClaw.
    """
    callback_query = {
        "id": "cq_skill_video_002",
        "data": "skill_video-ai",
        "from": {"id": 123456789, "first_name": "TripC"},
        "message": {
            "message_id": 43,
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
        ),
        patch(
            "api.telegram_webhook.OpenClawService",
            return_value=mock_openclaw,
        ),
    ):
        await _handle_callback_query(FastAPI(), callback_query)

    mock_openclaw.execute_task.assert_not_awaited()


# -----------------------------------------------------------------------------
# Test: Help text lists canonical commands
# -----------------------------------------------------------------------------
def test_help_text_lists_canonical_commands():
    """
    Help text should list only the canonical commands intended for Telegram UI.
    """
    help_text = _help_text()

    # Canonical commands that SHOULD be listed
    assert "/start" in help_text
    assert "/media" in help_text
    assert "/create_video" in help_text
    assert "/create_image" in help_text
    assert "/personas" in help_text
    assert "/quota" in help_text
    assert "/cancel" in help_text

    # Legacy commands that should NOT be in help
    assert "/create-video" not in help_text
    assert "/create-image" not in help_text
    assert "/create_persona" not in help_text
    assert "/inspect_persona" not in help_text


def test_registered_commands_match_help_text():
    """
    The commands registered via setMyCommands should match those in help text.
    """
    help_text = _help_text()

    for cmd in TELEGRAM_BOT_COMMANDS:
        command = f"/{cmd['command']}"
        assert command in help_text, (
            f"Command {command} registered but not in help text"
        )


def test_registered_commands_are_exactly_seven():
    """
    Operational smoke test: command-registration sends exactly 7 canonical commands.
    """
    expected_commands = {
        "start",
        "media",
        "create_video",
        "create_image",
        "personas",
        "quota",
        "cancel",
    }
    actual_commands = {cmd["command"] for cmd in TELEGRAM_BOT_COMMANDS}

    assert actual_commands == expected_commands
    assert len(TELEGRAM_BOT_COMMANDS) == 7


# -----------------------------------------------------------------------------
# Test: "create video" text shortcut also bypasses OpenClaw
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_video_text_shortcut_bypasses_openclaw(tg_calls):
    """
    Plain text 'create video' should start video-ai directly, not via OpenClaw.
    """
    message = {
        "text": "create video",
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

    # Should call start_skill directly with video-ai
    start_skill.assert_awaited_once()
    call_args = start_skill.call_args
    assert call_args[0][1] == "video-ai"

    # OpenClaw should NOT be called
    mock_openclaw.execute_task.assert_not_awaited()


# -----------------------------------------------------------------------------
# Test: Free-text chat still routes through OpenClaw
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_free_text_still_routes_through_openclaw(tg_calls):
    """
    Free-text conversational input should still route through OpenClaw.
    """
    message = {
        "text": "What can you help me with today?",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    mock_openclaw = AsyncMock()
    mock_openclaw.execute_task = AsyncMock(
        return_value={"text": "I can help with videos and more!"}
    )
    mock_openclaw.close = AsyncMock()

    with patch(
        "api.telegram_webhook.OpenClawService",
        return_value=mock_openclaw,
    ):
        await _handle_message(FastAPI(), message)

    # OpenClaw SHOULD be called for free-text
    mock_openclaw.execute_task.assert_awaited_once()
    mock_openclaw.close.assert_awaited_once()


# -----------------------------------------------------------------------------
# Test: Video-ai fresh session has collect_objective step
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_video_ai_fresh_session_has_collect_objective_step(tg_calls):
    """
    A fresh video-ai session should start at step_key='collect_objective'.
    """
    message = {
        "text": "/create_video",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    # Use real start_skill to test the actual skill initialization
    with patch.object(
        telegram_webhook.SkillDispatcher,
        "_fetch_personas",
        AsyncMock(return_value=[]),
    ):
        await _handle_message(FastAPI(), message)

    # Check that session was created with collect_objective
    session = await TelegramSkillSessionStore.get_session(123456789)
    assert session is not None
    assert session.skill_name == "video-ai"
    assert session.step_key == "collect_objective"


# -----------------------------------------------------------------------------
# Test: Video planner result prompts for objective
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_video_planner_result_prompts_for_objective(tg_calls):
    """
    Rendering a fresh video-planner result should prompt for the planning objective.
    """
    message = {
        "text": "/create_video",
        "chat": {"id": 123456789, "type": "private"},
        "from": {"first_name": "TripC", "username": "tripc"},
    }

    with patch.object(
        telegram_webhook.SkillDispatcher,
        "_fetch_personas",
        AsyncMock(return_value=[]),
    ):
        await _handle_message(FastAPI(), message)

    send_calls = [call for call in tg_calls if call["method"] == "sendMessage"]
    assert len(send_calls) >= 1

    last_send = send_calls[-1]
    assert "What is your objective for this video?" in last_send["payload"]["text"]
