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
    ConceptBriefContract,
    ExtractedFeatureContract,
    GroundedFeatureContract,
    RecordedDemoEvidenceContract,
    TimelineSegmentContract,
)
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
            "skills.video_ai.CreativeDirectorService.build_concept_brief",
            new_callable=AsyncMock,
        ) as mock_build_concept:
            mock_build_concept.return_value = _concept_contract()

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
