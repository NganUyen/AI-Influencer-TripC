from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from services.errors import HeyGenTimeoutError
from services import heygen_service as heygen_service_module
from services import persona_registry_service as persona_registry_service_module
from services.skill_dispatcher import SkillDispatcher
from services.skill_session_store import TelegramSkillSessionStore
from skills import SKILL_REGISTRY
from skills.base import SkillControl, SkillResult, SkillSession, SkillStatus


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


@pytest.mark.asyncio
async def test_save_persona_action_clears_session_after_marking_ready(monkeypatch):
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

    class FakeHeyGenService:
        async def wait_for_avatar_ready(self, avatar_id: str, **_kwargs):
            assert avatar_id == "heygen-789"
            return {"data": {"id": avatar_id, "status": "ready"}}

    monkeypatch.setattr(
        heygen_service_module,
        "HeyGenService",
        FakeHeyGenService,
    )

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

        async def wait_for_avatar_ready(self, avatar_id: str, **_kwargs):
            assert avatar_id == "heygen-456"
            return {"data": {"id": avatar_id, "status": "ready"}}

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
async def test_save_persona_keeps_draft_while_heygen_is_still_processing(monkeypatch):
    chat_id = 123987
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
            return "heygen-456"

        async def wait_for_avatar_ready(self, avatar_id: str, **_kwargs):
            raise HeyGenTimeoutError("HeyGen is still processing this avatar")

    captured_update = {}

    async def fake_update_persona(
        persona_id, payload, *, user_id=None, owner_key=None
    ):
        captured_update["persona_id"] = persona_id
        captured_update["payload"] = payload
        return {
            "persona_id": persona_id,
            "status": "draft",
            "language": "English",
            "tts_voice": "en-US-Studio-O",
            "avatar_image_url": "https://cdn.example/hero-host.png",
            "avatar_media_asset_id": "media-123",
            "heygen_avatar_id": "heygen-456",
            "avatar_source_type": "generated",
        }

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
    assert result.next_step == "preview"
    assert result.output["status"] == "pending_heygen_avatar"
    assert "still processing" in result.output["message"]
    assert captured_update["payload"]["heygen_avatar_id"] == "heygen-456"
    assert "status" not in captured_update["payload"]

    stored_session = await TelegramSkillSessionStore.get_session(chat_id)
    assert stored_session is not None
    assert stored_session.artifacts["heygen_avatar_id"] == "heygen-456"
    assert "HeyGen is still processing this avatar" in result.output["readiness"]["blocking_reason"]


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


@pytest.mark.asyncio
async def test_persona_ready_action_alias_maps_to_save(monkeypatch):
    chat_id = 13579
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
            "heygen_avatar_id": "heygen-999",
            "persona_data": {"avatar_source_type": "generated"},
        },
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    class FakeHeyGenService:
        async def wait_for_avatar_ready(self, avatar_id: str, **_kwargs):
            assert avatar_id == "heygen-999"
            return {"data": {"id": avatar_id, "status": "ready"}}

    monkeypatch.setattr(heygen_service_module, "HeyGenService", FakeHeyGenService)

    with patch(
        "services.persona_registry_service.PersonaRegistryService.update_persona",
        AsyncMock(return_value={"persona_id": "hero-host", "status": "ready"}),
    ) as update_persona:
        result = await SkillDispatcher.handle_action(chat_id, "ready", app=object())

    assert result.success is True
    update_persona.assert_awaited_once()


@pytest.mark.asyncio
async def test_persona_confirm_dream_action_sets_collected_flag(monkeypatch):
    chat_id = 24680
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="persona-creator",
        step_key="confirm_dream",
        collected={
            "creation_mode": "dream",
            "nationality": "Jamaican",
            "voice": "female_warm",
            "language": "English",
            "dream_brief": "fitness coach in an urban gym",
            "persona_id": "jamaican_creator",
            "appearance_prompt_or_photo": "portrait in gym",
        },
        artifacts={"telegram_chat_id": str(chat_id), "dream_ready": True},
        control=SkillControl(status=SkillStatus.collecting),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _FakeClient:
        async def request(self, method, url, params=None, json=None, headers=None):
            return _FakeResponse(
                {
                    "persona_id": "jamaican_creator",
                    "status": "draft",
                    "language": "English",
                    "tts_voice": "en-US-Studio-O",
                    "avatar_image_url": "https://cdn.example/a.png",
                    "avatar_media_asset_id": "media-1",
                    "heygen_avatar_id": "heygen-1",
                }
            )

    monkeypatch.setattr(
        SkillDispatcher,
        "_transport_client",
        lambda _app: _AsyncClientContext(_FakeClient()),
    )

    result = await SkillDispatcher.handle_action(chat_id, "confirm", app=object())

    assert result.session is not None
    assert result.session.collected.get("dream_confirmed") == "confirm"


@pytest.mark.asyncio
async def test_prepare_prompt_session_filters_video_planner_personas_to_ready(monkeypatch):
    session = SkillSession(
        skill_name="video-planner",
        step_key="pick_persona",
        artifacts={"telegram_chat_id": "555"},
        control=SkillControl(status=SkillStatus.collecting),
    )

    async def fake_fetch_personas(_app, *, ready_only, owner_key=None):
        assert ready_only is True
        assert owner_key == "telegram:555"
        return [{"persona_id": "persona-1", "status": "ready"}]

    monkeypatch.setattr(SkillDispatcher, "_fetch_personas", fake_fetch_personas)

    prepared = await SkillDispatcher._prepare_prompt_session(object(), session)

    assert prepared.artifacts["available_personas"][0]["persona_id"] == "persona-1"


@pytest.mark.asyncio
async def test_video_ai_demo_preview_approve_routes_to_preview_handler(monkeypatch):
    chat_id = 998877
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="video-ai",
        step_key="demo_preview_confirm",
        collected={},
        artifacts={"telegram_chat_id": str(chat_id)},
        control=SkillControl(status=SkillStatus.collecting),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    class _FakeVideoSkill:
        @classmethod
        async def handle_demo_preview_action(
            cls,
            session,
            action,
            backend_url,
            client,
            *,
            correction_text=None,
            reemphasis_text=None,
        ):
            return SkillResult(
                success=True,
                next_step="confirm_concept",
                session=session,
                output={"routed_to": "demo_preview", "action": action},
            )

        @classmethod
        async def handle_preproduction_action(cls, *args, **kwargs):
            raise AssertionError("preproduction handler should not be used")

    monkeypatch.setitem(SKILL_REGISTRY, "video-ai", _FakeVideoSkill)
    monkeypatch.setattr(
        SkillDispatcher,
        "_transport_client",
        lambda _app: _AsyncClientContext(SimpleNamespace()),
    )

    result = await SkillDispatcher.handle_action(chat_id, "approve", app=object())

    assert result.success is True
    assert result.output == {"routed_to": "demo_preview", "action": "approve"}


@pytest.mark.asyncio
async def test_handle_video_upload_bridges_legacy_video_planner_session(monkeypatch):
    chat_id = 223344
    await TelegramSkillSessionStore.clear_session(chat_id)
    session = SkillSession(
        skill_name="video-planner",
        step_key="upload_manual_video",
        artifacts={
            "telegram_chat_id": str(chat_id),
            "video_review_plan": {
                "plan_id": "plan-1",
                "planning_mode": "webpage_review",
                "objective": "Create a walkthrough",
                "target_url": "https://example.com",
                "language": "English",
                "persona_id": "persona-1",
                "execution_mode": "manual_mobile_recording",
                "access_level": "public_page_only",
                "status": "confirmed",
            },
        },
        control=SkillControl(status=SkillStatus.collecting),
    )
    await TelegramSkillSessionStore.set_session(chat_id, session)

    quality_report = SimpleNamespace(
        passed=True,
        duration_sec=9.5,
        resolution_string="1080x1920",
        file_size_bytes=2048,
        has_warnings=False,
        warnings=[],
        model_dump=lambda: {
            "passed": True,
            "duration_sec": 9.5,
            "resolution_string": "1080x1920",
            "file_size_bytes": 2048,
            "has_warnings": False,
            "warnings": [],
        },
    )

    bridged_result = SkillResult(
        success=True,
        next_step="poll_status",
        output={"message": "Upload processed."},
        session=SkillSession(
            skill_name="video-ai",
            step_key="package_ready",
            artifacts={"workflow_id": "wf-1"},
            control=SkillControl(
                status=SkillStatus.waiting_approval,
                workflow_id="wf-1",
            ),
        ),
    )

    monkeypatch.setattr(
        SkillDispatcher,
        "_transport_client",
        lambda _app: _AsyncClientContext(SimpleNamespace()),
    )

    with (
        patch(
            "services.video_quality_gate_service.VideoQualityGateService.validate_video_file",
            AsyncMock(return_value=quality_report),
        ),
        patch(
            "services.media_storage_service.MediaStorageService.upload_bytes",
            AsyncMock(
                return_value={
                    "media_asset_id": "asset-1",
                    "access_url": "https://cdn.example/demo.mp4",
                }
            ),
        ),
        patch(
            "skills.video_planner.VideoPlannerSkill.continue_manual_mobile_pipeline",
            AsyncMock(return_value=bridged_result),
        ) as continue_manual_mobile_pipeline,
    ):
        result = await SkillDispatcher.handle_video_upload(
            chat_id,
            file_id="tg-file-1",
            data=b"video-bytes",
            content_type="video/mp4",
            filename="demo.mp4",
            app=object(),
        )

    assert result is not None
    assert result.success is True
    assert result.session is not None
    assert result.session.skill_name == "video-ai"
    continue_manual_mobile_pipeline.assert_awaited_once()
    kwargs = continue_manual_mobile_pipeline.await_args.kwargs
    assert kwargs["file_id"] == "tg-file-1"
    assert kwargs["asset_url"] == "https://cdn.example/demo.mp4"
    assert kwargs["asset_id"] == "asset-1"
