"""
Failure handling policy for recorded_demo_video pipeline (Phase 8).

Classifies analysis/grounding/trim outcomes into severity levels and maps
them to user-safe Telegram behavior. Keeps the policy lightweight and explicit.

Severity levels:
- silent: Continue without user notification
- warn: Continue with preview warning
- block: Stop and require user action (retry/reupload/clarify)

Priority for evidence trust:
official site/docs > user confirmation > video evidence > model inference
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

if TYPE_CHECKING:
    from services.contracts import RecordedDemoEvidenceContract

SeverityLevel = Literal["silent", "warn", "block"]


@dataclass
class FailurePolicyResult:
    """Result of failure policy evaluation."""

    severity: SeverityLevel
    can_proceed: bool
    warnings: List[str] = field(default_factory=list)
    block_reason: Optional[str] = None
    user_message: Optional[str] = None  # Telegram-safe message


# ==============================================================================
# Analysis Stage Policy
# ==============================================================================


def evaluate_analysis_usability(
    evidence: "RecordedDemoEvidenceContract",
) -> FailurePolicyResult:
    """
    Evaluate whether analysis evidence is usable for downstream processing.

    Decision rules:
    - Block if evidence is structurally broken (duration=0, width=0, height=0)
    - Block if metadata extraction failed
    - Block if low confidence + no usable features + OCR unavailable
    - Warn if low confidence but still has usable features
    - Warn if OCR unavailable but other signals present
    - Silent if confidence is medium/high with valid features
    """
    warnings: List[str] = []
    signals = evidence.confidence_signals or {}

    # Check for structurally broken evidence (P0.2 guard, but also here for policy)
    if evidence.duration_sec <= 0 or evidence.width <= 0 or evidence.height <= 0:
        return FailurePolicyResult(
            severity="block",
            can_proceed=False,
            block_reason="metadata_extraction_failed",
            user_message=(
                "Could not read the video file properly. "
                "Please try uploading a different video."
            ),
        )

    # Check for explicit error in signals
    if "error" in signals:
        error_type = signals.get("error", "unknown")
        return FailurePolicyResult(
            severity="block",
            can_proceed=False,
            block_reason=f"analysis_error:{error_type}",
            user_message=(
                "Video analysis encountered an issue. "
                "Please try uploading a different video."
            ),
        )

    # Evaluate OCR availability
    ocr_available = signals.get(
        "ocr_available", True
    )  # Default true for backward compat
    ocr_useful = signals.get("ocr_useful", True)
    has_ocr_text = bool(evidence.extracted_features) or signals.get(
        "ocr_text_found", False
    )

    # Evaluate feature extraction
    has_features = len(evidence.extracted_features) > 0
    has_grounded = len(evidence.grounded_features) > 0

    # Get overall confidence
    confidence = evidence.analysis_confidence_overall

    # Case: Low confidence + no features + OCR unavailable = block
    if confidence == "low" and not has_features and not ocr_available:
        return FailurePolicyResult(
            severity="block",
            can_proceed=False,
            block_reason="low_confidence_no_features_no_ocr",
            user_message=(
                "Could not extract enough information from this video. "
                "Please upload a clearer recording or one with visible text/UI elements."
            ),
        )

    # Case: Low confidence + no features (but OCR available) = block
    if confidence == "low" and not has_features:
        return FailurePolicyResult(
            severity="block",
            can_proceed=False,
            block_reason="low_confidence_no_features",
            user_message=(
                "Could not identify features in this video. "
                "Please upload a video that clearly shows the product features."
            ),
        )

    # Case: OCR unavailable - warn but continue if has features
    if not ocr_available:
        warnings.append(
            "Text recognition was unavailable. Feature detection relied on visual analysis only."
        )

    # Case: OCR weak/no useful text - warn but continue
    if ocr_available and not ocr_useful and not has_ocr_text:
        warnings.append(
            "No readable text was detected. Feature names may need manual correction."
        )

    # Case: Low confidence but has features - warn
    if confidence == "low" and has_features:
        warnings.append(
            "Analysis confidence is low. Please review detected features carefully."
        )

    # Case: Medium confidence - subtle warn
    if confidence == "medium":
        warnings.append(
            "Some details may need verification. Review the detected features below."
        )

    # Determine severity
    if warnings:
        return FailurePolicyResult(
            severity="warn",
            can_proceed=True,
            warnings=warnings,
        )

    return FailurePolicyResult(
        severity="silent",
        can_proceed=True,
    )


# ==============================================================================
# Grounding Stage Policy
# ==============================================================================


def evaluate_grounding_quality(
    evidence: "RecordedDemoEvidenceContract",
) -> FailurePolicyResult:
    """
    Evaluate grounding quality and determine if warnings are needed.

    Decision rules:
    - Zero grounded features alone does NOT auto-block
    - Warn if no grounded features but OCR-derived candidates exist
    - Warn if grounding was skipped (no reference_url)
    - Block only if zero grounding + low confidence + weak evidence combined
    """
    warnings: List[str] = []
    signals = evidence.confidence_signals or {}

    has_extracted = len(evidence.extracted_features) > 0
    has_grounded = sum(1 for f in evidence.grounded_features if f.grounded) > 0
    total_grounded_attempts = len(evidence.grounded_features)
    grounding_completed = evidence.grounding_completed

    # Get analysis usability first
    analysis_result = evaluate_analysis_usability(evidence)
    if analysis_result.severity == "block":
        # If analysis itself is unusable, grounding policy is moot
        return analysis_result

    # Case: Grounding was not attempted (no reference_url)
    if not grounding_completed:
        warnings.append(
            "Feature verification was skipped (no reference URL provided). "
            "Feature names are based on video analysis only."
        )
        return FailurePolicyResult(
            severity="warn",
            can_proceed=True,
            warnings=warnings,
        )

    # Case: Zero grounded features out of attempted
    if total_grounded_attempts > 0 and not has_grounded:
        # Check if this combines with low confidence for blocking
        confidence = evidence.analysis_confidence_overall
        if confidence == "low":
            # Combined weakness: low confidence + zero grounding
            return FailurePolicyResult(
                severity="block",
                can_proceed=False,
                block_reason="low_confidence_zero_grounding",
                user_message=(
                    "Could not verify any features against the reference website, "
                    "and analysis confidence is low. Please try:\n"
                    "- Uploading a clearer video\n"
                    "- Providing a different reference URL\n"
                    "- Correcting the detected features manually"
                ),
            )

        # Zero grounding but confidence is medium/high - warn only
        warnings.append(
            "None of the detected features could be verified against the reference website. "
            "Feature names may not match official documentation."
        )

    # Case: Partial grounding
    elif total_grounded_attempts > 0 and has_grounded:
        grounded_count = sum(1 for f in evidence.grounded_features if f.grounded)
        ungrounded_count = total_grounded_attempts - grounded_count
        if ungrounded_count > 0:
            warnings.append(
                f"{ungrounded_count} of {total_grounded_attempts} features could not be verified. "
                "Unverified feature names are based on video analysis."
            )

    if warnings:
        return FailurePolicyResult(
            severity="warn",
            can_proceed=True,
            warnings=warnings,
        )

    return FailurePolicyResult(
        severity="silent",
        can_proceed=True,
    )


# ==============================================================================
# Trim Confidence Policy
# ==============================================================================


@dataclass
class TrimPolicyResult:
    """Result of trim confidence evaluation."""

    action: Literal["normal", "caution", "conservative_hold"]
    can_proceed: bool
    warning: Optional[str] = None
    block_reason: Optional[str] = None
    user_message: Optional[str] = None


def evaluate_trim_confidence(
    trim_confidence: float,
    trim_start: Optional[str],
    trim_end: Optional[str],
) -> TrimPolicyResult:
    """
    Evaluate trim confidence and determine handling action.

    Semantics:
    - >= 0.8: normal (proceed without warning)
    - 0.5-0.79: caution (proceed with internal warning)
    - < 0.5: conservative_hold (use conservative window if valid, warn)

    Does NOT auto-fallback to AI. Uses conservative mapped window if valid.
    Fails clearly if trim range is invalid.
    """
    # Validate trim range exists
    if not trim_start or not trim_end:
        return TrimPolicyResult(
            action="conservative_hold",
            can_proceed=False,
            block_reason="missing_trim_range",
            user_message="Could not determine video segment timing. Please try a different video.",
        )

    # Validate trim range format (basic check)
    try:
        _parse_timestamp(trim_start)
        _parse_timestamp(trim_end)
    except (ValueError, IndexError):
        return TrimPolicyResult(
            action="conservative_hold",
            can_proceed=False,
            block_reason="invalid_trim_format",
            user_message="Video segment timing is invalid. Please try a different video.",
        )

    # Check trim confidence thresholds
    if trim_confidence >= 0.8:
        return TrimPolicyResult(
            action="normal",
            can_proceed=True,
        )

    if trim_confidence >= 0.5:
        return TrimPolicyResult(
            action="caution",
            can_proceed=True,
            warning=f"Trim confidence is moderate ({trim_confidence:.0%}). Segment boundaries may be approximate.",
        )

    # < 0.5: conservative_hold
    return TrimPolicyResult(
        action="conservative_hold",
        can_proceed=True,
        warning=f"Trim confidence is low ({trim_confidence:.0%}). Using conservative segment boundaries.",
    )


def _parse_timestamp(ts: str) -> float:
    """Parse HH:MM:SS or HH:MM:SS.mmm to seconds."""
    parts = ts.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


# ==============================================================================
# Production/Assembly Failure Policy
# ==============================================================================


def sanitize_production_error(error: Exception) -> str:
    """
    Convert production/assembly errors to user-safe messages.

    Prevents exposing ffmpeg commands, file paths, storage errors, etc.
    """
    error_text = str(error).lower()

    # FFmpeg errors
    if "ffmpeg" in error_text or "ffprobe" in error_text:
        return "Video processing failed. Please try again or contact support."

    # Trim/segment extraction errors
    if "trim" in error_text or "segment" in error_text or "extract" in error_text:
        return "Could not extract the video segment. Please try again."

    # Storage errors
    if any(p in error_text for p in ["storage", "bucket", "blob", "s3://", "upload"]):
        return "Could not save the video. Please try again in a few minutes."

    # Download errors
    if "download" in error_text or "fetch" in error_text:
        return "Could not access the source video. Please try re-uploading."

    # Timeout errors
    if "timeout" in error_text:
        return "Processing timed out. Please try again."

    # Generic fallback
    return "Video production failed. Please try again or contact support."


# ==============================================================================
# Combined Preview Warning Builder
# ==============================================================================


def build_preview_warnings(
    evidence: "RecordedDemoEvidenceContract",
) -> List[str]:
    """
    Build combined list of warnings for demo preview.

    Aggregates warnings from analysis and grounding evaluation.
    Returns empty list if no warnings.
    """
    warnings: List[str] = []

    # Get analysis warnings
    analysis_result = evaluate_analysis_usability(evidence)
    if analysis_result.severity == "warn":
        warnings.extend(analysis_result.warnings)

    # Get grounding warnings (only if analysis is usable)
    if analysis_result.can_proceed:
        grounding_result = evaluate_grounding_quality(evidence)
        if grounding_result.severity == "warn":
            warnings.extend(grounding_result.warnings)

    # Deduplicate while preserving order
    seen = set()
    unique_warnings = []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            unique_warnings.append(w)

    return unique_warnings


def should_block_before_concept(
    evidence: "RecordedDemoEvidenceContract",
) -> Optional[str]:
    """
    Check if evidence is too weak to proceed to concept/beat generation.

    Returns block message if should block, None if can proceed.
    """
    # Check analysis usability
    analysis_result = evaluate_analysis_usability(evidence)
    if analysis_result.severity == "block":
        return analysis_result.user_message

    # Check grounding quality
    grounding_result = evaluate_grounding_quality(evidence)
    if grounding_result.severity == "block":
        return grounding_result.user_message

    return None
