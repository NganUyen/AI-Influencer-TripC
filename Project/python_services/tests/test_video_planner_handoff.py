from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services.contracts import VideoReviewPlanContract
from services.video_planner_handoff_service import VideoPlannerHandoffService
from skills.video_planner import VideoPlannerSkill


def _confirmed_plan(execution_mode: str = "autonomous_screen_recording") -> VideoReviewPlanContract:
    plan = VideoReviewPlanContract(
        planning_mode="webpage_review",
        objective="Create a short product review",
        target_url="https://example.com",
        language="English",
        persona_id="persona-1",
        execution_mode=execution_mode,
        access_level="public_page_only",
        status="confirmed",
    )
    return plan


@pytest.mark.asyncio
async def test_video_planner_handoff_starts_workflow_for_autonomous_mode():
    http_client = AsyncMock()
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"workflow_id": "video-123", "status": "started"},
    )
    http_client.post.return_value = response

    result = await VideoPlannerHandoffService.start_confirmed_plan(
        plan=_confirmed_plan(),
        persona_snapshot={"persona_id": "persona-1"},
        backend_url="http://backend",
        http_client=http_client,
        telegram_chat_id="555",
    )

    assert result["workflow_id"] == "video-123"
    payload = http_client.post.await_args.kwargs["json"]
    assert payload["execution_mode"] == "autonomous_screen_recording"
    assert payload["talking_head_optional"] is True
    assert payload["review_plan"]["status"] == "confirmed"


@pytest.mark.asyncio
async def test_video_planner_handoff_blocks_authenticated_mode_without_workflow_start():
    http_client = AsyncMock()

    async def fake_resolve_user_id(owner_key, allow_fallback=False):
        assert owner_key == "telegram:555"
        return "11111111-1111-1111-1111-111111111111"

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        "services.video_planner_handoff_service.TelegramLinkService.resolve_user_id_for_owner_key",
        fake_resolve_user_id,
    )

    try:
        result = await VideoPlannerHandoffService.start_confirmed_plan(
            plan=_confirmed_plan("authenticated_pc_recording"),
            persona_snapshot={"persona_id": "persona-1"},
            backend_url="http://backend",
            http_client=http_client,
            telegram_chat_id="555",
        )
    finally:
        monkeypatch.undo()

    assert result["status"] == "handoff_required"
    assert result["handoff_url"].startswith("http")
    assert http_client.post.await_count == 0


@pytest.mark.asyncio
async def test_video_planner_confirm_routes_to_handoff_and_persists_workflow(monkeypatch):
    session = VideoPlannerSkill.initial_session()
    session.step_key = "confirm_plan"
    session.collected.update(
        {
            "objective": "Create a short product review",
            "target_url": "https://example.com",
            "language": "English",
            "persona_id": "persona-1",
            "execution_mode": "autonomous_screen_recording",
            "plan_decision": "confirm",
        }
    )
    session.artifacts.update(
        {
            "telegram_chat_id": "555",
            "video_review_plan": _confirmed_plan().model_copy(update={"status": "draft"}).model_dump(mode="json"),
        }
    )

    async def fake_handoff(**kwargs):
        assert kwargs["plan"].status == "confirmed"
        return {
            "status": "started",
            "workflow_id": "video-xyz",
            "message": "Autonomous execution started.",
            "execution_mode": "autonomous_screen_recording",
        }

    monkeypatch.setattr(
        "skills.video_planner.VideoPlannerHandoffService.start_confirmed_plan",
        fake_handoff,
    )

    result = await VideoPlannerSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.output["workflow_id"] == "video-xyz"
    assert result.session.control.workflow_id == "video-xyz"


@pytest.mark.asyncio
async def test_video_planner_confirm_manual_mode_waits_for_upload(monkeypatch):
    session = VideoPlannerSkill.initial_session()
    session.step_key = "confirm_plan"
    session.collected.update(
        {
            "objective": "Turn my phone recording into a review video",
            "target_url": "https://example.com",
            "language": "English",
            "persona_id": "persona-1",
            "execution_mode": "manual_mobile_recording",
            "plan_decision": "confirm",
        }
    )
    session.artifacts.update(
        {
            "telegram_chat_id": "555",
            "video_review_plan": _confirmed_plan("manual_mobile_recording")
            .model_copy(update={"status": "draft"})
            .model_dump(mode="json"),
        }
    )

    async def fake_handoff(**kwargs):
        return {
            "status": "awaiting_manual_upload",
            "message": "Upload the recorded mobile video next.",
            "execution_mode": "manual_mobile_recording",
        }

    monkeypatch.setattr(
        "skills.video_planner.VideoPlannerHandoffService.start_confirmed_plan",
        fake_handoff,
    )

    result = await VideoPlannerSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "upload_manual_video"
    assert result.session.step_key == "upload_manual_video"


@pytest.mark.asyncio
async def test_video_planner_manual_mobile_pipeline_bridges_into_video_ai(monkeypatch):
    session = VideoPlannerSkill.initial_session()
    session.artifacts["telegram_chat_id"] = "555"
    session.artifacts["video_review_plan"] = _confirmed_plan("manual_mobile_recording").model_dump(mode="json")

    async def fake_analysis(cls, session_obj, backend_url, http_client):
        return SimpleNamespace(model_dump=lambda mode="json": {"grounded_features": [], "confidence_signals": {}})

    async def fake_execute(cls, session_obj, backend_url, http_client):
        if not session_obj.artifacts.get("concept_approved"):
            session_obj.artifacts["concept_brief"] = {"ok": True}
            return SimpleNamespace(success=True, next_step="confirm_concept", session=session_obj)
        if not session_obj.artifacts.get("beat_sheet_approved"):
            session_obj.artifacts["beat_sheet"] = {"ok": True}
            return SimpleNamespace(success=True, next_step="confirm_beats", session=session_obj)
        return SimpleNamespace(success=True, next_step="poll_status", session=session_obj)

    monkeypatch.setattr("skills.video_ai.VideoAISkill._run_demo_analysis_and_grounding", classmethod(fake_analysis))
    monkeypatch.setattr("skills.video_ai.VideoAISkill.execute", classmethod(fake_execute))

    result = await VideoPlannerSkill.continue_manual_mobile_pipeline(
        session,
        backend_url="http://backend",
        http_client=AsyncMock(),
        file_id="file-1",
        asset_url="https://cdn.example/manual.mp4",
        asset_id="asset-1",
        filename="manual.mp4",
        quality_report={"resolution_string": "1080x1920"},
    )

    assert result.success is True
    assert result.next_step == "poll_status"
    assert result.session.collected["platform"] == "tiktok"
    assert result.session.collected["demo_video_asset_url"] == "https://cdn.example/manual.mp4"


@pytest.mark.asyncio
async def test_complete_authenticated_handoff_starts_workflow(monkeypatch):
    http_client = AsyncMock()
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"workflow_id": "video-auth-1", "status": "started"},
    )
    http_client.post.return_value = response

    result = await VideoPlannerHandoffService.complete_authenticated_handoff(
        handoff_payload={
            "review_plan": _confirmed_plan("authenticated_pc_recording").model_dump(mode="json"),
            "telegram_chat_id": "555",
        },
        method="workspace_session_capture",
        notes="Secure session ready.",
        backend_url="http://backend",
        http_client=http_client,
    )

    assert result["workflow_id"] == "video-auth-1"
    assert result["credential_handoff"]["status"] == "completed"
    assert any("completion_method:workspace_session_capture" == note for note in result["credential_handoff"]["notes"])
