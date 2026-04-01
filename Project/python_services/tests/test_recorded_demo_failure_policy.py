from unittest.mock import AsyncMock, patch

import pytest

from services.contracts import (
    ExtractedFeatureContract,
    GroundedFeatureContract,
    RecordedDemoEvidenceContract,
    TimelineSegmentContract,
)
from services.recorded_demo_failure_policy import (
    build_preview_warnings,
    evaluate_analysis_usability,
    evaluate_grounding_quality,
    evaluate_trim_confidence,
    sanitize_production_error,
    should_block_before_concept,
)
from services.telegram_renderer import TelegramRenderer
from skills.video_ai import VideoAISkill


def _base_evidence() -> RecordedDemoEvidenceContract:
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
                end_sec=10.0,
                segment_type="feature_demo",
                ocr_texts=["TripC", "Planner"],
                description="Main demo flow",
            )
        ],
        extracted_features=[
            ExtractedFeatureContract(
                feature_id="feat_1",
                name="AI Planner",
                confidence="medium",
                timestamp_start_sec=5.0,
                timestamp_end_sec=12.0,
                ocr_evidence=["Planner"],
            )
        ],
        feature_candidates=["AI Planner"],
        timeline_narrative="Shows planning flow",
        analysis_confidence_overall="medium",
        confidence_signals={
            "ocr_available": True,
            "ocr_useful": True,
            "ocr_text_found": True,
            "feature_count": 1,
        },
    )


def _collected_fields() -> dict[str, str]:
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


def test_low_confidence_with_features_warns_but_does_not_block():
    evidence = _base_evidence()
    evidence.analysis_confidence_overall = "low"

    result = evaluate_analysis_usability(evidence)

    assert result.severity == "warn"
    assert result.can_proceed is True
    assert any("confidence is low" in warning.lower() for warning in result.warnings)


def test_low_confidence_with_no_features_and_no_ocr_blocks():
    evidence = _base_evidence()
    evidence.analysis_confidence_overall = "low"
    evidence.extracted_features = []
    evidence.feature_candidates = []
    evidence.confidence_signals.update(
        {
            "ocr_available": False,
            "ocr_useful": False,
            "ocr_text_found": False,
        }
    )

    result = evaluate_analysis_usability(evidence)

    assert result.severity == "block"
    assert result.can_proceed is False
    # Updated: new message focuses on text recognition unavailable
    assert "text recognition" in (result.user_message or "").lower()
    assert "no features" in (result.user_message or "").lower()


def test_ocr_unavailable_and_ocr_weak_are_distinguished():
    unavailable = _base_evidence()
    unavailable.confidence_signals.update(
        {"ocr_available": False, "ocr_useful": False, "ocr_text_found": False}
    )

    weak = _base_evidence()
    weak.confidence_signals.update(
        {"ocr_available": True, "ocr_useful": False, "ocr_text_found": False}
    )

    unavailable_result = evaluate_analysis_usability(unavailable)
    weak_result = evaluate_analysis_usability(weak)

    assert any(
        "text recognition was unavailable" in warning.lower()
        for warning in unavailable_result.warnings
    )
    assert any(
        "no readable text" in warning.lower() for warning in weak_result.warnings
    )


def test_zero_grounding_warns_when_analysis_is_still_usable():
    evidence = _base_evidence()
    evidence.analysis_confidence_overall = "medium"
    evidence.grounding_completed = True
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Planner",
            grounded=False,
            official_name=None,
            grounding_confidence="low",
        )
    ]

    result = evaluate_grounding_quality(evidence)

    assert result.severity == "warn"
    assert result.can_proceed is True
    assert any("could be verified" in warning.lower() for warning in result.warnings)


def test_zero_grounding_blocks_only_on_combined_low_confidence():
    evidence = _base_evidence()
    evidence.analysis_confidence_overall = "low"
    evidence.grounding_completed = True
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Planner",
            grounded=False,
            official_name=None,
            grounding_confidence="low",
        )
    ]

    result = evaluate_grounding_quality(evidence)

    assert result.severity == "block"
    assert result.can_proceed is False
    assert "could not verify any features" in (result.user_message or "").lower()


def test_trim_confidence_uses_expected_bands_without_remap():
    normal = evaluate_trim_confidence(0.9, "00:00:05", "00:00:10")
    caution = evaluate_trim_confidence(0.65, "00:00:05", "00:00:10")
    conservative = evaluate_trim_confidence(0.3, "00:00:05", "00:00:10")

    assert normal.action == "normal"
    assert normal.can_proceed is True
    assert caution.action == "caution"
    assert caution.can_proceed is True
    assert "approximate" in (caution.warning or "").lower()
    assert conservative.action == "conservative_hold"
    assert conservative.can_proceed is True
    assert "conservative" in (conservative.warning or "").lower()


def test_trim_invalid_range_blocks_cleanly():
    result = evaluate_trim_confidence(0.3, "bad", "00:00:10")

    assert result.can_proceed is False
    assert result.block_reason == "invalid_trim_format"
    assert "invalid" in (result.user_message or "").lower()


def test_production_error_sanitization_is_user_safe():
    ffmpeg_msg = sanitize_production_error(
        RuntimeError("ffmpeg failed: C:\\tmp\\video.mp4 rc=1")
    )
    storage_msg = sanitize_production_error(
        RuntimeError("upload to s3://bucket/key failed")
    )

    assert "ffmpeg" not in ffmpeg_msg.lower()
    assert "c:\\tmp" not in ffmpeg_msg.lower()
    assert "s3://" not in storage_msg.lower()
    assert "bucket" not in storage_msg.lower()


@pytest.mark.asyncio
async def test_video_ai_preview_includes_phase8_warnings():
    session = VideoAISkill.initial_session()
    session.collected.update(_collected_fields())

    evidence = _base_evidence()
    evidence.analysis_confidence_overall = "low"
    evidence.confidence_signals.update(
        {"ocr_available": True, "ocr_useful": False, "ocr_text_found": False}
    )
    evidence.grounding_completed = True
    evidence.grounded_features = [
        GroundedFeatureContract(
            feature_id="feat_1",
            original_name="AI Planner",
            grounded=False,
            official_name=None,
            grounding_confidence="low",
        )
    ]

    with patch.object(
        VideoAISkill,
        "_run_demo_analysis_and_grounding",
        new_callable=AsyncMock,
    ) as mock_run_analysis:
        mock_run_analysis.return_value = evidence

        result = await VideoAISkill.execute(
            session=session,
            backend_url="http://backend",
            http_client=AsyncMock(),
        )

    preview_summary = result.session.artifacts["demo_preview_summary"]

    assert result.next_step == "demo_preview_confirm"
    assert preview_summary.get("warnings")
    assert any(
        "confidence is low" in warning.lower()
        for warning in preview_summary["warnings"]
    )
    assert any(
        "reference website" in warning.lower()
        for warning in preview_summary["warnings"]
    )


def test_telegram_renderer_shows_warning_section_for_demo_preview():
    session = VideoAISkill.initial_session()
    session.collected.update(_collected_fields())
    session.step_key = "demo_preview_confirm"
    session.artifacts["demo_preview_summary"] = {
        "video_info": {
            "duration_sec": 45,
            "resolution": "1920x1080",
            "segment_count": 3,
        },
        "confidence": "low",
        "warnings": [
            "Analysis confidence is low. Please review detected features carefully.",
            "None of the detected features could be verified against the reference website.",
        ],
        "grounded_features": [],
        "ungrounded_features": ["AI Planner"],
        "feature_candidates": ["AI Planner"],
        "timeline_narrative": "Shows planning flow",
    }

    rendered = TelegramRenderer.render_skill_prompt(session)

    assert "Warnings" in rendered["text"]
    assert "Analysis confidence is low" in rendered["text"]
    assert "could be verified" in rendered["text"]


def test_should_block_before_concept_respects_combined_weakness_only():
    warn_only = _base_evidence()
    warn_only.analysis_confidence_overall = "low"
    warn_only.grounding_completed = True
    warn_only.grounded_features = []

    block = _base_evidence()
    block.analysis_confidence_overall = "low"
    block.extracted_features = []
    block.feature_candidates = []
    block.confidence_signals.update(
        {"ocr_available": False, "ocr_useful": False, "ocr_text_found": False}
    )

    assert should_block_before_concept(warn_only) is None
    assert should_block_before_concept(block) is not None
    assert build_preview_warnings(warn_only)


def test_high_confidence_no_features_no_ocr_still_blocks():
    """
    Bug fix verification: Even with high confidence (from good video metadata),
    if OCR is unavailable and no features were detected, we must block.
    Phase 4 is OCR-only, so without OCR we have no content analysis.
    """
    evidence = _base_evidence()
    evidence.analysis_confidence_overall = (
        "high"  # From good resolution/duration/segmentation
    )
    evidence.extracted_features = []
    evidence.feature_candidates = []
    evidence.confidence_signals.update(
        {
            "ocr_available": False,
            "ocr_useful": False,
            "ocr_text_found": False,
            "weighted_score": 0.755,  # High score from video metadata
        }
    )

    result = evaluate_analysis_usability(evidence)

    # Must block even with high confidence when no OCR and no features
    assert result.severity == "block"
    assert result.can_proceed is False
    assert result.block_reason == "no_features_no_ocr"
    assert "text recognition" in (result.user_message or "").lower()
