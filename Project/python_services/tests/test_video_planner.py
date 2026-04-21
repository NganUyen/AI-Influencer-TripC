from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from skills.base import SkillStatus
from skills.video_planner import VideoPlannerSkill


@pytest.mark.asyncio
async def test_confirmed_plan_with_workflow_marks_session_running(monkeypatch):
    session = VideoPlannerSkill.initial_session()
    session.step_key = "confirm_plan"
    session.collected.update(
        {
            "plan_decision": "confirm",
            "persona_id": "persona-1",
            "language": "English",
        }
    )
    session.artifacts["video_review_plan"] = {
        "plan_id": "plan-1",
        "objective": "Create a walkthrough",
        "target_url": "https://example.com",
        "language": "English",
        "persona_id": "persona-1",
        "execution_mode": "autonomous_screen_recording",
        "access_level": "public_page_only",
        "status": "confirmed",
        "credential_handoff": {"status": "not_required", "handoff_method": "none"},
        "audio_policy": {"voiceover_required": True},
        "page_review": {
            "target_url": "https://example.com",
            "normalized_url": "https://example.com",
            "page_title": "Example",
            "product_summary": "Summary",
            "page_fetch_method": "manual_summary",
            "access_level": "public_page_only",
            "login_required": False,
            "visible_features": [],
            "visible_flows": [],
            "recording_candidates": [],
            "risks": [],
            "assumptions": [],
        },
        "assumptions": [],
        "risks": [],
    }

    monkeypatch.setattr(
        VideoPlannerSkill,
        "_resolve_persona_snapshot",
        AsyncMock(
            return_value={
                "persona_id": "persona-1",
                "display_name": "Persona 1",
                "language": "English",
                "tts_voice": "en-US-Studio-O",
            }
        ),
    )

    with patch(
        "skills.video_planner.VideoPlannerHandoffService.start_confirmed_plan",
        AsyncMock(
            return_value={
                "status": "started",
                "message": "Workflow started.",
                "workflow_id": "wf-123",
                "execution_mode": "autonomous_screen_recording",
            }
        ),
    ):
        result = await VideoPlannerSkill.execute(
            session,
            backend_url="http://backend",
            http_client=SimpleNamespace(),
        )

    assert result.success is True
    assert result.session is not None
    assert result.next_step == "done"
    assert result.session.control.workflow_id == "wf-123"
    assert result.session.control.status == SkillStatus.running
