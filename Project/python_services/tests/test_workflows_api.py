from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from temporalio.api.enums.v1 import WorkflowExecutionStatus

from api import workflows
from services.contracts import ConceptBriefContract
from skills import video_ai as video_ai_module
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


def _approved_package_payload(persona_id: str = "persona-1") -> dict:
    return {
        "concept_brief": {
            "persona_id": persona_id,
            "feature_focus": "AI itinerary planner",
            "video_goal": "feature_demo",
            "audience": "young travelers",
            "angle": "problem_solution",
            "platform": "tiktok",
            "cta": "Try TripC free",
            "reference_url": "https://tripc.ai",
            "access_level": "public_page_only",
            "source_summary": "TripC is presented as a trip planning product.",
            "tone_resolved": "confident",
        },
        "beat_sheet": {
            "beats": [
                {
                    "idx": idx,
                    "purpose": purpose,
                    "bottom_half_message": f"Beat {idx} message",
                    "top_half_source_type": "public_page_capture",
                    "top_half_target": f"section_{idx}",
                    "top_half_capture_hint": f"Show section {idx}",
                    "overlay_text": f"Overlay {idx}",
                    "duration_sec": 4,
                }
                for idx, purpose in enumerate(
                    ["hook", "problem", "solution_intro", "feature_demo", "cta"],
                    start=1,
                )
            ]
        },
        "persona_snapshot": {"persona_id": persona_id},
    }


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
    assert response["status"]["status"]["status"] == "waiting_approval"
    assert response["status"]["execution_status"] == "running"
    assert response["status"]["source"] == "query"


@pytest.mark.asyncio
async def test_get_workflow_status_falls_back_to_terminal_result(monkeypatch):
    handle = AsyncMock()
    handle.query.side_effect = RuntimeError("workflow already closed")
    handle.describe.return_value = SimpleNamespace(
        raw_description=SimpleNamespace(
            workflow_execution_info=SimpleNamespace(
                status=WorkflowExecutionStatus.WORKFLOW_EXECUTION_STATUS_COMPLETED
            )
        )
    )
    handle.result.return_value = {
        "status": "failed",
        "workflow_id": "wf-closed",
        "metadata": {"reason": "module 'temporalio.workflow' has no attribute 'gather'"},
    }
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.get_workflow_status(request, workflow_id="wf-closed")

    assert response["workflow_id"] == "wf-closed"
    assert response["status"]["status"]["status"] == "failed"
    assert response["status"]["execution_status"] == "completed"
    assert response["status"]["source"] == "result"


@pytest.mark.asyncio
async def test_get_workflow_status_falls_back_to_completed_result(monkeypatch):
    handle = AsyncMock()
    handle.query.side_effect = RuntimeError("query unavailable after close")
    handle.describe.return_value = SimpleNamespace(
        status=SimpleNamespace(name="COMPLETED")
    )
    handle.result.return_value = {
        "status": "failed",
        "workflow_id": "wf-closed",
        "metadata": {"reason": "module 'temporalio.workflow' has no attribute 'gather'"},
    }
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.get_workflow_status(request, workflow_id="wf-closed")

    assert response["workflow_id"] == "wf-closed"
    assert response["status"]["status"]["status"] == "failed"
    assert response["status"]["execution_status"] == "completed"
    assert response["status"]["source"] == "result"
    handle.result.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_workflow_status_falls_back_to_describe_for_running_workflow(
    monkeypatch,
):
    handle = AsyncMock()
    handle.query.side_effect = RuntimeError("query unavailable")
    handle.describe.return_value = SimpleNamespace(
        status=SimpleNamespace(name="RUNNING")
    )
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.get_workflow_status(request, workflow_id="wf-running")

    assert response["workflow_id"] == "wf-running"
    assert response["status"]["status"]["status"] == "running"
    assert response["status"]["status"]["current_step"] == "running"
    assert response["status"]["execution_status"] == "running"
    assert response["status"]["source"] == "describe"
    handle.result.assert_not_awaited()


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
async def test_list_workflows_queries_weekly_and_short_video(monkeypatch):
    captured = {}

    async def iter_workflows(*_args, **_kwargs):
        if False:
            yield None

    def fake_list_workflows(query):
        captured["query"] = query
        return iter_workflows()

    mock_client = SimpleNamespace(list_workflows=fake_list_workflows)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.list_workflows(request, limit=10)

    assert response["workflows"] == []
    assert "WeeklyMarketingWorkflow" in captured["query"]
    assert "ShortVideoWorkflow" in captured["query"]


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
async def test_start_video_workflow_rejects_missing_heygen_avatar_when_talking_head_required(
    monkeypatch,
):
    """When talking_head_optional=False (default), missing heygen_avatar_id should be rejected."""
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
    monkeypatch.setattr(
        workflows.PersonaRegistryService, "get_persona", fake_get_persona
    )

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    payload = workflows.StartVideoRequest(
        persona_id="persona-1",
        topic="Da Nang travel tips",
        tone="natural",
        platform="tiktok",
        telegram_chat_id="123456",
        # talking_head_optional defaults to False
    )

    with pytest.raises(HTTPException) as exc_info:
        await workflows.start_video_workflow(request, payload)

    assert exc_info.value.status_code == 400
    assert "heygen_avatar_id" in exc_info.value.detail


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
    monkeypatch.setattr(
        workflows.PersonaRegistryService, "get_persona", fake_get_persona
    )

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
    assert started_payload["owner_key"] == "telegram:999"
    assert started_payload["persona_snapshot"] == {
        "display_name": None,
        "language": "English",
        "tts_voice": "male_friendly",
        "heygen_avatar_id": None,
    }


@pytest.mark.asyncio
async def test_start_video_workflow_passes_validated_approved_package_and_snapshot(
    monkeypatch,
):
    handle = SimpleNamespace(id="run-video-3")
    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    async def fake_get_persona(_persona_id, user_id=None, owner_key=None):
        return {
            "persona_id": "persona-3",
            "display_name": "Persona 3",
            "language": "Vietnamese",
            "status": "ready",
            "tts_voice": "vi-VN-Neural2-A",
            "heygen_avatar_id": "avatar-3",
        }

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)
    monkeypatch.setattr(
        workflows.PersonaRegistryService, "get_persona", fake_get_persona
    )

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    payload = workflows.StartVideoRequest(
        persona_id="persona-3",
        topic="Hoi An cafe guide",
        telegram_chat_id="333",
        approved_package=_approved_package_payload("persona-3"),
    )

    response = await workflows.start_video_workflow(request, payload)

    assert response["status"] == "started"
    started_payload = mock_client.start_workflow.await_args.kwargs["args"][0]
    assert started_payload["approved_package"]["concept_brief"]["persona_id"] == "persona-3"
    assert started_payload["approved_package"]["beat_sheet"]["beats"][0]["purpose"] == "hook"
    assert started_payload["persona_snapshot"] == {
        "display_name": "Persona 3",
        "language": "Vietnamese",
        "tts_voice": "vi-VN-Neural2-A",
        "heygen_avatar_id": "avatar-3",
    }


@pytest.mark.asyncio
async def test_start_video_workflow_passes_review_plan_and_execution_mode(monkeypatch):
    handle = SimpleNamespace(id="run-video-4")
    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    async def fake_get_persona(_persona_id, user_id=None, owner_key=None):
        return {
            "persona_id": "persona-4",
            "display_name": "Persona 4",
            "language": "English",
            "status": "ready",
            "tts_voice": "en-US-Neural2-A",
            "heygen_avatar_id": None,
        }

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)
    monkeypatch.setattr(
        workflows.PersonaRegistryService, "get_persona", fake_get_persona
    )

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    payload = workflows.StartVideoRequest(
        persona_id="persona-4",
        topic="Create a short product review",
        telegram_chat_id="444",
        talking_head_optional=True,
        execution_mode="autonomous_screen_recording",
        review_plan={
            "planning_mode": "webpage_review",
            "objective": "Create a short product review",
            "target_url": "https://example.com",
            "language": "English",
            "persona_id": "persona-4",
            "execution_mode": "autonomous_screen_recording",
            "access_level": "public_page_only",
            "status": "confirmed",
        },
        audio_policy={
            "voiceover_required": True,
            "bgm_fallback_enabled": True,
            "bgm_library_profile": "product_explainer",
            "bgm_duck_under_voiceover": True,
            "max_bgm_duration_seconds": 60,
        },
    )

    response = await workflows.start_video_workflow(request, payload)

    assert response["status"] == "started"
    started_payload = mock_client.start_workflow.await_args.kwargs["args"][0]
    assert started_payload["execution_mode"] == "autonomous_screen_recording"
    assert started_payload["review_plan"]["target_url"] == "https://example.com"
    assert started_payload["audio_policy"]["bgm_fallback_enabled"] is True


def test_start_video_request_rejects_invalid_approved_package():
    with pytest.raises(ValidationError):
        workflows.StartVideoRequest(
            persona_id="persona-4",
            topic="Broken package",
            approved_package={"concept_brief": {"persona_id": "persona-4"}},
        )


@pytest.mark.asyncio
async def test_video_ai_skill_legacy_topic_payload_no_longer_starts_workflow(
    monkeypatch,
):
    session = VideoAISkill.initial_session()
    session.collected["persona_id"] = "persona-1"
    session.collected["topic"] = "Weekend beach trip"
    session.collected["creative_input_mode"] = "idea_brief"

    request_mock = AsyncMock(
        side_effect=AssertionError("Legacy workflow start should not run")
    )
    monkeypatch.setattr(VideoAISkill, "_request_json", request_mock)

    result = await VideoAISkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "collect_idea_brief"
    assert result.session is not None
    assert result.session.control.approval_required is False
    assert request_mock.await_count == 0


@pytest.mark.asyncio
async def test_video_ai_skill_requires_reference_url_before_generation(monkeypatch):
    session = VideoAISkill.initial_session()
    session.collected.update(
        {
            "persona_id": "persona-legacy",
            "creative_input_mode": "idea_brief",
            "idea_brief": "Sunset cruise concept",
            "feature_focus": "Trip planning",
            "video_goal": "feature_demo",
            "audience": "young travelers",
            "cta": "Try TripC free",
        }
    )

    request_mock = AsyncMock(
        side_effect=AssertionError("Persona lookup should wait for full brief")
    )
    monkeypatch.setattr(VideoAISkill, "_request_json", request_mock)

    result = await VideoAISkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "collect_reference_url"
    assert request_mock.await_count == 0


@pytest.mark.asyncio
async def test_video_ai_skill_builds_concept_preview_instead_of_starting_workflow(
    monkeypatch,
):
    session = VideoAISkill.initial_session()
    session.collected.update(
        {
            "persona_id": "persona-1",
            "creative_input_mode": "idea_brief",
            "idea_brief": "Weekend beach trip planner",
            "feature_focus": "AI itinerary planner",
            "video_goal": "feature_demo",
            "audience": "young travelers",
            "cta": "Try TripC free",
            "reference_url": "https://tripc.ai",
            "access_level": "public_page_only",
        }
    )

    async def fake_request_json(cls, http_client, method, backend_url, path, **kwargs):
        if path.endswith("/readiness"):
            return {"ready": True}
        if path.endswith("/api/personas/persona-1"):
            return {
                "persona_id": "persona-1",
                "display_name": "Persona 1",
                "language": "English",
                "tts_voice": "en-US-Neural2-A",
                "tone_default": "confident",
                "status": "ready",
                "heygen_avatar_id": "avatar-1",
            }
        raise AssertionError(f"Unexpected path: {path}")

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return ConceptBriefContract(
            persona_id="persona-1",
            feature_focus=collected["feature_focus"],
            video_goal=collected["video_goal"],
            audience=collected["audience"],
            angle="problem_solution",
            platform="tiktok",
            cta=collected["cta"],
            reference_url=collected["reference_url"],
            access_level=collected["access_level"],
            source_summary="TripC is presented as a trip planning product.",
            tone_resolved=persona_snapshot["tone_resolved"],
        )

    monkeypatch.setattr(VideoAISkill, "_request_json", classmethod(fake_request_json))
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )

    result = await VideoAISkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "confirm_concept"
    assert result.session is not None
    assert result.session.step_key == "confirm_concept"
    assert result.session.control.status.value == "preview_ready"
    assert result.session.artifacts.get("workflow_id") is None
    assert result.output["concept_brief"]["reference_url"] == "https://tripc.ai"
