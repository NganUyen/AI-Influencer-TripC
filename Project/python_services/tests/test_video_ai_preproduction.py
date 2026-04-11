from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from config.settings import settings
from services.contracts import BeatSheetContract, ConceptBriefContract
from services.skill_dispatcher import SkillDispatcher
from services.skill_session_store import TelegramSkillSessionStore
from skills import video_ai as video_ai_module
from skills.video_ai import VideoAISkill


class _AsyncClientContext:
    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def reset_skill_session_store(monkeypatch):
    TelegramSkillSessionStore._redis_client = None
    TelegramSkillSessionStore._redis_enabled = False
    TelegramSkillSessionStore._redis_init_attempted = True
    TelegramSkillSessionStore._memory_sessions.clear()
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "FRONTEND_PUBLIC_URL", "http://localhost:3000")
    monkeypatch.setattr(settings, "BACKEND_PUBLIC_URL", "http://localhost:8000")
    monkeypatch.setattr(
        settings,
        "CHATGPT_CONNECTOR_PUBLIC_URL",
        "http://localhost:8000",
    )
    yield
    TelegramSkillSessionStore._memory_sessions.clear()


def _persona_payload():
    return {
        "persona_id": "minh_vn",
        "display_name": "Minh VN",
        "language": "Vietnamese",
        "tts_voice": "vi-VN-Neural2-A",
        "tone_default": "confident",
        "status": "ready",
        "heygen_avatar_id": "avatar_123",
    }


def _concept_contract():
    return ConceptBriefContract(
        persona_id="minh_vn",
        feature_focus="AI itinerary planner",
        video_goal="feature_demo",
        audience="travelers aged 22-35",
        angle="problem_solution",
        platform="tiktok",
        cta="Try TripC free",
        reference_url="https://tripc.ai",
        access_level="public_page_only",
        source_summary="TripC is presented as a travel planning product.",
        tone_resolved="confident",
    )


def _beat_sheet_contract():
    beats = []
    for idx, purpose in enumerate(
        ["hook", "problem", "solution_intro", "feature_demo", "cta"],
        start=1,
    ):
        beats.append(
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
        )
    return BeatSheetContract(beats=beats)


def _filled_session():
    session = VideoAISkill.initial_session()
    session.collected.update(
        {
            "persona_id": "minh_vn",
            "idea_brief": "Show how TripC plans trips faster.",
            "feature_focus": "AI itinerary planner",
            "video_goal": "feature_demo",
            "audience": "travelers aged 22-35",
            "cta": "Try TripC free",
            "reference_url": "https://tripc.ai",
            "access_level": "public_page_only",
        }
    )
    return session


def _mock_workflow_start_client(workflow_id: str = "video-minh_vn-test123"):
    mock_response = MagicMock()
    mock_response.json.return_value = {"workflow_id": workflow_id}
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_response
    return mock_http_client


def _patch_persona_lookup(monkeypatch):
    async def fake_request_json(cls, http_client, method, backend_url, path, **kwargs):
        # Strip query parameters for matching
        base_path = path.split("?")[0]
        if base_path.endswith("/readiness"):
            return {"ready": True}
        if base_path.endswith("/personas/minh_vn"):
            return _persona_payload()
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(VideoAISkill, "_request_json", classmethod(fake_request_json))


def _patch_persona_lookup_missing_heygen(monkeypatch):
    async def fake_request_json(cls, http_client, method, backend_url, path, **kwargs):
        base_path = path.split("?")[0]
        if base_path.endswith("/readiness"):
            return {
                "ready": False,
                "blocking_reason": "Missing heygen_avatar_id. Run persona avatar setup first.",
                "checks": {
                    "status_ready": True,
                    "has_tts_voice": True,
                    "has_avatar_asset": True,
                    "has_heygen_avatar_id": False,
                },
            }
        if base_path.endswith("/personas/minh_vn"):
            payload = _persona_payload()
            payload["heygen_avatar_id"] = None
            return payload
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(VideoAISkill, "_request_json", classmethod(fake_request_json))


@pytest.mark.asyncio
async def test_video_ai_collects_required_fields_in_order(monkeypatch):
    _patch_persona_lookup(monkeypatch)
    auto_plan = {
        "idea_brief": "Show how TripC handles login and booking.",
        "feature_focus": "Login and booking flow",
        "video_goal": "walkthrough",
        "audience": "travelers comparing booking tools",
        "cta": "Try TripC free",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
    }

    async def fake_build_preproduction_plan_from_review(
        cls,
        *,
        objective,
        target_url,
        page_review,
        persona_snapshot,
        platform="tiktok",
    ):
        assert objective == "Need a product demo."
        assert target_url == "https://tripc.ai"
        assert persona_snapshot["persona_id"] == "minh_vn"
        return auto_plan

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        assert collected["feature_focus"] == auto_plan["feature_focus"]
        assert collected["video_goal"] == auto_plan["video_goal"]
        assert collected["audience"] == auto_plan["audience"]
        assert collected["cta"] == auto_plan["cta"]
        return _concept_contract().model_copy(
            update={
                "feature_focus": auto_plan["feature_focus"],
                "video_goal": auto_plan["video_goal"],
                "audience": auto_plan["audience"],
                "cta": auto_plan["cta"],
            }
        )

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_preproduction_plan_from_review",
        classmethod(fake_build_preproduction_plan_from_review),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    session = VideoAISkill.initial_session()

    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_objective"

    session.collected["objective"] = "Need a product demo."
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_target_url"

    session.collected["target_url"] = "https://tripc.ai"
    session.artifacts["page_review"] = {
        "target_url": "https://tripc.ai",
        "normalized_url": "https://tripc.ai",
        "page_title": "TripC",
        "product_summary": "Trip planner",
        "access_level": "public_page_only",
        "login_required": False,
        "visible_features": [],
        "visible_flows": [],
        "recording_candidates": [],
        "risks": [],
        "assumptions": [],
    }
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "pick_persona"

    session.collected["persona_id"] = "minh_vn"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "choose_execution_mode"

    session.collected["execution_mode"] = "autonomous_screen_recording"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "confirm_plan"

    session.step_key = "confirm_plan"
    session.collected["plan_decision"] = "confirm"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "confirm_concept"

    assert result.session.collected["idea_brief"] == auto_plan["idea_brief"]
    assert result.session.collected["reference_url"] == "https://tripc.ai"
    assert result.session.collected["creative_input_mode"] == "idea_brief"
    assert result.session.collected["feature_focus"] == auto_plan["feature_focus"]
    assert result.session.collected["video_goal"] == auto_plan["video_goal"]
    assert result.session.collected["audience"] == auto_plan["audience"]
    assert result.session.collected["cta"] == auto_plan["cta"]


@pytest.mark.asyncio
async def test_video_ai_keeps_planning_flow_when_website_review_sets_access_level():
    session = VideoAISkill.initial_session()
    session.collected.update(
        {
            "objective": "Need a product demo.",
            "target_url": "https://tripc.ai",
            "persona_id": "minh_vn",
            "access_level": "public_page_only",
        }
    )
    session.artifacts["page_review"] = {
        "target_url": "https://tripc.ai",
        "normalized_url": "https://tripc.ai",
        "page_title": "TripC",
        "product_summary": "Trip planner",
        "access_level": "public_page_only",
        "login_required": False,
        "visible_features": [],
        "visible_flows": [],
        "recording_candidates": [],
        "risks": [],
        "assumptions": [],
    }

    result = await VideoAISkill.execute(session, "http://backend", object())

    assert result.success is True
    assert result.next_step == "choose_execution_mode"
    assert result.session.step_key == "choose_execution_mode"
    assert result.session.collected["creative_input_mode"] is None


@pytest.mark.asyncio
async def test_video_ai_autofills_stale_reference_url_step_after_plan_confirmation(
    monkeypatch,
):
    _patch_persona_lookup(monkeypatch)
    auto_plan = {
        "idea_brief": "Walk through TripC login and booking.",
        "feature_focus": "Login and booking flow",
        "video_goal": "walkthrough",
        "audience": "travelers booking their first trip",
        "cta": "Try TripC free",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
    }

    async def fake_build_preproduction_plan_from_review(
        cls,
        *,
        objective,
        target_url,
        page_review,
        persona_snapshot,
        platform="tiktok",
    ):
        assert objective == "Record a walkthrough"
        assert target_url == "https://tripc.ai"
        assert persona_snapshot["persona_id"] == "minh_vn"
        return auto_plan

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        assert collected["reference_url"] == "https://tripc.ai"
        assert collected["feature_focus"] == auto_plan["feature_focus"]
        return _concept_contract().model_copy(
            update={
                "feature_focus": auto_plan["feature_focus"],
                "video_goal": auto_plan["video_goal"],
                "audience": auto_plan["audience"],
                "cta": auto_plan["cta"],
                "reference_url": auto_plan["reference_url"],
                "access_level": auto_plan["access_level"],
            }
        )

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_preproduction_plan_from_review",
        classmethod(fake_build_preproduction_plan_from_review),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )

    session = VideoAISkill.initial_session()
    session.step_key = "collect_reference_url"
    session.collected.update(
        {
            "objective": "Record a walkthrough",
            "target_url": "https://tripc.ai",
            "persona_id": "minh_vn",
            "execution_mode": "autonomous_screen_recording",
            "creative_input_mode": "idea_brief",
            "idea_brief": "Record a walkthrough",
        }
    )
    session.artifacts["plan_confirmed"] = True
    session.artifacts["page_review"] = {
        "target_url": "https://tripc.ai",
        "normalized_url": "https://tripc.ai",
        "page_title": "TripC",
        "product_summary": "Trip planner",
        "access_level": "public_page_only",
        "login_required": False,
        "visible_features": [],
        "visible_flows": [],
        "recording_candidates": [],
        "risks": [],
        "assumptions": [],
    }

    result = await VideoAISkill.execute(session, "http://backend", object())

    assert result.success is True
    assert result.next_step == "confirm_concept"
    assert result.session.step_key == "confirm_concept"
    assert result.session.collected["reference_url"] == "https://tripc.ai"
    assert result.session.collected["video_goal"] == "walkthrough"


@pytest.mark.asyncio
async def test_video_ai_builds_concept_with_persona_tone(monkeypatch):
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        concept = _concept_contract()
        assert persona_snapshot["tone_resolved"] == "confident"
        return concept

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )

    session = _filled_session()
    result = await VideoAISkill.execute(session, "http://backend", object())

    assert result.success is True
    assert result.session.step_key == "confirm_concept"
    assert result.session.artifacts["persona_snapshot"]["tone_resolved"] == "confident"
    assert result.session.artifacts["concept_brief"]["tone_resolved"] == "confident"


@pytest.mark.asyncio
async def test_video_ai_allows_voiceover_only_fallback_when_heygen_avatar_missing(
    monkeypatch,
):
    _patch_persona_lookup_missing_heygen(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        assert persona_snapshot["heygen_avatar_id"] is None
        return _concept_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )

    session = _filled_session()
    result = await VideoAISkill.execute(session, "http://backend", object())

    assert result.success is True
    assert result.session.step_key == "confirm_concept"
    assert result.session.artifacts["talking_head_optional"] is True
    assert "voiceover instead" in result.session.artifacts["production_note"]
    assert result.session.artifacts["persona_readiness"]["ready"] is False
    assert result.session.artifacts["concept_brief"]["persona_id"] == "minh_vn"


@pytest.mark.asyncio
async def test_video_ai_approval_flow_reaches_package_ready(monkeypatch):
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    mock_http_client = _mock_workflow_start_client("video-minh_vn-flow")

    session = _filled_session()
    session.artifacts["telegram_chat_id"] = "123456"
    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    package_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )

    assert beat_result.session.step_key == "confirm_beats"
    assert package_result.session.step_key == "package_ready"
    assert package_result.next_step == "poll_status"
    assert package_result.session.control.status.value == "waiting_approval"
    assert package_result.session.control.workflow_id == "video-minh_vn-flow"
    assert package_result.session.artifacts["workflow_id"] == "video-minh_vn-flow"
    assert (
        package_result.session.artifacts["approved_production_package"][
            "concept_brief"
        ]["persona_id"]
        == "minh_vn"
    )


@pytest.mark.asyncio
async def test_dispatcher_persists_video_ai_package_ready_session(monkeypatch):
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    mock_http_client = _mock_workflow_start_client("video-minh_vn-dispatch")
    monkeypatch.setattr(
        SkillDispatcher,
        "_transport_client",
        lambda _app: _AsyncClientContext(mock_http_client),
    )

    session = _filled_session()
    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    await TelegramSkillSessionStore.set_session(123, concept_result.session)

    app = FastAPI()
    beat_result = await SkillDispatcher.handle_action(123, "approve", app)
    stored = await TelegramSkillSessionStore.get_session(123)

    assert beat_result.session.step_key == "confirm_beats"
    assert stored is not None
    assert stored.artifacts["beat_sheet"] is not None

    await TelegramSkillSessionStore.set_session(123, deepcopy(beat_result.session))
    package_result = await SkillDispatcher.handle_action(123, "approve", app)
    stored = await TelegramSkillSessionStore.get_session(123)

    assert package_result.session.step_key == "package_ready"
    assert stored is not None
    assert stored.artifacts["approved_production_package"] is not None
    assert stored.artifacts["workflow_id"] == "video-minh_vn-dispatch"
    assert stored.control.workflow_id == "video-minh_vn-dispatch"
    assert stored.control.status.value == "waiting_approval"


@pytest.mark.asyncio
async def test_video_ai_beat_generation_failure_stays_retryable(monkeypatch):
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        raise ValueError("temporary OpenClaw error")

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    session = _filled_session()
    concept_result = await VideoAISkill.execute(session, "http://backend", object())
    failed_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        object(),
    )

    assert failed_result.success is False
    assert failed_result.session.step_key == "confirm_beats"
    assert failed_result.output["retryable"] is True
    assert failed_result.session.artifacts["concept_approved"] is True


@pytest.mark.asyncio
async def test_video_ai_edit_restarts_from_review_plan(monkeypatch):
    session = VideoAISkill.initial_session()
    session.step_key = "confirm_concept"
    session.collected.update(
        {
            "objective": "Record a walkthrough",
            "target_url": "https://tripc.ai",
            "persona_id": "minh_vn",
            "execution_mode": "autonomous_screen_recording",
            "creative_input_mode": "idea_brief",
            "idea_brief": "Walk through TripC login and booking.",
            "feature_focus": "Login and booking flow",
            "video_goal": "walkthrough",
            "audience": "travelers booking their first trip",
            "cta": "Try TripC free",
            "reference_url": "https://tripc.ai",
            "access_level": "public_page_only",
        }
    )
    session.artifacts["plan_confirmed"] = True
    session.artifacts["page_review"] = {
        "target_url": "https://tripc.ai",
        "normalized_url": "https://tripc.ai",
        "page_title": "TripC",
        "product_summary": "Trip planner",
        "access_level": "public_page_only",
        "login_required": False,
        "visible_features": [],
        "visible_flows": [],
        "recording_candidates": [],
        "risks": [],
        "assumptions": [],
    }
    session.artifacts["concept_brief"] = _concept_contract().model_dump(mode="json")

    result = await VideoAISkill.handle_preproduction_action(
        session,
        "edit",
        "http://backend",
        object(),
    )

    assert result.success is True
    assert result.next_step == "confirm_plan"
    assert result.session.step_key == "confirm_plan"
    assert result.session.artifacts["plan_confirmed"] is False
    assert result.session.collected["objective"] == "Record a walkthrough"
    assert result.session.collected["target_url"] == "https://tripc.ai"
    assert result.session.collected["reference_url"] is None
    assert result.output["video_review_plan"]["target_url"] == "https://tripc.ai"


@pytest.mark.asyncio
async def test_video_ai_stale_artifacts_are_rebuilt_safely(monkeypatch):
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    session = _filled_session()
    session.artifacts["concept_brief"] = {"persona_id": "minh_vn"}
    session.artifacts["concept_approved"] = True
    session.artifacts["beat_sheet"] = {"beats": "bad-shape"}
    session.artifacts["beat_sheet_approved"] = True
    session.artifacts["approved_production_package"] = {"bad": "package"}

    result = await VideoAISkill.execute(session, "http://backend", object())

    assert result.success is True
    assert result.session.step_key == "confirm_concept"
    assert (
        result.session.artifacts["concept_brief"]["feature_focus"]
        == "AI itinerary planner"
    )
    assert result.session.artifacts["beat_sheet"] is None


@pytest.mark.asyncio
async def test_video_ai_package_ready_posts_to_start_video(monkeypatch):
    """
    Verify that when beat sheet is approved and package is ready,
    video_ai actually POSTs to /api/workflows/start-video with the approved_package.
    """
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    mock_http_client = _mock_workflow_start_client("video-minh_vn-test123")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")

    # Run through the full approval flow
    session = _filled_session()
    session.artifacts["telegram_chat_id"] = "123456"

    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    package_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )

    # Verify the POST was called
    mock_http_client.post.assert_called_once()
    call_args = mock_http_client.post.call_args

    # Verify URL
    assert call_args[0][0] == "http://backend/api/workflows/start-video"

    # Verify payload contains approved_package
    payload = call_args[1]["json"]
    headers = call_args[1]["headers"]
    assert payload["persona_id"] == "minh_vn"
    assert payload["approved_package"] is not None
    assert payload["approved_package"]["concept_brief"]["persona_id"] == "minh_vn"
    assert payload["approved_package"]["beat_sheet"]["beats"] is not None
    assert len(payload["approved_package"]["beat_sheet"]["beats"]) == 5
    assert payload["telegram_chat_id"] == "123456"
    assert payload["owner_key"] == "telegram:123456"
    assert headers == {"x-internal-api-token": "test-internal-token"}

    # Verify result
    assert package_result.success is True
    assert package_result.session.step_key == "package_ready"
    assert package_result.next_step == "poll_status"
    assert package_result.output["workflow_id"] == "video-minh_vn-test123"
    assert package_result.session.control.workflow_id == "video-minh_vn-test123"
    assert package_result.session.artifacts["workflow_id"] == "video-minh_vn-test123"


@pytest.mark.asyncio
async def test_video_ai_package_ready_reuses_existing_workflow_id(monkeypatch):
    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    mock_http_client = _mock_workflow_start_client("video-minh_vn-idempotent")

    session = _filled_session()
    session.artifacts["telegram_chat_id"] = "123456"

    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    package_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    repeated_result = await VideoAISkill.execute(
        package_result.session,
        "http://backend",
        mock_http_client,
    )

    mock_http_client.post.assert_called_once()
    assert repeated_result.success is True
    assert repeated_result.next_step == "poll_status"
    assert repeated_result.output["workflow_id"] == "video-minh_vn-idempotent"


@pytest.mark.asyncio
async def test_video_ai_package_ready_uses_voiceover_mode_when_heygen_avatar_missing(
    monkeypatch,
):
    _patch_persona_lookup_missing_heygen(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    mock_http_client = _mock_workflow_start_client("video-minh_vn-voiceover")

    session = _filled_session()
    session.artifacts["telegram_chat_id"] = "123456"

    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    package_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )

    payload = mock_http_client.post.call_args[1]["json"]
    assert payload["talking_head_optional"] is True
    assert package_result.output["production_mode"] == "voiceover_only"
    assert "voiceover instead" in package_result.output["production_note"]


@pytest.mark.asyncio
async def test_video_ai_package_ready_handles_api_failure(monkeypatch):
    """
    Verify that when the production API call fails, video_ai returns
    a failed result with appropriate error message.
    """
    import httpx

    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    # Create a mock http_client that raises an error
    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = httpx.HTTPError("Connection refused")

    # Run through the full approval flow
    session = _filled_session()
    session.artifacts["telegram_chat_id"] = "123456"

    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    package_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )

    # Verify the result indicates failure
    assert package_result.success is False
    assert package_result.session.step_key == "package_ready"
    assert "Connection refused" in package_result.error
    assert package_result.output["approved_production_package"] is not None
    assert package_result.session.control.workflow_id is None
    assert package_result.session.artifacts["workflow_id"] is None


@pytest.mark.asyncio
async def test_video_ai_package_ready_retry_start_retries_failed_launch(monkeypatch):
    import httpx

    _patch_persona_lookup(monkeypatch)

    async def fake_build_concept_brief(cls, collected, persona_snapshot):
        return _concept_contract()

    async def fake_build_beat_sheet(cls, concept_brief, persona_snapshot):
        return _beat_sheet_contract()

    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_concept_brief",
        classmethod(fake_build_concept_brief),
    )
    monkeypatch.setattr(
        video_ai_module.CreativeDirectorService,
        "build_beat_sheet",
        classmethod(fake_build_beat_sheet),
    )

    success_response = MagicMock()
    success_response.json.return_value = {"workflow_id": "video-minh_vn-retried"}
    success_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.post.side_effect = [
        httpx.HTTPError("Connection refused"),
        success_response,
    ]

    session = _filled_session()
    session.artifacts["telegram_chat_id"] = "123456"

    concept_result = await VideoAISkill.execute(
        session, "http://backend", mock_http_client
    )
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    failed_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        mock_http_client,
    )
    retry_result = await VideoAISkill.handle_preproduction_action(
        failed_result.session,
        "retry_start",
        "http://backend",
        mock_http_client,
    )

    assert mock_http_client.post.await_count == 2
    assert retry_result.success is True
    assert retry_result.next_step == "poll_status"
    assert retry_result.output["workflow_id"] == "video-minh_vn-retried"
