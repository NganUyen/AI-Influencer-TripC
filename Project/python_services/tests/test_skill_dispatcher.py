from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.skill_dispatcher import SkillDispatcher
from services.skill_session_store import TelegramSkillSessionStore
from skills.base import SkillControl, SkillSession, SkillStatus


class _AsyncClientContext:
    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_cancel_action_cancels_workflow_before_clearing_session(monkeypatch):
    chat_id = 112233
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="video-ai",
        step_key="approve_video",
        collected={"persona_id": "persona-1", "topic": "Beach trip"},
        artifacts={"workflow_id": "video-wf-1"},
        control=SkillControl(
            status=SkillStatus.waiting_approval,
            workflow_id="video-wf-1",
            approval_required=True,
        ),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    response = SimpleNamespace(raise_for_status=lambda: None)
    client = SimpleNamespace(post=AsyncMock(return_value=response))
    monkeypatch.setattr(
        SkillDispatcher,
        "_transport_client",
        lambda _app: _AsyncClientContext(client),
    )

    result = await SkillDispatcher.handle_action(chat_id, "cancel", app=object())

    assert result.success is True
    assert result.output == {"status": "cancelled", "workflow_id": "video-wf-1"}
    assert result.session is not None
    assert result.session.skill_name == "video-ai"
    client.post.assert_awaited_once()
    assert await TelegramSkillSessionStore.get_session(chat_id) is None


@pytest.mark.asyncio
async def test_cancel_action_preserves_session_when_workflow_cancel_fails(monkeypatch):
    chat_id = 445566
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="video-ai",
        step_key="approve_video",
        artifacts={"workflow_id": "video-wf-2"},
        control=SkillControl(
            status=SkillStatus.waiting_approval,
            workflow_id="video-wf-2",
            approval_required=True,
        ),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    client = SimpleNamespace(post=AsyncMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(
        SkillDispatcher,
        "_transport_client",
        lambda _app: _AsyncClientContext(client),
    )

    result = await SkillDispatcher.handle_action(chat_id, "cancel", app=object())

    assert result.success is False
    assert "couldn't cancel the running workflow" in result.error
    assert await TelegramSkillSessionStore.get_session(chat_id) is not None
