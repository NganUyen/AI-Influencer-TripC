from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from services import heygen_service as heygen_service_module
from services import persona_registry_service as persona_registry_service_module
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


async def test_save_persona_action_clears_session_after_marking_ready():
    chat_id = 778899
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="persona-creator",
        step_key="preview",
        collected={"persona_id": "travis-us"},
        artifacts={
            "telegram_chat_id": str(chat_id),
            "persona_id": "travis-us",
            "avatar_image_url": "https://cdn.example/avatar.png",
            "preview_image_url": "https://cdn.example/avatar.png",
            "avatar_media_asset_id": "asset-123",
            "persona_data": {"avatar_source_type": "generated"},
            "heygen_avatar_id": "heygen-789",
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    with patch(
        "services.persona_registry_service.PersonaRegistryService.update_persona",
        AsyncMock(
            return_value={
                "persona_id": "travis-us",
                "status": "ready",
                "avatar_media_asset_id": "asset-123",
                "heygen_avatar_id": "heygen-789",
            }
        ),
    ) as update_persona:
        result = await SkillDispatcher.handle_action(chat_id, "save", app=object())

    assert result.success is True
    assert result.session is None
    assert result.output is not None
    assert result.output["status"] == "saved"
    assert result.output["persona_id"] == "travis-us"
    assert result.output["avatar_media_asset_id"] == "asset-123"
    assert result.output["heygen_avatar_id"] == "heygen-789"
    assert "marked as ready" in result.output["message"]
    update_persona.assert_awaited_once()
    assert await TelegramSkillSessionStore.get_session(chat_id) is None


@pytest.mark.asyncio
async def test_save_persona_registers_heygen_avatar_before_marking_ready(monkeypatch):
    chat_id = 123321
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="persona-creator",
        step_key="preview",
        collected={"persona_id": "hero-host"},
        artifacts={
            "telegram_chat_id": str(chat_id),
            "persona_id": "hero-host",
            "avatar_image_url": "https://cdn.example/hero-host.png",
            "avatar_media_asset_id": "media-123",
            "persona_data": {"avatar_source_type": "generated"},
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    class FakeHeyGenService:
        async def create_avatar(self, image_url: str, avatar_name: str = "Minh_TripC"):
            assert image_url == "https://cdn.example/hero-host.png"
            assert avatar_name == "hero-host"
            return "heygen-456"

    captured_update = {}

    async def fake_update_persona(
        persona_id, payload, *, user_id=None, owner_key=None
    ):
        captured_update["persona_id"] = persona_id
        captured_update["payload"] = payload
        captured_update["owner_key"] = owner_key
        return {"persona_id": persona_id, **payload}

    monkeypatch.setattr(
        heygen_service_module,
        "HeyGenService",
        FakeHeyGenService,
    )
    monkeypatch.setattr(
        persona_registry_service_module.PersonaRegistryService,
        "update_persona",
        fake_update_persona,
    )

    result = await SkillDispatcher.handle_action(chat_id, "save", app=object())

    assert result.success is True
    assert captured_update["persona_id"] == "hero-host"
    assert captured_update["owner_key"] == f"telegram:{chat_id}"
    assert captured_update["payload"]["status"] == "ready"
    assert captured_update["payload"]["avatar_media_asset_id"] == "media-123"
    assert captured_update["payload"]["heygen_avatar_id"] == "heygen-456"
    assert result.output["heygen_avatar_id"] == "heygen-456"
    assert await TelegramSkillSessionStore.get_session(chat_id) is None


@pytest.mark.asyncio
async def test_save_persona_keeps_session_when_heygen_registration_fails(monkeypatch):
    chat_id = 998877
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="persona-creator",
        step_key="preview",
        collected={"persona_id": "hero-host"},
        artifacts={
            "telegram_chat_id": str(chat_id),
            "persona_id": "hero-host",
            "avatar_image_url": "https://cdn.example/hero-host.png",
            "avatar_media_asset_id": "media-123",
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    class FakeHeyGenService:
        async def create_avatar(self, image_url: str, avatar_name: str = "Minh_TripC"):
            raise RuntimeError("quota temporarily unavailable")

    update_persona = AsyncMock()

    monkeypatch.setattr(
        heygen_service_module,
        "HeyGenService",
        FakeHeyGenService,
    )
    monkeypatch.setattr(
        persona_registry_service_module.PersonaRegistryService,
        "update_persona",
        update_persona,
    )

    result = await SkillDispatcher.handle_action(chat_id, "save", app=object())

    assert result.success is False
    assert "couldn't register this persona with HeyGen yet" in result.error
    update_persona.assert_not_awaited()
    assert await TelegramSkillSessionStore.get_session(chat_id) is not None
