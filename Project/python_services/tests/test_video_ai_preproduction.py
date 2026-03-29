from copy import deepcopy

import pytest
from fastapi import FastAPI

from services.contracts import BeatSheetContract, ConceptBriefContract
from services.skill_dispatcher import SkillDispatcher
from services.skill_session_store import TelegramSkillSessionStore
from skills import video_ai as video_ai_module
from skills.video_ai import VideoAISkill


@pytest.fixture(autouse=True)
def reset_skill_session_store():
    TelegramSkillSessionStore._redis_client = None
    TelegramSkillSessionStore._redis_enabled = False
    TelegramSkillSessionStore._redis_init_attempted = True
    TelegramSkillSessionStore._memory_sessions.clear()
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
async def test_video_ai_collects_required_fields_in_order():
    session = VideoAISkill.initial_session()

    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "pick_persona"

    session.collected["persona_id"] = "minh_vn"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_idea_brief"

    session.collected["idea_brief"] = "Need a product demo."
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_feature_focus"

    session.collected["feature_focus"] = "AI itinerary planner"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "choose_video_goal"

    session.collected["video_goal"] = "feature_demo"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_audience"

    session.collected["audience"] = "travelers aged 22-35"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_cta"

    session.collected["cta"] = "Try TripC free"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "collect_reference_url"

    session.collected["reference_url"] = "https://tripc.ai"
    result = await VideoAISkill.execute(session, "http://backend", object())
    assert result.next_step == "choose_access_level"


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

    session = _filled_session()
    concept_result = await VideoAISkill.execute(session, "http://backend", object())
    beat_result = await VideoAISkill.handle_preproduction_action(
        concept_result.session,
        "approve",
        "http://backend",
        object(),
    )
    package_result = await VideoAISkill.handle_preproduction_action(
        beat_result.session,
        "approve",
        "http://backend",
        object(),
    )

    assert beat_result.session.step_key == "confirm_beats"
    assert package_result.session.step_key == "package_ready"
    assert package_result.session.control.status.value == "done"
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

    session = _filled_session()
    concept_result = await VideoAISkill.execute(session, "http://backend", object())
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
    from unittest.mock import AsyncMock, MagicMock

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

    # Create a mock http_client that tracks calls
    mock_response = MagicMock()
    mock_response.json.return_value = {"workflow_id": "video-minh_vn-test123"}
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_response

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
    assert payload["persona_id"] == "minh_vn"
    assert payload["approved_package"] is not None
    assert payload["approved_package"]["concept_brief"]["persona_id"] == "minh_vn"
    assert payload["approved_package"]["beat_sheet"]["beats"] is not None
    assert len(payload["approved_package"]["beat_sheet"]["beats"]) == 5
    assert payload["telegram_chat_id"] == "123456"
    assert payload["owner_key"] == "telegram:123456"

    # Verify result
    assert package_result.success is True
    assert package_result.session.step_key == "package_ready"
    assert package_result.output["workflow_id"] == "video-minh_vn-test123"


@pytest.mark.asyncio
async def test_video_ai_package_ready_uses_voiceover_mode_when_heygen_avatar_missing(
    monkeypatch,
):
    from unittest.mock import AsyncMock, MagicMock

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

    mock_response = MagicMock()
    mock_response.json.return_value = {"workflow_id": "video-minh_vn-voiceover"}
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_response

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
    from unittest.mock import AsyncMock, MagicMock
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
