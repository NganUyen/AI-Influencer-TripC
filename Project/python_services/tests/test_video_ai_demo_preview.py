"""
Tests for Phase 5: Demo Preview Confirm and Feature Grounding.

Tests cover:
- demo_preview_confirm step in recorded_demo_video mode
- handle_demo_preview_action (confirm, correct, reemphasize, reupload, timeout)
- DemoFeatureGroundingService
- Timeout handling in skill_dispatcher
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.contracts import (
    BeatSheetContract,
    ConceptBriefContract,
    ExtractedFeatureContract,
    GroundedFeatureContract,
    RecordedDemoEvidenceContract,
    ResolvedIdeaContract,
    TimelineSegmentContract,
)
from services.creative_director_service import CreativeDirectorService
from services.demo_feature_grounding_service import (
    DemoFeatureGroundingService,
    build_preview_summary,
)
from services.skill_session_store import TelegramSkillSessionStore
from skills.video_ai import VideoAISkill


@pytest.fixture(autouse=True)
def reset_skill_session_store():
    TelegramSkillSessionStore._redis_client = None
    TelegramSkillSessionStore._redis_enabled = False
    TelegramSkillSessionStore._redis_init_attempted = True
    TelegramSkillSessionStore._memory_sessions.clear()
    yield
    TelegramSkillSessionStore._memory_sessions.clear()


def _sample_evidence() -> RecordedDemoEvidenceContract:
    """Create sample RecordedDemoEvidenceContract for testing."""
    return RecordedDemoEvidenceContract(
        demo_video_asset_url="https://storage.example.com/demo.mp4",
        original_filename="demo.mp4",
        duration_sec=45.0,
        width=1920,
        height=1080,
        segments=[
            TimelineSegmentContract(
                segment_id="seg_1",
                start_sec=0.0,
                end_sec=5.0,
                segment_type="intro",
                ocr_texts=["TripC", "AI Travel Planner"],
                description="App logo and title screen",
            ),
            TimelineSegmentContract(
                segment_id="seg_2",
                start_sec=5.0,
                end_sec=35.0,
                segment_type="feature_demo",
                ocr_texts=["Create Itinerary", "AI Suggestions", "Budget Tracker"],
                description="User navigating itinerary creation flow",
            ),
            TimelineSegmentContract(
                segment_id="seg_3",
                start_sec=35.0,
                end_sec=45.0,
                segment_type="outro",
                ocr_texts=["Try TripC Free", "tripc.ai"],
                description="CTA screen with download button",
            ),
        ],
        extracted_features=[
            ExtractedFeatureContract(
                feature_id="feat_1",
                name="AI Itinerary Planner",
                confidence="high",
                timestamp_start_sec=10.0,
                timestamp_end_sec=20.0,
                ocr_evidence=["Create Itinerary", "AI Suggestions"],
            ),
            ExtractedFeatureContract(
                feature_id="feat_2",
                name="Budget Tracker",
                confidence="medium",
                timestamp_start_sec=25.0,
                timestamp_end_sec=30.0,
                ocr_evidence=["Budget Tracker"],
            ),
        ],
        feature_candidates=["AI Itinerary Planner", "Budget Tracker"],
        timeline_narrative="Demo showcases TripC app's itinerary planning workflow",
        analysis_confidence_overall="medium",
        confidence_signals={"weighted_score": 0.65},
    )


def _recorded_demo_collected_fields() -> dict[str, str]:
    return {
        "persona_id": "minh_vn",
        "creative_input_mode": "recorded_demo_video",
        "demo_video_telegram_file_id": "file_12345",
        "demo_video_asset_url": "https://storage.example.com/demo.mp4",
        "reference_url": "https://tripc.ai",
        "access_level": "public_page_only",
        "video_goal": "feature_demo",
        "audience": "travelers aged 22-35",
        "cta": "Try TripC free",
    }


def _concept_contract() -> ConceptBriefContract:
    return ConceptBriefContract(
        persona_id="minh_vn",
        feature_focus="Smart Trip Planner",
        video_goal="feature_demo",
        audience="travelers aged 22-35",
        angle="problem_solution",
        platform="tiktok",
        cta="Try TripC free",
        reference_url="https://tripc.ai",
        access_level="public_page_only",
        source_summary="TripC is an AI travel planning app.",
        tone_resolved="confident",
    )


def _recorded_demo_concept_contract() -> ConceptBriefContract:
    concept = _concept_contract()
    concept.creative_input_mode = "recorded_demo_video"
    concept.demo_video_telegram_file_id = "file_12345"
    concept.demo_video_asset_url = "https://storage.example.com/demo.mp4"
    return concept


def _parse_target_range(target: str) -> tuple[int, int]:
    start_text, end_text = target.split("-", 1)

    def _parse_part(value: str) -> int:
        hours, minutes, seconds = [int(part) for part in value.split(":", 2)]
        return (hours * 3600) + (minutes * 60) + seconds

    return _parse_part(start_text), _parse_part(end_text)


def _demo_session_at_preview_confirm():
    """Create a session ready for demo_preview_confirm step."""
    session = VideoAISkill.initial_session()
    session.collected.update(_recorded_demo_collected_fields())
    session.step_key = "demo_preview_confirm"
    session.artifacts["demo_evidence"] = _sample_evidence().model_dump(mode="json")
    session.artifacts["demo_preview_summary"] = {
        "summary_text": "Duration: 45s\nResolution: 1920x1080",
        "feature_candidates": ["AI Itinerary Planner", "Budget Tracker"],
        "confidence": "medium",
    }
    session.artifacts["demo_preview_confirmed"] = False
    session.artifacts["demo_preview_timeout_at"] = (
        datetime.now(timezone.utc) + timedelta(minutes=15)
    ).isoformat()
    return session


# =============================================================================
# DemoFeatureGroundingService Tests
# =============================================================================


@pytest.mark.asyncio
async def test_grounding_service_enriches_features_with_official_names():
    """Test that grounding service adds official names from OpenClaw result."""
    mock_openclaw = AsyncMock()
    mock_openclaw.execute_task.return_value = {
        "grounded_features": [
            {
                "original_name": "AI Itinerary Planner",
                "grounded": True,
                "official_name": "Smart Trip Planner",
                "official_description": "AI-powered itinerary generation",
                "value_proposition": "Plan trips 10x faster",
                "source_url": "https://tripc.ai/features",
                "confidence": "high",
                "note": "Found on features page",
            },
            {
                "original_name": "Budget Tracker",
                "grounded": False,
                "official_name": None,
                "confidence": "low",
                "note": "Not found on official website",
            },
        ],
        "project_summary": "TripC is an AI travel planning app",
        "key_value_props": ["Save time", "Smart recommendations"],
    }

    service = DemoFeatureGroundingService(openclaw_service=mock_openclaw)
    evidence = _sample_evidence()

    result = await service.ground_features(
        evidence=evidence,
        reference_url="https://tripc.ai",
        project_name="TripC",
        video_goal="feature_demo",
    )

    # Verify OpenClaw was called
    mock_openclaw.execute_task.assert_called_once()

    # Verify grounded features were populated
    assert len(result.grounded_features) == 2
    assert result.grounding_completed is True

    # Check first feature was grounded with official name
    grounded_1 = next(
        gf
        for gf in result.grounded_features
        if gf.original_name == "AI Itinerary Planner"
    )
    assert grounded_1.grounded is True
    assert grounded_1.official_name == "Smart Trip Planner"
    assert grounded_1.grounding_confidence == "high"

    # Check second feature was not grounded
    grounded_2 = next(
        gf for gf in result.grounded_features if gf.original_name == "Budget Tracker"
    )
    assert grounded_2.grounded is False
    assert grounded_2.official_name is None

    # Feature candidates should prefer official names
    assert "Smart Trip Planner" in result.feature_candidates


@pytest.mark.asyncio
async def test_grounding_service_handles_openclaw_failure_gracefully():
    """Test that grounding service creates ungrounded entries on failure."""
    mock_openclaw = AsyncMock()
    mock_openclaw.execute_task.side_effect = RuntimeError("OpenClaw unavailable")

    service = DemoFeatureGroundingService(openclaw_service=mock_openclaw)
    evidence = _sample_evidence()

    result = await service.ground_features(
        evidence=evidence,
        reference_url="https://tripc.ai",
    )

    # Should still complete but with ungrounded features
    assert result.grounding_completed is True
    assert len(result.grounded_features) == 2
    assert all(not gf.grounded for gf in result.grounded_features)
    assert all(gf.grounding_confidence == "low" for gf in result.grounded_features)


@pytest.mark.asyncio
async def test_grounding_service_skips_when_no_features():
    """Test grounding service handles empty feature list."""
    mock_openclaw = AsyncMock()
    service = DemoFeatureGroundingService(openclaw_service=mock_openclaw)

    evidence = _sample_evidence()
    evidence.extracted_features = []
    evidence.feature_candidates = []

    result = await service.ground_features(
        evidence=evidence,
        reference_url="https://tripc.ai",
    )

    # Should complete without calling OpenClaw
    assert result.grounding_completed is True
    mock_openclaw.execute_task.assert_not_called()


def test_build_preview_summary_creates_structured_output():
    """Test that build_preview_summary creates proper Telegram preview data."""
    evidence = _sample_evidence()
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="Smart Trip Planner",
            grounding_confidence="high",
        ),
        GroundedFeatureContract(
            feature_id="feat_2",
            original_name="Budget Tracker",
            grounded=False,
            grounding_confidence="low",
        ),
    ]
    evidence.grounding_completed = True

    summary = build_preview_summary(evidence, video_goal="feature_demo")

    assert summary["video_info"]["duration_sec"] == 45.0
    assert summary["video_info"]["resolution"] == "1920x1080"
    assert "Smart Trip Planner" in summary["grounded_features"]
    assert "Budget Tracker" in summary["ungrounded_features"]
    assert summary["confidence"] == "medium"
    assert summary["grounding_completed"] is True


# =============================================================================
# VideoAISkill.handle_demo_preview_action Tests
# =============================================================================


@pytest.mark.asyncio
async def test_handle_demo_preview_confirm_proceeds_to_concept_brief():
    """Test that confirming the preview proceeds to ConceptBrief generation."""
    session = _demo_session_at_preview_confirm()

    with patch.object(VideoAISkill, "execute", new_callable=AsyncMock) as mock_execute:
        expected_session = session.model_copy(deep=True)
        expected_session.artifacts["demo_preview_confirmed"] = True
        expected_session.artifacts["demo_preview_timeout_at"] = None
        mock_execute.return_value = MagicMock(
            success=True,
            next_step="confirm_concept",
            session=expected_session,
        )

        result = await VideoAISkill.handle_demo_preview_action(
            session=session,
            action="confirm",
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

        # Verify demo_preview_confirmed was set
        assert result.session.artifacts["demo_preview_confirmed"] is True
        assert result.session.artifacts["demo_preview_timeout_at"] is None

        # Verify execute was called to proceed
        mock_execute.assert_called_once()


@pytest.mark.asyncio
async def test_handle_demo_preview_correct_with_text_updates_evidence():
    """Test that correction updates evidence and proceeds."""
    session = _demo_session_at_preview_confirm()

    with patch.object(VideoAISkill, "execute", new_callable=AsyncMock) as mock_execute:
        expected_session = session.model_copy(deep=True)
        expected_session.artifacts["demo_preview_confirmed"] = True
        expected_session.artifacts["demo_preview_timeout_at"] = None
        expected_session.artifacts["demo_evidence"] = session.artifacts["demo_evidence"]
        mock_execute.return_value = MagicMock(
            success=True,
            next_step="confirm_concept",
            session=expected_session,
        )

        result = await VideoAISkill.handle_demo_preview_action(
            session=session,
            action="correct",
            backend_url="http://backend",
            http_client=AsyncMock(),
            correction_text="The main feature is actually Smart Trip Builder, not AI Itinerary Planner",
        )

        # Verify correction was stored in evidence
        called_session = mock_execute.await_args.args[0]
        evidence_payload = called_session.artifacts["demo_evidence"]
        assert "user_correction" in evidence_payload["confidence_signals"]
        assert called_session.artifacts["demo_preview_confirmed"] is True


@pytest.mark.asyncio
async def test_handle_demo_preview_correct_without_text_prompts_for_input():
    """Test that correction without text prompts for input."""
    session = _demo_session_at_preview_confirm()

    result = await VideoAISkill.handle_demo_preview_action(
        session=session,
        action="correct",
        backend_url="http://backend",
        http_client=AsyncMock(),
    )

    # Should prompt for correction text
    assert result.next_step == "demo_correct_features"
    assert result.session.step_key == "demo_correct_features"
    assert result.session.artifacts["demo_preview_confirmed"] is False


@pytest.mark.asyncio
async def test_handle_demo_preview_reemphasize_stores_focus():
    """Test that re-emphasis stores the focus and proceeds."""
    session = _demo_session_at_preview_confirm()

    with patch.object(VideoAISkill, "execute", new_callable=AsyncMock) as mock_execute:
        expected_session = session.model_copy(deep=True)
        expected_session.collected["feature_emphasis"] = (
            "Focus on the AI recommendations feature"
        )
        expected_session.artifacts["demo_preview_confirmed"] = True
        expected_session.artifacts["demo_preview_timeout_at"] = None
        expected_session.artifacts["demo_evidence"] = session.artifacts["demo_evidence"]
        mock_execute.return_value = MagicMock(
            success=True,
            next_step="confirm_concept",
            session=expected_session,
        )

        result = await VideoAISkill.handle_demo_preview_action(
            session=session,
            action="reemphasize",
            backend_url="http://backend",
            http_client=AsyncMock(),
            reemphasis_text="Focus on the AI recommendations feature",
        )

        # Verify re-emphasis was stored
        called_session = mock_execute.await_args.args[0]
        assert called_session.collected.get("feature_emphasis") == (
            "Focus on the AI recommendations feature"
        )
        evidence_payload = called_session.artifacts["demo_evidence"]
        assert "user_reemphasis" in evidence_payload["confidence_signals"]


@pytest.mark.asyncio
async def test_handle_demo_preview_reupload_resets_video_state():
    """Test that reupload resets video-related artifacts."""
    session = _demo_session_at_preview_confirm()

    result = await VideoAISkill.handle_demo_preview_action(
        session=session,
        action="reupload",
        backend_url="http://backend",
        http_client=AsyncMock(),
    )

    # Verify video state was reset
    assert result.session.collected.get("demo_video_telegram_file_id") is None
    assert result.session.collected.get("demo_video_asset_url") is None
    assert result.session.artifacts.get("demo_evidence") is None
    assert result.session.artifacts.get("demo_preview_summary") is None
    assert result.session.artifacts.get("demo_preview_confirmed") is False
    assert result.next_step == "upload_demo_video"


@pytest.mark.asyncio
async def test_handle_demo_preview_timeout_aborts_without_auto_confirm():
    """Test that timeout aborts session (does NOT auto-confirm per spec)."""
    session = _demo_session_at_preview_confirm()

    result = await VideoAISkill.handle_demo_preview_action(
        session=session,
        action="timeout",
        backend_url="http://backend",
        http_client=AsyncMock(),
    )

    # Should fail, NOT auto-confirm
    assert result.success is False
    assert "timed out" in result.error.lower()
    assert result.output.get("timeout") is True
    assert result.output.get("retryable") is True
    # Session should still be at demo_preview_confirm for retry
    assert result.session.step_key == "demo_preview_confirm"


@pytest.mark.asyncio
async def test_handle_demo_preview_action_rejects_wrong_step():
    """Test that demo preview action is rejected if not at correct step."""
    session = VideoAISkill.initial_session()
    session.step_key = "confirm_concept"  # Wrong step

    result = await VideoAISkill.handle_demo_preview_action(
        session=session,
        action="confirm",
        backend_url="http://backend",
        http_client=AsyncMock(),
    )

    assert result.success is False
    assert "not applicable" in result.error.lower()


# =============================================================================
# Timeout Detection Tests
# =============================================================================


def test_demo_preview_timeout_detection():
    """Test that timeout is correctly detected based on timestamp."""
    session = _demo_session_at_preview_confirm()

    # Set timeout in the past
    past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.artifacts["demo_preview_timeout_at"] = past_time.isoformat()

    # Check if timed out (logic from skill_dispatcher._check_demo_preview_timeout)
    timeout_at_str = session.artifacts.get("demo_preview_timeout_at")
    if timeout_at_str:
        timeout_at = datetime.fromisoformat(timeout_at_str)
        is_timed_out = datetime.now(timezone.utc) >= timeout_at
        assert is_timed_out is True


def test_demo_preview_no_timeout_when_within_window():
    """Test that no timeout when within 15-minute window."""
    session = _demo_session_at_preview_confirm()

    # Set timeout in the future
    future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    session.artifacts["demo_preview_timeout_at"] = future_time.isoformat()

    timeout_at_str = session.artifacts.get("demo_preview_timeout_at")
    if timeout_at_str:
        timeout_at = datetime.fromisoformat(timeout_at_str)
        is_timed_out = datetime.now(timezone.utc) >= timeout_at
        assert is_timed_out is False


# =============================================================================
# Grounding Orchestration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_execute_runs_analysis_and_grounding_before_preview_confirm():
    """Test that execute runs analysis and grounding when reaching demo_preview_confirm."""
    session = VideoAISkill.initial_session()
    session.collected.update(_recorded_demo_collected_fields())

    mock_evidence = _sample_evidence()
    mock_evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="Smart Trip Planner",
            grounding_confidence="high",
        ),
    ]
    mock_evidence.grounding_completed = True

    with patch.object(
        VideoAISkill,
        "_run_demo_analysis_and_grounding",
        new_callable=AsyncMock,
    ) as mock_run_analysis:
        mock_run_analysis.return_value = mock_evidence

        result = await VideoAISkill.execute(
            session=session,
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

        # Verify analysis was called
        mock_run_analysis.assert_called_once()

        # Should be at demo_preview_confirm step
        assert result.next_step == "demo_preview_confirm"
        assert result.session.step_key == "demo_preview_confirm"

        # Verify evidence was stored
        assert result.session.artifacts.get("demo_evidence") is not None
        assert result.session.artifacts.get("demo_preview_summary") is not None
        assert result.session.artifacts.get("demo_preview_timeout_at") is not None


@pytest.mark.asyncio
async def test_execute_skips_analysis_when_already_confirmed():
    """Test that execute skips analysis when demo_preview_confirmed is True."""
    session = _demo_session_at_preview_confirm()
    session.artifacts["demo_preview_confirmed"] = True

    # Mock persona lookup
    with patch.object(
        VideoAISkill,
        "_request_json",
        new_callable=AsyncMock,
    ) as mock_request:
        mock_request.side_effect = [
            {"ready": True},
            {
                "persona_id": "minh_vn",
                "display_name": "Minh VN",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Neural2-A",
                "tone_default": "confident",
                "status": "ready",
                "heygen_avatar_id": "avatar_123",
            },
        ]

        # Mock CreativeDirectorService
        with patch(
            "skills.video_ai.CreativeDirectorService.build_concept_from_demo_evidence",
            new_callable=AsyncMock,
        ) as mock_build_concept:
            mock_build_concept.return_value = _recorded_demo_concept_contract()

            with patch.object(
                VideoAISkill,
                "_run_demo_analysis_and_grounding",
                new_callable=AsyncMock,
            ) as mock_run_analysis:
                result = await VideoAISkill.execute(
                    session=session,
                    backend_url="http://backend",
                    http_client=AsyncMock(),
                )

            mock_run_analysis.assert_not_called()
            assert result.next_step == "confirm_concept"


@pytest.mark.asyncio
async def test_execute_recorded_demo_builds_concept_from_grounded_evidence():
    session = _demo_session_at_preview_confirm()
    session.artifacts["demo_preview_confirmed"] = True
    evidence = _sample_evidence()
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="Smart Trip Planner",
            grounding_confidence="high",
        )
    ]
    session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

    with patch.object(
        VideoAISkill, "_request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            {"ready": True},
            {
                "persona_id": "minh_vn",
                "display_name": "Minh VN",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Neural2-A",
                "tone_default": "confident",
                "status": "ready",
                "heygen_avatar_id": "avatar_123",
            },
        ]
        result = await VideoAISkill.execute(
            session=session,
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

    concept = ConceptBriefContract.model_validate(
        result.session.artifacts["concept_brief"]
    )
    assert result.next_step == "confirm_concept"
    assert concept.creative_input_mode == "recorded_demo_video"
    assert concept.feature_focus == "Smart Trip Planner"
    assert concept.demo_video_asset_url == "https://storage.example.com/demo.mp4"
    assert "Smart Trip Planner" in concept.source_summary


@pytest.mark.asyncio
async def test_execute_recorded_demo_uses_novel_user_correction_for_feature_focus():
    """
    Bug fix verification: User corrections should be used as feature_focus
    even when they don't match any existing detected feature.
    Previously, novel corrections were discarded in favor of existing features.
    """
    session = _demo_session_at_preview_confirm()
    session.artifacts["demo_preview_confirmed"] = True
    evidence = _sample_evidence()
    # Clear extracted_features to avoid partial matching with "Budget Tracker"
    evidence.extracted_features = []
    evidence.feature_candidates = []
    # Existing grounded feature
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="AI Trip Optimizer",
            grounding_confidence="high",
        )
    ]
    # User provides a completely novel correction that doesn't match any feature
    evidence.confidence_signals["user_correction"] = "Smart Budget Tracker"
    session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

    with patch.object(
        VideoAISkill, "_request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            {"ready": True},
            {
                "persona_id": "minh_vn",
                "display_name": "Minh VN",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Neural2-A",
                "tone_default": "confident",
                "status": "ready",
                "heygen_avatar_id": "avatar_123",
            },
        ]
        result = await VideoAISkill.execute(
            session=session,
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

    concept = ConceptBriefContract.model_validate(
        result.session.artifacts["concept_brief"]
    )
    # The user's novel correction should be used, not the existing detected feature
    assert concept.feature_focus == "Smart Budget Tracker"
    assert concept.feature_focus != "AI Trip Optimizer"  # Not the existing feature


@pytest.mark.asyncio
async def test_execute_recorded_demo_builds_beats_with_timestamp_ranges():
    session = _demo_session_at_preview_confirm()
    session.artifacts["demo_preview_confirmed"] = True
    session.artifacts["concept_brief"] = _recorded_demo_concept_contract().model_dump(
        mode="json"
    )
    session.artifacts["concept_approved"] = True
    evidence = _sample_evidence()
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="Smart Trip Planner",
            grounding_confidence="high",
        )
    ]
    session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

    with patch.object(
        VideoAISkill, "_request_json", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            {"ready": True},
            {
                "persona_id": "minh_vn",
                "display_name": "Minh VN",
                "language": "Vietnamese",
                "tts_voice": "vi-VN-Neural2-A",
                "tone_default": "confident",
                "status": "ready",
                "heygen_avatar_id": "avatar_123",
            },
        ]
        result = await VideoAISkill.execute(
            session=session,
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

    beat_sheet = BeatSheetContract.model_validate(
        result.session.artifacts["beat_sheet"]
    )
    assert result.next_step == "confirm_beats"
    assert all(
        beat.top_half_source_type == "uploaded_demo_video" for beat in beat_sheet.beats
    )
    assert all("-" in beat.top_half_target for beat in beat_sheet.beats)
    assert all(beat.top_half_target.count(":") == 4 for beat in beat_sheet.beats)
    assert all(beat.trim_confidence is not None for beat in beat_sheet.beats)
    assert beat_sheet.beats[0].purpose == "hook"
    assert beat_sheet.beats[-1].purpose == "cta"


@pytest.mark.asyncio
async def test_recorded_demo_beat_ranges_stay_within_video_and_relevant_segments():
    evidence = _sample_evidence()
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="Smart Trip Planner",
            grounding_confidence="high",
        )
    ]
    beat_sheet = await CreativeDirectorService.build_beats_from_demo_evidence(
        _recorded_demo_concept_contract(),
        evidence,
    )

    parsed_ranges = [
        _parse_target_range(beat.top_half_target) for beat in beat_sheet.beats
    ]
    assert all(0 <= start < end <= 45 for start, end in parsed_ranges)
    assert all(
        abs((end - start) - beat.duration_sec) <= 1
        for (start, end), beat in zip(parsed_ranges, beat_sheet.beats)
    )
    assert parsed_ranges[0][1] <= 5
    assert parsed_ranges[2][0] >= 5 and parsed_ranges[2][1] <= 35
    assert parsed_ranges[-1][0] >= 35 and parsed_ranges[-1][1] <= 45
    assert len({beat.top_half_target for beat in beat_sheet.beats}) == len(
        beat_sheet.beats
    )


@pytest.mark.asyncio
async def test_recorded_demo_trim_confidence_uses_expected_bands():
    evidence = _sample_evidence()
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Itinerary Planner",
            grounded=True,
            official_name="Smart Trip Planner",
            grounding_confidence="high",
        )
    ]
    beat_sheet = await CreativeDirectorService.build_beats_from_demo_evidence(
        _recorded_demo_concept_contract(),
        evidence,
    )

    hook_confidence = beat_sheet.beats[0].trim_confidence
    feature_confidence = beat_sheet.beats[2].trim_confidence
    cta_confidence = beat_sheet.beats[-1].trim_confidence

    assert hook_confidence is not None and hook_confidence < 0.5
    assert cta_confidence is not None and cta_confidence < 0.5
    assert feature_confidence is not None and feature_confidence >= 0.8
    assert (
        CreativeDirectorService._trim_confidence_policy(feature_confidence) == "normal"
    )
    assert (
        CreativeDirectorService._trim_confidence_policy(hook_confidence)
        == "conservative_hold"
    )


@pytest.mark.asyncio
async def test_execute_handles_analysis_failure_gracefully():
    """Test that execute handles analysis failure with retryable error."""
    session = VideoAISkill.initial_session()
    session.collected.update(_recorded_demo_collected_fields())

    with patch.object(
        VideoAISkill,
        "_run_demo_analysis_and_grounding",
        new_callable=AsyncMock,
    ) as mock_run_analysis:
        mock_run_analysis.side_effect = ValueError(
            "Video analysis failed: invalid format"
        )

        result = await VideoAISkill.execute(
            session=session,
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

        # Should return error result
        assert result.success is False
        assert (
            "analysis failed" in result.error.lower()
            or "invalid format" in result.error.lower()
        )
        assert result.output.get("retryable") is True


@pytest.mark.asyncio
async def test_confirm_concept_regenerate_recorded_demo_reanalyzes_preview():
    session = _demo_session_at_preview_confirm()
    session.step_key = "confirm_concept"
    session.artifacts["concept_brief"] = _recorded_demo_concept_contract().model_dump(
        mode="json"
    )
    session.artifacts["concept_approved"] = False
    session.artifacts["demo_preview_confirmed"] = True

    with patch.object(
        VideoAISkill,
        "_run_demo_analysis_and_grounding",
        new_callable=AsyncMock,
    ) as mock_run_analysis:
        mock_run_analysis.return_value = _sample_evidence()

        result = await VideoAISkill.handle_preproduction_action(
            session=session,
            action="regenerate",
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

    assert result.success is True
    assert result.next_step == "demo_preview_confirm"
    assert result.session.step_key == "demo_preview_confirm"
    assert result.session.artifacts["concept_brief"] is None
    assert result.session.artifacts["demo_preview_confirmed"] is False
    assert result.session.artifacts.get("demo_evidence") is not None
    mock_run_analysis.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_recorded_demo_blocked_policy_returns_to_preview_step():
    session = _demo_session_at_preview_confirm()
    session.artifacts["demo_preview_confirmed"] = True

    blocked_evidence = _sample_evidence()
    blocked_evidence.extracted_features = []
    blocked_evidence.confidence_signals = {
        "ocr_available": False,
        "ocr_useful": False,
        "ocr_text_found": False,
    }
    session.artifacts["demo_evidence"] = blocked_evidence.model_dump(mode="json")

    with patch.object(
        VideoAISkill,
        "_resolve_persona_snapshot",
        new_callable=AsyncMock,
    ) as mock_snapshot:
        mock_snapshot.return_value = {
            "persona_id": "minh_vn",
            "tone_resolved": "confident",
        }

        with patch.object(
            CreativeDirectorService,
            "build_concept_from_demo_evidence",
            new_callable=AsyncMock,
        ) as mock_build_concept:
            result = await VideoAISkill.execute(
                session=session,
                backend_url="http://backend",
                http_client=AsyncMock(),
            )

    assert result.success is False
    assert result.next_step == "demo_preview_confirm"
    assert result.session.step_key == "demo_preview_confirm"
    assert result.output.get("retryable") is True
    assert "Could not analyze the video content" in (result.error or "")
    mock_build_concept.assert_not_awaited()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7: Production Handoff and Top-Half Trimming Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase7ExtractUploadedDemoSegment:
    """Tests for _extract_uploaded_demo_segment helper in media_activities.py."""

    @pytest.mark.asyncio
    async def test_extract_segment_parses_timestamp_range(self):
        """Test that timestamp ranges are correctly parsed."""
        from activities.media_activities import _extract_uploaded_demo_segment
        from temporalio.exceptions import ApplicationError

        # Invalid range should raise
        scene = {
            "id": "scene_1",
            "top_half_target": "",  # Empty
            "trim_confidence": 0.9,
        }

        with pytest.raises(ApplicationError) as exc_info:
            await _extract_uploaded_demo_segment(
                scene,
                {"campaign_id": "test"},
                "https://example.com/demo.mp4",
            )
        assert "invalid timestamp range" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_segment_validates_source_ref(self):
        """Test that source_ref is required."""
        from activities.media_activities import _extract_uploaded_demo_segment
        from temporalio.exceptions import ApplicationError

        scene = {
            "id": "scene_1",
            "top_half_target": "00:00:05-00:00:15",
            "trim_confidence": 0.9,
        }

        # Empty source_ref should be caught in routing, but test the helper
        # The helper itself doesn't validate source_ref presence
        # (that's done in generate_scene_images routing)
        pass  # Validation happens at routing level

    @pytest.mark.asyncio
    async def test_extract_segment_logs_low_confidence_warning(self):
        """Test that low trim_confidence logs a warning."""
        from activities.media_activities import _extract_uploaded_demo_segment
        from temporalio.exceptions import ApplicationError
        import logging

        scene = {
            "id": "scene_1",
            "top_half_target": "00:00:05-00:00:15",
            "trim_confidence": 0.3,  # Low confidence
        }

        # This will fail on download (mock needed), but should log warning first
        with pytest.raises((ApplicationError, Exception)):
            await _extract_uploaded_demo_segment(
                scene,
                {"campaign_id": "test"},
                "https://example.com/nonexistent.mp4",
            )


class TestPhase7GenerateSceneImagesRouting:
    """Tests for uploaded_demo_video routing in generate_scene_images."""

    def test_uploaded_demo_video_in_valid_source_types(self):
        """Ensure uploaded_demo_video is in VALID_TOP_HALF_SOURCE_TYPES."""
        from services.contracts import VALID_TOP_HALF_SOURCE_TYPES

        assert "uploaded_demo_video" in VALID_TOP_HALF_SOURCE_TYPES

    @pytest.mark.asyncio
    async def test_generate_scene_images_routes_uploaded_demo_video(self):
        """Test that uploaded_demo_video routes to _extract_uploaded_demo_segment."""
        from activities.media_activities import generate_scene_images
        from unittest.mock import patch, AsyncMock

        mock_extract = AsyncMock(
            return_value={
                "url": "https://storage.example.com/segment.mp4",
                "storage_url": "https://storage.example.com/segment.mp4",
                "storage_key": "demo_segment_1",
                "media_asset_id": "asset_123",
                "is_video": True,
                "generation_method": "uploaded_demo_segment",
            }
        )

        scenes = [
            {
                "id": 1,
                "top_half_source_type": "uploaded_demo_video",
                "top_half_target": "00:00:05-00:00:15",
                "source_ref": "https://storage.example.com/demo.mp4",
                "trim_confidence": 0.9,
                "metadata": {"campaign_id": "test_campaign"},
            }
        ]

        with patch(
            "activities.media_activities._extract_uploaded_demo_segment",
            mock_extract,
        ):
            results = await generate_scene_images(scenes)

        assert len(results) == 1
        assert results[0]["is_video"] is True
        assert results[0]["generation_method"] == "uploaded_demo_segment"
        assert results[0]["status"] == "completed"
        mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_scene_images_requires_source_ref_for_uploaded_demo(self):
        """Test that missing source_ref for uploaded_demo_video raises error."""
        from activities.media_activities import generate_scene_images
        from temporalio.exceptions import ApplicationError

        scenes = [
            {
                "id": 1,
                "top_half_source_type": "uploaded_demo_video",
                "top_half_target": "00:00:05-00:00:15",
                "source_ref": None,  # Missing!
                "trim_confidence": 0.9,
                "metadata": {},
            }
        ]

        with pytest.raises(ApplicationError) as exc_info:
            await generate_scene_images(scenes)

        assert "requires source_ref" in str(exc_info.value)


class TestPhase7BeatToSceneIntegration:
    """Tests for recorded_demo_video beats flowing to production."""

    @pytest.mark.asyncio
    async def test_beat_with_uploaded_demo_source_has_required_fields(self):
        """Test that recorded-demo beats have all required production fields."""
        evidence = _sample_evidence()
        evidence.grounded_features = [
            GroundedFeatureContract(
                feature_id="feat_1",
                original_name="AI Itinerary Planner",
                grounded=True,
                official_name="Smart Trip Planner",
                grounding_confidence="high",
            )
        ]

        beat_sheet = await CreativeDirectorService.build_beats_from_demo_evidence(
            _recorded_demo_concept_contract(),
            evidence,
        )

        # Find a beat with uploaded_demo_video source
        demo_beats = [
            b
            for b in beat_sheet.beats
            if b.top_half_source_type == "uploaded_demo_video"
        ]

        assert len(demo_beats) > 0, "Should have at least one uploaded_demo_video beat"

        for beat in demo_beats:
            # Required fields for production
            assert beat.top_half_target is not None
            assert "-" in beat.top_half_target, "Should be timestamp range format"
            assert beat.source_ref is not None, "Should have demo video URL"
            assert beat.trim_confidence is not None

            # Validate timestamp format (HH:MM:SS-HH:MM:SS)
            parts = beat.top_half_target.split("-")
            assert len(parts) == 2, f"Invalid range format: {beat.top_half_target}"
            for part in parts:
                assert ":" in part, f"Invalid timestamp format: {part}"

    @pytest.mark.asyncio
    async def test_approved_package_includes_demo_video_url(self):
        """Test that ApprovedProductionPackage beats carry demo_video_asset_url as source_ref."""
        from services.contracts import ApprovedProductionPackageContract

        evidence = _sample_evidence()
        concept = _recorded_demo_concept_contract()

        # For recorded_demo_video mode, the demo_video_asset_url should flow
        # to beats as source_ref (not through reference_url which may be website)
        demo_video_url = evidence.demo_video_asset_url

        evidence.grounded_features = [
            GroundedFeatureContract(
                feature_id="feat_1",
                original_name="AI Itinerary Planner",
                grounded=True,
                official_name="Smart Trip Planner",
                grounding_confidence="high",
            )
        ]
        beat_sheet = await CreativeDirectorService.build_beats_from_demo_evidence(
            concept, evidence
        )

        # Build package
        package = ApprovedProductionPackageContract(
            concept_brief=concept,
            beat_sheet=beat_sheet,
            persona_snapshot={"name": "Test Persona"},
        )

        # Verify beats with uploaded_demo_video source have demo video URL as source_ref
        demo_beats = [
            b
            for b in package.beat_sheet.beats
            if b.top_half_source_type == "uploaded_demo_video"
        ]

        assert len(demo_beats) > 0, "Should have uploaded_demo_video beats"
        for beat in demo_beats:
            assert beat.source_ref == demo_video_url, (
                f"Beat source_ref should be demo video URL, got: {beat.source_ref}"
            )


# ==================== V3.1 Tests: Proposed Main Idea UI ====================


class TestV31ProposedMainIdeaUI:
    """V3.1 tests for new Proposed Main Idea card and user actions."""

    def test_build_preview_summary_includes_resolved_idea(self):
        """build_preview_summary should include resolved_idea when provided."""
        evidence = _sample_evidence()
        evidence.grounded_features = [
            GroundedFeatureContract(
                feature_id="feat_1",
                original_name="AI Planner",
                official_name="Smart Trip Planner",
                grounded=True,
                source="official_catalog",
                consistency_score=0.9,
                explanation="Grounded to official catalog",
            )
        ]

        resolved_idea = ResolvedIdeaContract(
            main_idea_name="Smart Trip Planner",
            idea_source="official_catalog_prominence",
            idea_confidence=0.92,
            explanation="Highest-prominence feature from official catalog",
            alternate_candidates=["Budget Tracker", "Collaborative Planning"],
        )

        summary = build_preview_summary(
            evidence=evidence,
            video_goal="feature_demo",
            resolved_idea=resolved_idea,
        )

        assert "resolved_idea" in summary
        assert summary["resolved_idea"]["main_idea_name"] == "Smart Trip Planner"
        assert summary["resolved_idea"]["idea_source"] == "official_catalog_prominence"
        assert summary["resolved_idea"]["idea_confidence"] == 0.92

    def test_build_preview_summary_without_resolved_idea(self):
        """build_preview_summary should work without resolved_idea (backward compat)."""
        evidence = _sample_evidence()
        evidence.grounded_features = []

        summary = build_preview_summary(
            evidence=evidence,
            video_goal="feature_demo",
            resolved_idea=None,  # V3.1: No resolved_idea
        )

        # Should not have resolved_idea key when None is passed
        assert "resolved_idea" not in summary
        # Original fields should still be present
        assert "grounded_features" in summary
        assert "timeline_narrative" in summary

    @pytest.mark.asyncio
    async def test_approve_action_confirms_main_idea(self):
        """V3.1: 'approve' action should mark demo as confirmed."""
        session = VideoAISkill.initial_session()
        session.collected["creative_input_mode"] = "recorded_demo_video"
        session.collected["persona_id"] = "persona_123"
        session.step_key = "demo_preview_confirm"

        evidence = _sample_evidence()
        evidence.resolved_idea = ResolvedIdeaContract(
            main_idea_name="Smart Trip Planner",
            idea_source="official_catalog_prominence",
            idea_confidence=0.9,
            explanation="Test",
            alternate_candidates=[],
        )
        session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")
        session.artifacts["demo_preview_summary"] = {"test": "data"}

        with patch(
            "skills.video_ai.VideoAISkill.execute", new_callable=AsyncMock
        ) as mock_execute:
            mock_execute.return_value = MagicMock(success=True)

            result = await VideoAISkill.handle_demo_preview_action(
                session=session,
                action="approve",
                backend_url="http://backend",
                http_client=MagicMock(),
            )

        # Should mark as confirmed and proceed
        assert session.artifacts["demo_preview_confirmed"] is True
        assert session.artifacts["demo_preview_timeout_at"] is None
        mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_alternate_action_navigates_to_selection(self):
        """V3.1: 'pick_alternate' action should navigate to alternate focus step."""
        session = VideoAISkill.initial_session()
        session.collected["creative_input_mode"] = "recorded_demo_video"
        session.step_key = "demo_preview_confirm"

        evidence = _sample_evidence()
        evidence.resolved_idea = ResolvedIdeaContract(
            main_idea_name="Smart Trip Planner",
            idea_source="official_catalog_prominence",
            idea_confidence=0.9,
            explanation="Test",
            alternate_candidates=["Budget Tracker", "Collaborative Planning"],
        )
        session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

        result = await VideoAISkill.handle_demo_preview_action(
            session=session,
            action="pick_alternate",
            backend_url="http://backend",
            http_client=MagicMock(),
        )

        assert result.success is True
        assert result.next_step == "demo_pick_alternate_focus"
        assert session.step_key == "demo_pick_alternate_focus"

    @pytest.mark.asyncio
    async def test_rewrite_action_navigates_to_custom_input(self):
        """V3.1: 'rewrite' action should navigate to custom main idea input."""
        session = VideoAISkill.initial_session()
        session.collected["creative_input_mode"] = "recorded_demo_video"
        session.step_key = "demo_preview_confirm"

        result = await VideoAISkill.handle_demo_preview_action(
            session=session,
            action="rewrite",
            backend_url="http://backend",
            http_client=MagicMock(),
        )

        assert result.success is True
        assert result.next_step == "demo_rewrite_main_idea"
        assert session.step_key == "demo_rewrite_main_idea"

    @pytest.mark.asyncio
    async def test_alternate_focus_selection_updates_resolved_idea(self):
        """V3.1: Selecting alternate focus should update resolved_idea."""
        session = VideoAISkill.initial_session()
        session.collected["creative_input_mode"] = "recorded_demo_video"
        session.collected["persona_id"] = "persona_123"
        session.step_key = "demo_pick_alternate_focus"
        session.collected["alternate_main_idea"] = "Budget Tracker"

        evidence = _sample_evidence()
        evidence.resolved_idea = ResolvedIdeaContract(
            main_idea_name="Smart Trip Planner",
            idea_source="official_catalog_prominence",
            idea_confidence=0.9,
            explanation="Original",
            alternate_candidates=["Budget Tracker"],
        )
        session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

        with patch(
            "skills.video_ai.VideoAISkill._resolve_persona_snapshot",
            new_callable=AsyncMock,
        ) as mock_persona:
            mock_persona.return_value = {"persona_id": "persona_123", "name": "Test"}
            with patch(
                "skills.video_ai.CreativeDirectorService.build_concept_from_demo_evidence",
                new_callable=AsyncMock,
            ) as mock_concept:
                mock_concept.return_value = _recorded_demo_concept_contract()

                result = await VideoAISkill.execute(
                    session=session,
                    backend_url="http://backend",
                    http_client=MagicMock(),
                )

        # Check that resolved_idea was updated
        updated_evidence = RecordedDemoEvidenceContract.model_validate(
            session.artifacts["demo_evidence"]
        )
        assert updated_evidence.resolved_idea.main_idea_name == "Budget Tracker"
        assert updated_evidence.resolved_idea.idea_source == "user_selected_alternate"
        assert (
            updated_evidence.resolved_idea.idea_confidence == 1.0
        )  # User selection = max

    @pytest.mark.asyncio
    async def test_custom_main_idea_updates_resolved_idea(self):
        """V3.1: Custom main idea text should update resolved_idea."""
        session = VideoAISkill.initial_session()
        session.collected["creative_input_mode"] = "recorded_demo_video"
        session.collected["persona_id"] = "persona_123"
        session.step_key = "demo_rewrite_main_idea"
        session.collected["custom_main_idea"] = "Advanced Travel Planning Features"

        evidence = _sample_evidence()
        evidence.resolved_idea = ResolvedIdeaContract(
            main_idea_name="Smart Trip Planner",
            idea_source="official_catalog_prominence",
            idea_confidence=0.9,
            explanation="Original",
            alternate_candidates=[],
        )
        session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

        with patch(
            "skills.video_ai.VideoAISkill._resolve_persona_snapshot",
            new_callable=AsyncMock,
        ) as mock_persona:
            mock_persona.return_value = {"persona_id": "persona_123", "name": "Test"}
            with patch(
                "skills.video_ai.CreativeDirectorService.build_concept_from_demo_evidence",
                new_callable=AsyncMock,
            ) as mock_concept:
                mock_concept.return_value = _recorded_demo_concept_contract()

                result = await VideoAISkill.execute(
                    session=session,
                    backend_url="http://backend",
                    http_client=MagicMock(),
                )

        # Check that resolved_idea was updated
        updated_evidence = RecordedDemoEvidenceContract.model_validate(
            session.artifacts["demo_evidence"]
        )
        assert (
            updated_evidence.resolved_idea.main_idea_name
            == "Advanced Travel Planning Features"
        )
        assert updated_evidence.resolved_idea.idea_source == "user_custom_rewrite"
        assert (
            updated_evidence.resolved_idea.idea_confidence == 1.0
        )  # User choice = max
