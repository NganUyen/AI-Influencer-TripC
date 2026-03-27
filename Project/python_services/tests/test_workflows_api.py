from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api import workflows
from skills.video_ai import VideoAISkill


class _WorkflowStatus:
    def __init__(self, name: str):
        self.name = name


class _WorkflowItem:
    def __init__(self, workflow_id: str, run_id: str, status: str):
        self.id = workflow_id
        self.run_id = run_id
        self.status = _WorkflowStatus(status)
        self.start_time = datetime(2026, 3, 2, 10, 0, 0)


@pytest.mark.asyncio
async def test_start_weekly_workflow_returns_started(monkeypatch):
    handle = SimpleNamespace(id="run-123")

    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.start_weekly_workflow(
        request,
        user_id="user-1",
        brand_config={"tone": "friendly"},
    )

    assert response["workflow_id"] == "weekly-marketing-user-1"
    assert response["run_id"] == "run-123"
    assert response["status"] == "started"
    mock_client.start_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_workflow_sends_signal(monkeypatch):
    handle = AsyncMock()
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.approve_workflow(
        request,
        workflow_id="wf-approve",
        approved=True,
        feedback="ok",
    )

    assert response == {
        "workflow_id": "wf-approve",
        "approved": True,
        "status": "signal_sent",
    }
    handle.signal.assert_awaited_once_with("approve_strategy", True, "ok")


@pytest.mark.asyncio
async def test_get_workflow_status_returns_query(monkeypatch):
    handle = AsyncMock()
    handle.query.return_value = {
        "status": "waiting_approval",
        "workflow_id": "wf-1",
    }
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.get_workflow_status(request, workflow_id="wf-1")

    assert response["workflow_id"] == "wf-1"
    assert response["status"]["status"] == "waiting_approval"


@pytest.mark.asyncio
async def test_list_workflows_happy_path(monkeypatch):
    workflow_items = [
        _WorkflowItem("wf-1", "run-1", "RUNNING"),
        _WorkflowItem("wf-2", "run-2", "COMPLETED"),
    ]

    async def iter_workflows(*_args, **_kwargs):
        for item in workflow_items:
            yield item

    mock_client = SimpleNamespace(
        list_workflows=lambda *_args, **_kwargs: iter_workflows()
    )

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.list_workflows(request, limit=10)

    assert len(response["workflows"]) == 2
    assert response["workflows"][0]["workflow_id"] == "wf-1"
    assert response["workflows"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_workflow_api_converts_exceptions(monkeypatch):
    async def fake_get_temporal_client(_request):
        raise workflows.TemporalUnavailableError("temporal down")

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(HTTPException) as start_exc:
        await workflows.start_weekly_workflow(request, user_id="u", brand_config={})
    assert start_exc.value.status_code == 503

    response = await workflows.list_workflows(request)
    assert response["workflows"] == []
    assert response["temporal_available"] is False


@pytest.mark.asyncio
async def test_start_video_workflow_allows_missing_heygen_avatar(monkeypatch):
    handle = SimpleNamespace(id="run-video-1")
    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    async def fake_get_persona(_persona_id, user_id=None, owner_key=None):
        return {
            "persona_id": "persona-1",
            "status": "ready",
            "tts_voice": "male_friendly",
            "heygen_avatar_id": None,
        }

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)
    monkeypatch.setattr(workflows.PersonaRegistryService, "get_persona", fake_get_persona)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    payload = workflows.StartVideoRequest(
        persona_id="persona-1",
        topic="Da Nang travel tips",
        tone="natural",
        platform="tiktok",
        telegram_chat_id="123456",
    )

    response = await workflows.start_video_workflow(request, payload)

    assert response["status"] == "started"
    mock_client.start_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_video_workflow_passes_talking_head_optional(monkeypatch):
    handle = SimpleNamespace(id="run-video-2")
    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    async def fake_get_persona(_persona_id, user_id=None, owner_key=None):
        return {
            "persona_id": "persona-2",
            "status": "ready",
            "tts_voice": "male_friendly",
            "heygen_avatar_id": None,
        }

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)
    monkeypatch.setattr(workflows.PersonaRegistryService, "get_persona", fake_get_persona)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    payload = workflows.StartVideoRequest(
        persona_id="persona-2",
        topic="Hoi An cafe guide",
        telegram_chat_id="999",
        talking_head_optional=True,
    )

    response = await workflows.start_video_workflow(request, payload)

    assert response["status"] == "started"
    started_payload = mock_client.start_workflow.await_args.kwargs["args"][0]
    assert started_payload["talking_head_optional"] is True


@pytest.mark.asyncio
async def test_video_ai_skill_allows_fallback_when_heygen_missing(monkeypatch):
    session = VideoAISkill.initial_session()
    session.collected["persona_id"] = "persona-1"
    session.collected["topic"] = "Weekend beach trip"
    session.artifacts["telegram_chat_id"] = "123456"

    monkeypatch.setattr(
        VideoAISkill,
        "_request_json",
        AsyncMock(
        side_effect=[
            {
                "ready": False,
                "blocking_reason": "Missing heygen_avatar_id. Run persona avatar setup first.",
                "checks": {
                    "status_ready": True,
                    "has_tts_voice": True,
                    "has_avatar_asset": True,
                    "has_heygen_avatar_id": False,
                },
            },
            {
                "workflow_id": "video-wf-1",
                "run_id": "run-1",
                "status": "started",
            },
        ]
    ),
    )

    result = await VideoAISkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.session is not None
    assert result.session.control.approval_required is True
    assert result.session.artifacts["talking_head_optional"] is True
    assert result.output["workflow_id"] == "video-wf-1"


@pytest.mark.asyncio
async def test_video_ai_skill_accepts_legacy_avatar_image_fallback_flag(monkeypatch):
    session = VideoAISkill.initial_session()
    session.collected["persona_id"] = "persona-legacy"
    session.collected["topic"] = "Sunset cruise"
    session.artifacts["telegram_chat_id"] = "654321"

    monkeypatch.setattr(
        VideoAISkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "ready": False,
                    "blocking_reason": "Missing heygen_avatar_id. Run persona avatar setup first.",
                    "checks": {
                        "status_ready": True,
                        "has_tts_voice": True,
                        "has_avatar_image": True,
                        "has_heygen_avatar_id": False,
                    },
                },
                {
                    "workflow_id": "video-wf-legacy",
                    "run_id": "run-legacy",
                    "status": "started",
                },
            ]
        ),
    )

    result = await VideoAISkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.output["workflow_id"] == "video-wf-legacy"


@pytest.mark.asyncio
async def test_video_ai_skill_errors_when_workflow_id_missing(monkeypatch):
    session = VideoAISkill.initial_session()
    session.collected["persona_id"] = "persona-1"
    session.collected["topic"] = "Weekend beach trip"
    session.artifacts["telegram_chat_id"] = "123456"

    monkeypatch.setattr(
        VideoAISkill,
        "_request_json",
        AsyncMock(
            side_effect=[
                {
                    "ready": True,
                    "checks": {
                        "status_ready": True,
                        "has_tts_voice": True,
                        "has_avatar_asset": True,
                        "has_heygen_avatar_id": True,
                    },
                },
                {
                    "run_id": "run-1",
                    "status": "started",
                },
            ]
        ),
    )

    result = await VideoAISkill.execute(session, "http://backend", AsyncMock())

    assert result.success is False
    assert result.error == "Video workflow started without a workflow_id. Please try again."
