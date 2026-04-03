"""Schema-first creative direction helpers for video pre-production."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict
from urllib.parse import urlparse

from .contracts import (
    ApprovedProductionPackageContract,
    BeatContract,
    BeatSheetContract,
    ConceptBriefContract,
    GroundedFeatureContract,
    RecordedDemoEvidenceContract,
)
from .openclaw_service import OpenClawService

logger = logging.getLogger(__name__)


class CreativeDirectorService:
    """Generate pre-production artifacts from deterministic Telegram inputs."""

    _openclaw_service_class = OpenClawService
    _PUBLIC_ONLY_BLOCKLIST = {
        "dashboard",
        "logged-in",
        "logged in",
        "after login",
        "admin",
        "private workspace",
        "internal tool",
        "authenticated flow",
    }
    _FEATURE_HINT_STOPWORDS = {
        "ai",
        "the",
        "a",
        "an",
        "for",
        "to",
        "of",
        "and",
        "with",
    }

    _DEMO_ANGLE_BY_GOAL = {
        "feature_demo": "grounded_feature_demo",
        "conversion": "grounded_benefit_proof",
        "walkthrough": "step_by_step_demo",
        # Deprecated: "awareness" auto-migrates to "feature_demo" via contract validator
    }
    _DEMO_BEAT_TARGET_SECONDS = {
        "hook": 5,
        "solution_intro": 6,
        "feature_demo": 8,
        "benefit": 6,
        "cta": 5,
    }
    _TRIM_CONFIDENCE_NORMAL_THRESHOLD = 0.8
    _TRIM_CONFIDENCE_CAUTION_THRESHOLD = 0.5

    @classmethod
    def _prompt_context(
        cls,
        *,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "creative_input_mode": "idea_brief",
            "persona": {
                "persona_id": persona_snapshot.get("persona_id"),
                "display_name": persona_snapshot.get("display_name"),
                "language": persona_snapshot.get("language"),
                "tts_voice": persona_snapshot.get("tts_voice"),
                "tone_default": persona_snapshot.get("tone_default"),
            },
            "collected": {
                "persona_id": collected.get("persona_id"),
                "idea_brief": collected.get("idea_brief"),
                "feature_focus": collected.get("feature_focus"),
                "video_goal": collected.get("video_goal"),
                "audience": collected.get("audience"),
                "cta": collected.get("cta"),
                "reference_url": collected.get("reference_url"),
                "access_level": collected.get("access_level"),
                "platform": collected.get("platform") or "tiktok",
            },
        }

    @staticmethod
    def _require_mapping(payload: Any, *, label: str) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(f"{label} must be returned as a JSON object")
        return payload

    @staticmethod
    def _normalized(value: Any) -> str:
        return " ".join(str(value or "").strip().lower().split())

    @classmethod
    def _feature_focus_keywords(cls, feature_focus: str) -> set[str]:
        return {
            token
            for token in cls._normalized(feature_focus).replace("-", " ").split()
            if token and token not in cls._FEATURE_HINT_STOPWORDS and len(token) > 2
        }

    @staticmethod
    def _host_label(reference_url: str) -> str:
        host = urlparse(reference_url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host or "the official product site"

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total_seconds = max(0, int(round(seconds)))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @classmethod
    def _format_timestamp_range(cls, start_sec: float, end_sec: float) -> str:
        safe_end = max(end_sec, start_sec + 1)
        return f"{cls._format_timestamp(start_sec)}-{cls._format_timestamp(safe_end)}"

    @staticmethod
    def _parse_timestamp(timestamp_text: str) -> int:
        hours, minutes, seconds = [int(part) for part in timestamp_text.split(":", 2)]
        return (hours * 3600) + (minutes * 60) + seconds

    @classmethod
    def _parse_timestamp_range(cls, range_text: str) -> tuple[int, int]:
        start_text, end_text = range_text.split("-", 1)
        return cls._parse_timestamp(start_text), cls._parse_timestamp(end_text)

    @staticmethod
    def _trim_confidence_policy(trim_confidence: float) -> str:
        if trim_confidence >= CreativeDirectorService._TRIM_CONFIDENCE_NORMAL_THRESHOLD:
            return "normal"
        if (
            trim_confidence
            >= CreativeDirectorService._TRIM_CONFIDENCE_CAUTION_THRESHOLD
        ):
            return "caution"
        return "conservative_hold"

    @staticmethod
    def _clamp_window(
        start_sec: float,
        end_sec: float,
        *,
        video_duration_sec: float,
    ) -> tuple[float, float]:
        safe_start = max(0.0, min(start_sec, video_duration_sec))
        safe_end = max(safe_start + 1.0, min(end_sec, video_duration_sec))
        if safe_end > video_duration_sec:
            safe_end = max(safe_start + 1.0, video_duration_sec)
            safe_start = max(0.0, safe_end - 1.0)
        return safe_start, safe_end

    @classmethod
    def _window_from_segment(
        cls,
        segment: dict[str, Any],
        *,
        target_duration_sec: int,
        video_duration_sec: float,
        anchor: str,
    ) -> tuple[float, float]:
        seg_start, seg_end = cls._clamp_window(
            float(segment["start_sec"]),
            float(segment["end_sec"]),
            video_duration_sec=video_duration_sec,
        )
        available = max(1.0, seg_end - seg_start)
        clip = min(float(target_duration_sec), available)
        if available <= clip:
            return seg_start, seg_end
        if anchor == "end":
            return seg_end - clip, seg_end
        if anchor == "middle":
            offset = (available - clip) / 2.0
            return seg_start + offset, seg_start + offset + clip
        return seg_start, seg_start + clip

    @staticmethod
    def _first_segment_of_type(
        segment_ranges: list[dict[str, Any]], segment_type: str
    ) -> dict[str, Any] | None:
        for segment in segment_ranges:
            if segment["purpose"] == segment_type:
                return segment
        return None

    @classmethod
    def _demo_grounded_feature_names(
        cls, evidence: RecordedDemoEvidenceContract
    ) -> list[str]:
        names: list[str] = []
        for grounded in evidence.grounded_features:
            name = (
                grounded.official_name
                if grounded.grounded and grounded.official_name
                else grounded.original_name
            )
            if name and name not in names:
                names.append(name)
        for candidate in evidence.feature_candidates:
            if candidate and candidate not in names:
                names.append(candidate)
        for feature in evidence.extracted_features:
            if feature.name and feature.name not in names:
                names.append(feature.name)
        return names

    @classmethod
    def _best_feature_match(
        cls,
        text: str,
        grounded_features: list[GroundedFeatureContract],
        fallback_names: list[str],
    ) -> str | None:
        normalized_text = cls._normalized(text)
        if not normalized_text:
            return None
        text_tokens = set(normalized_text.replace("-", " ").split())
        best_name = None
        best_score = 0
        candidates = [
            grounded.official_name or grounded.original_name
            for grounded in grounded_features
            if grounded.official_name or grounded.original_name
        ] + fallback_names
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            candidate_tokens = set(cls._normalized(candidate).replace("-", " ").split())
            score = len(text_tokens.intersection(candidate_tokens))
            if score > best_score:
                best_name = candidate
                best_score = score
        return best_name if best_score > 0 else None

    @classmethod
    def _select_demo_feature_focus(
        cls,
        evidence: RecordedDemoEvidenceContract,
        collected: Dict[str, Any],
    ) -> str:
        fallback_names = cls._demo_grounded_feature_names(evidence)
        user_text = (
            evidence.confidence_signals.get("user_correction")
            or evidence.confidence_signals.get("user_reemphasis")
            or collected.get("feature_emphasis")
            or ""
        )

        # If user provided a correction/emphasis, they explicitly want to override
        # detected features. Use their input directly unless it's an exact match
        # to an existing feature (in which case, normalize to official name).
        if user_text.strip():
            clean_user_text = user_text.strip()[:100]
            normalized_user = cls._normalized(clean_user_text)

            # Check for exact or near-exact match with existing features
            for feature in evidence.grounded_features:
                official = feature.official_name or feature.original_name
                if official and cls._normalized(official) == normalized_user:
                    return official  # Use normalized official name
            for name in fallback_names:
                if name and cls._normalized(name) == normalized_user:
                    return name  # Use the existing name casing

            # No exact match - user is providing a novel feature name
            # Trust their input as-is (they may be correcting a miss)
            return clean_user_text

        # No user input - fall back to first detected feature name
        # (Note: _best_feature_match requires non-empty text to do matching,
        # so without user input we skip directly to the fallback)
        if fallback_names:
            return fallback_names[0]
        return "Recorded demo highlights"

    @classmethod
    def _build_demo_source_summary(
        cls,
        evidence: RecordedDemoEvidenceContract,
        collected: Dict[str, Any],
        feature_focus: str,
    ) -> str:
        host_label = cls._host_label(str(collected.get("reference_url") or ""))
        segment_types = [segment.segment_type for segment in evidence.segments]
        summary_parts = [f"Recorded demo grounded against {host_label}."]
        if feature_focus:
            summary_parts.append(f"Confirmed focus stays on {feature_focus}.")
        if evidence.timeline_narrative:
            summary_parts.append(evidence.timeline_narrative.strip())
        elif segment_types:
            summary_parts.append(
                "Observed flow: " + " -> ".join(segment_types[:5]) + "."
            )
        grounded_names = [
            grounded.official_name or grounded.original_name
            for grounded in evidence.grounded_features
            if grounded.grounded
        ]

    @classmethod
    def _enforce_disjoint(
        cls, windows: list[tuple[float, float]], max_duration: float
    ) -> list[tuple[float, float]]:
        """
        Enforce disjoint beat windows with 0.5s gap (Fix 2 - V3.1).

        Adjusts beat windows to prevent overlap, preserving order.

        Args:
            windows: List of (start, end) tuples
            max_duration: Maximum duration (video length)

        Returns:
            List of adjusted (start, end) tuples
        """
        MIN_GAP = 0.5  # 0.5s gap between beats
        MIN_BEAT_DURATION = 2.0  # Minimum beat duration

        result = []
        for i, (start, end) in enumerate(windows):
            if result and start < result[-1][1] + MIN_GAP:
                # Overlap detected, adjust start
                start = result[-1][1] + MIN_GAP
                if start >= end:
                    # Beat too short, extend end
                    end = start + MIN_BEAT_DURATION

            # Cap at max duration
            end = min(end, max_duration)
            result.append((start, end))

        return result

    @classmethod
    def _build_demo_beat_messages(
        cls,
        concept: ConceptBriefContract,
        evidence: RecordedDemoEvidenceContract,
    ) -> list[dict[str, Any]]:
        segment_ranges = [
            {
                "start_sec": segment.start_sec,
                "end_sec": segment.end_sec,
                "purpose": segment.segment_type,
                "description": segment.description
                or segment.segment_type.replace("_", " "),
                "overlay": (
                    segment.ocr_texts[0]
                    if segment.ocr_texts
                    else segment.segment_type.replace("_", " ").title()
                )[:50],
            }
            for segment in evidence.segments
        ]
        if not segment_ranges:
            segment_ranges = [
                {
                    "start_sec": 0.0,
                    "end_sec": max(evidence.duration_sec, 5.0),
                    "purpose": "feature_demo",
                    "description": "Recorded demo walkthrough",
                    "overlay": concept.feature_focus,
                }
            ]
        intro_range = (
            cls._first_segment_of_type(segment_ranges, "intro") or segment_ranges[0]
        )
        feature_segments = [
            segment
            for segment in segment_ranges
            if segment["purpose"] == "feature_demo"
        ]
        primary_feature_range = (
            feature_segments[0]
            if feature_segments
            else segment_ranges[min(1, len(segment_ranges) - 1)]
        )
        benefit_range = (
            feature_segments[-1]
            if feature_segments
            else segment_ranges[min(2, len(segment_ranges) - 1)]
        )
        cta_range = (
            cls._first_segment_of_type(segment_ranges, "outro") or segment_ranges[-1]
        )
        hook_start, hook_end = cls._window_from_segment(
            intro_range,
            target_duration_sec=cls._DEMO_BEAT_TARGET_SECONDS["hook"],
            video_duration_sec=evidence.duration_sec,
            anchor="start",
        )
        solution_start, solution_end = cls._window_from_segment(
            primary_feature_range,
            target_duration_sec=cls._DEMO_BEAT_TARGET_SECONDS["solution_intro"],
            video_duration_sec=evidence.duration_sec,
            anchor="start",
        )
        feature_start, feature_end = cls._window_from_segment(
            primary_feature_range,
            target_duration_sec=cls._DEMO_BEAT_TARGET_SECONDS["feature_demo"],
            video_duration_sec=evidence.duration_sec,
            anchor="middle",
        )
        benefit_start, benefit_end = cls._window_from_segment(
            benefit_range,
            target_duration_sec=cls._DEMO_BEAT_TARGET_SECONDS["benefit"],
            video_duration_sec=evidence.duration_sec,
            anchor="end",
        )
        cta_start, cta_end = cls._window_from_segment(
            cta_range,
            target_duration_sec=cls._DEMO_BEAT_TARGET_SECONDS["cta"],
            video_duration_sec=evidence.duration_sec,
            anchor="end",
        )

        # V3.1 (Fix 2): Enforce disjoint windows with 0.5s gap
        raw_windows = [
            (hook_start, hook_end),
            (solution_start, solution_end),
            (feature_start, feature_end),
            (benefit_start, benefit_end),
            (cta_start, cta_end),
        ]
        disjoint_windows = cls._enforce_disjoint(raw_windows, evidence.duration_sec)
        hook_start, hook_end = disjoint_windows[0]
        solution_start, solution_end = disjoint_windows[1]
        feature_start, feature_end = disjoint_windows[2]
        benefit_start, benefit_end = disjoint_windows[3]
        cta_start, cta_end = disjoint_windows[4]

        return [
            {
                "purpose": "hook",
                "segment": {
                    **intro_range,
                    "start_sec": hook_start,
                    "end_sec": hook_end,
                },
                "message": f"This demo gets straight to {concept.feature_focus} so viewers see the product in action fast.",
                "overlay": concept.feature_focus,
            },
            {
                "purpose": "solution_intro",
                "segment": {
                    **primary_feature_range,
                    "start_sec": solution_start,
                    "end_sec": solution_end,
                },
                "message": f"Here the flow introduces how {concept.feature_focus} works for {concept.audience}.",
                "overlay": primary_feature_range["overlay"],
            },
            {
                "purpose": "feature_demo",
                "segment": {
                    **primary_feature_range,
                    "start_sec": feature_start,
                    "end_sec": feature_end,
                },
                "message": f"Stay on the real demo flow and call out {concept.feature_focus} using the grounded product terminology.",
                "overlay": concept.feature_focus,
            },
            {
                "purpose": "benefit",
                "segment": {
                    **benefit_range,
                    "start_sec": benefit_start,
                    "end_sec": benefit_end,
                },
                "message": f"Connect this on-screen step back to the user value behind {concept.feature_focus} without adding claims beyond the demo.",
                "overlay": "User value",
            },
            {
                "purpose": "cta",
                "segment": {**cta_range, "start_sec": cta_start, "end_sec": cta_end},
                "message": concept.cta,
                "overlay": "Call to action",
            },
        ]

    @classmethod
    async def build_concept_from_demo_evidence(
        cls,
        evidence: RecordedDemoEvidenceContract,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
    ) -> ConceptBriefContract:
        # V3.1: Validate resolved_idea exists and is complete
        if not evidence.resolved_idea:
            raise ValueError(
                "Cannot build concept: resolved_idea is None. IdeaResolver must run first."
            )
        if evidence.resolved_idea.open_questions:
            raise ValueError(
                f"Cannot build concept: resolved_idea has open questions: {evidence.resolved_idea.open_questions}"
            )

        feature_focus = cls._select_demo_feature_focus(evidence, collected)
        concept = ConceptBriefContract(
            persona_id=str(collected.get("persona_id") or ""),
            creative_input_mode="recorded_demo_video",
            feature_focus=feature_focus,
            video_goal=str(collected.get("video_goal") or "feature_demo"),
            audience=str(collected.get("audience") or ""),
            angle=cls._DEMO_ANGLE_BY_GOAL.get(
                str(collected.get("video_goal") or "feature_demo"),
                "grounded_feature_demo",
            ),
            platform=str(collected.get("platform") or "tiktok"),
            cta=str(collected.get("cta") or ""),
            reference_url=str(collected.get("reference_url") or ""),
            access_level=str(collected.get("access_level") or "unknown"),
            source_summary=cls._build_demo_source_summary(
                evidence,
                collected,
                feature_focus,
            ),
            tone_resolved=str(persona_snapshot.get("tone_default") or "natural"),
            demo_video_telegram_file_id=collected.get("demo_video_telegram_file_id"),
            demo_video_asset_url=collected.get("demo_video_asset_url")
            or evidence.demo_video_asset_url,
        )
        cls._validate_demo_concept_quality(
            concept=concept,
            evidence=evidence,
            collected=collected,
            persona_snapshot=persona_snapshot,
        )
        return concept

    @classmethod
    async def build_beats_from_demo_evidence(
        cls,
        concept_brief: ConceptBriefContract,
        evidence: RecordedDemoEvidenceContract,
    ) -> BeatSheetContract:
        beat_specs = cls._build_demo_beat_messages(concept_brief, evidence)
        beats: list[BeatContract] = []
        for idx, spec in enumerate(beat_specs, start=1):
            segment = spec["segment"]
            start_sec = float(segment["start_sec"])
            end_sec = float(segment["end_sec"])
            duration_sec = max(1, int(round(end_sec - start_sec)))
            beats.append(
                BeatContract(
                    idx=idx,
                    purpose=spec["purpose"],
                    bottom_half_message=spec["message"],
                    top_half_source_type="uploaded_demo_video",
                    top_half_target=cls._format_timestamp_range(start_sec, end_sec),
                    top_half_capture_hint=segment["description"],
                    top_half_follow_links=False,
                    top_half_max_capture_seconds=max(8, min(60, duration_sec)),
                    source_ref=evidence.demo_video_asset_url,
                    overlay_text=spec["overlay"],
                    duration_sec=duration_sec,
                    trim_confidence=cls._segment_trim_confidence(
                        evidence, start_sec, end_sec
                    ),
                )
            )
        beat_sheet = BeatSheetContract(beats=beats)
        cls._validate_demo_beat_mapping(beats=beats, evidence=evidence)
        cls._validate_beat_sheet_quality(
            concept_brief=concept_brief,
            beat_sheet=beat_sheet,
        )
        return beat_sheet

    @classmethod
    def _validate_concept_quality(
        cls,
        *,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
        concept: ConceptBriefContract,
    ) -> None:
        expected_tone = (
            str(persona_snapshot.get("tone_default") or "natural").strip() or "natural"
        )
        required_exact = {
            "persona_id": collected.get("persona_id"),
            "feature_focus": collected.get("feature_focus"),
            "video_goal": collected.get("video_goal"),
            "audience": collected.get("audience"),
            "cta": collected.get("cta"),
            "reference_url": collected.get("reference_url"),
            "access_level": collected.get("access_level"),
            "platform": collected.get("platform") or "tiktok",
        }

        for field_name, expected in required_exact.items():
            actual = getattr(concept, field_name)
            if cls._normalized(actual) != cls._normalized(expected):
                raise ValueError(
                    f"ConceptBrief drifted from collected {field_name}: expected '{expected}', got '{actual}'"
                )

        if cls._normalized(concept.tone_resolved) != cls._normalized(expected_tone):
            raise ValueError(
                f"ConceptBrief tone_resolved drifted from persona tone: expected '{expected_tone}', got '{concept.tone_resolved}'"
            )

        source_summary = cls._normalized(concept.source_summary)
        if not source_summary:
            raise ValueError("ConceptBrief source_summary must not be empty")
        if concept.access_level == "public_page_only":
            for blocked in cls._PUBLIC_ONLY_BLOCKLIST:
                if blocked in source_summary:
                    raise ValueError(
                        f"ConceptBrief source_summary overclaims private product access for public_page_only: '{blocked}'"
                    )

    @classmethod
    def _validate_beat_sheet_quality(
        cls,
        *,
        concept_brief: ConceptBriefContract,
        beat_sheet: BeatSheetContract,
    ) -> None:
        beats = beat_sheet.beats
        if not beats:
            raise ValueError("BeatSheet must contain beats")
        if beats[0].purpose != "hook":
            raise ValueError("BeatSheet must start with a hook beat")
        if beats[-1].purpose != "cta":
            raise ValueError("BeatSheet must end with a cta beat")

        expected_idx = list(range(1, len(beats) + 1))
        actual_idx = [beat.idx for beat in beats]
        if actual_idx != expected_idx:
            raise ValueError(
                f"BeatSheet idx values must be contiguous starting at 1: {actual_idx}"
            )

        middle_purposes = {beat.purpose for beat in beats[1:-1]}
        if not middle_purposes.intersection(
            {
                "problem",
                "solution_intro",
                "feature_demo",
                "product_positioning",
                "proof",
                "benefit",
            }
        ):
            raise ValueError("BeatSheet middle beats do not build toward the CTA")

        if concept_brief.access_level == "public_page_only":
            if any(
                beat.top_half_source_type == "authenticated_capture_later"
                for beat in beats
            ):
                raise ValueError(
                    "BeatSheet overclaims authenticated capture while access_level is public_page_only"
                )

        feature_keywords = cls._feature_focus_keywords(concept_brief.feature_focus)
        if feature_keywords:
            joined_text = " ".join(
                cls._normalized(beat.bottom_half_message)
                + " "
                + cls._normalized(beat.top_half_target)
                + " "
                + cls._normalized(beat.top_half_capture_hint)
                + " "
                + cls._normalized(beat.overlay_text)
                for beat in beats
            )
            if not any(keyword in joined_text for keyword in feature_keywords):
                raise ValueError(
                    "BeatSheet does not stay grounded on the approved feature_focus"
                )

    @classmethod
    def _validate_demo_concept_quality(
        cls,
        *,
        concept: ConceptBriefContract,
        evidence: RecordedDemoEvidenceContract,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
    ) -> None:
        """
        Validate ConceptBrief quality for demo video mode (V3.1).

        Similar to _validate_concept_quality but tailored for demo videos.
        """
        # Check required fields are present
        if not concept.feature_focus:
            raise ValueError(
                "ConceptBrief feature_focus must not be empty for demo mode"
            )

        if not concept.demo_video_asset_url:
            raise ValueError(
                "ConceptBrief must have demo_video_asset_url for demo mode"
            )

        # Validate feature_focus is grounded in evidence
        grounded_names = {
            f.official_name or f.original_name
            for f in evidence.grounded_features
            if f.grounded
        }
        feature_candidates = set(evidence.feature_candidates)
        allowed_features = grounded_names | feature_candidates

        if concept.feature_focus not in allowed_features:
            # Allow if any keyword matches
            feature_lower = concept.feature_focus.lower()
            if not any(
                feature_lower in f.lower() or f.lower() in feature_lower
                for f in allowed_features
            ):
                logger.warning(
                    f"Demo ConceptBrief feature_focus '{concept.feature_focus}' not found in evidence. "
                    f"Available: {allowed_features}"
                )

    @classmethod
    def _segment_trim_confidence(
        cls,
        evidence: RecordedDemoEvidenceContract,
        start_sec: float,
        end_sec: float,
    ) -> float:
        """
        Calculate trim confidence for a segment based on evidence quality (V3.1).

        Returns a confidence score between 0.0 and 1.0.
        """
        # Base confidence from analysis
        base_confidence = 0.5

        # Boost if we have timeline steps that overlap this segment
        if evidence.timeline_steps:
            overlapping_steps = [
                step
                for step in evidence.timeline_steps
                if step.start_sec < end_sec and step.end_sec > start_sec
            ]
            if overlapping_steps:
                base_confidence += 0.2

        # Boost if we have frame understandings
        if evidence.frame_understandings:
            base_confidence += 0.1

        # Boost if overall analysis confidence is high
        if evidence.analysis_confidence_overall == "high":
            base_confidence += 0.15
        elif evidence.analysis_confidence_overall == "medium":
            base_confidence += 0.05

        # Cap at 1.0
        return min(1.0, base_confidence)

    @classmethod
    def _validate_demo_beat_mapping(
        cls,
        *,
        beats: list[BeatContract],
        evidence: RecordedDemoEvidenceContract,
    ) -> None:
        """
        Validate that beats map correctly to demo video segments (V3.1).

        Ensures beat timestamps are within video duration and make sense.
        """
        video_duration = evidence.duration_sec

        for beat in beats:
            # Parse the timestamp range from top_half_target
            if beat.top_half_target and "-" in beat.top_half_target:
                try:
                    start_sec, end_sec = cls._parse_timestamp_range(
                        beat.top_half_target
                    )

                    # Validate within video bounds
                    if start_sec < 0:
                        logger.warning(
                            f"Beat {beat.idx} start time {start_sec} is negative"
                        )

                    if end_sec > video_duration + 1:  # Allow 1 second tolerance
                        logger.warning(
                            f"Beat {beat.idx} end time {end_sec} exceeds video duration {video_duration}"
                        )

                    if start_sec >= end_sec:
                        logger.warning(
                            f"Beat {beat.idx} has invalid time range: {start_sec} >= {end_sec}"
                        )

                except (ValueError, IndexError) as e:
                    logger.warning(
                        f"Beat {beat.idx} has unparseable timestamp range: {e}"
                    )

    @classmethod
    async def build_concept_brief(
        cls,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
    ) -> ConceptBriefContract:
        context = cls._prompt_context(
            collected=collected, persona_snapshot=persona_snapshot
        )
        prompt = (
            "You are the creative director for a short AI influencer video.\n"
            "Normalize the operator input into a single conservative ConceptBrief JSON object.\n"
            "Rules:\n"
            "- Output JSON only.\n"
            "- creative_input_mode must be 'idea_brief'.\n"
            "- Keep platform as the provided platform.\n"
            "- Keep video_goal exactly within: feature_demo, conversion, walkthrough.\n"
            "- Infer a short angle that matches the goal and idea.\n"
            "- source_summary must be conservative and avoid claiming product details that are not explicitly visible from the provided source context.\n"
            "- tone_resolved must prefer the provided persona tone_default, otherwise 'natural'.\n"
            "- Do not invent new fields.\n"
            "Return this exact shape:\n"
            "{\n"
            '  "persona_id": "...",\n'
            '  "creative_input_mode": "idea_brief",\n'
            '  "feature_focus": "...",\n'
            '  "video_goal": "feature_demo|conversion|walkthrough",\n'
            '  "audience": "...",\n'
            '  "angle": "...",\n'
            '  "platform": "tiktok",\n'
            '  "cta": "...",\n'
            '  "reference_url": "https://...",\n'
            '  "access_level": "public_page_only|has_logged_in_access|login_required_but_not_available|unknown",\n'
            '  "source_summary": "...",\n'
            '  "tone_resolved": "..."\n'
            "}\n"
            f"Input context:\n{json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True)}"
        )
        async with cls._openclaw_service_class() as service:
            response = await service.execute_task(
                task_type="video_preproduction_concept_brief",
                prompt=prompt,
                user_id=f"creative-director:{collected.get('persona_id') or 'unknown'}",
                context=context,
            )
        contract = ConceptBriefContract.model_validate(
            cls._require_mapping(response, label="ConceptBrief")
        )
        cls._validate_concept_quality(
            collected=collected,
            persona_snapshot=persona_snapshot,
            concept=contract,
        )
        return contract

    @classmethod
    async def build_beat_sheet(
        cls,
        concept_brief: ConceptBriefContract,
        persona_snapshot: Dict[str, Any],
    ) -> BeatSheetContract:
        concept_payload = concept_brief.model_dump(mode="json")
        context = {
            "concept_brief": concept_payload,
            "persona": {
                "persona_id": persona_snapshot.get("persona_id"),
                "language": persona_snapshot.get("language"),
                "tts_voice": persona_snapshot.get("tts_voice"),
                "tone_default": persona_snapshot.get("tone_default"),
            },
        }
        prompt = (
            "You are planning the pre-production BeatSheet for a split-screen short video.\n"
            "Generate JSON only.\n"
            "Rules:\n"
            "- Return a BeatSheet with 5 beats by default. Use 6 beats only if the feature demo clearly needs one extra beat.\n"
            "- Keep beat purpose within: hook, problem, solution_intro, feature_demo, product_positioning, proof, benefit, expectation_setting, cta.\n"
            "- Keep top_half_source_type within: public_page_capture, authenticated_capture_later, ai_visual_fallback, hybrid_candidate.\n"
            "- IMPORTANT: When top_half_source_type is 'public_page_capture', leave source_ref as null (the system will auto-fill it from the concept_brief reference_url).\n"
            "- Only use 'ai_visual_fallback' for abstract visuals that cannot be captured from the website (e.g., emotions, metaphors, conceptual imagery).\n"
            "- For demos, walkthroughs, and feature showcases, prefer 'public_page_capture' to show the REAL website.\n"
            "- bottom_half_message should be concise and production-friendly.\n"
            "- top_half_target should name the source area or section to capture (e.g., 'Hero Section', 'Features Grid', 'Pricing Table').\n"
            "- top_half_capture_hint should describe how to capture it (e.g., 'scroll', 'static', 'Scroll hero section').\n"
            "- top_half_follow_links must be true for walkthrough-like or demo-like beats where moving to relevant internal pages helps storytelling.\n"
            "- top_half_max_capture_seconds must be an integer between 8 and 60. Prefer 45-60 for walkthrough beats and 12-30 for simple beats.\n"
            "- Do not invent product details beyond the concept brief and source_summary.\n"
            "Return this exact shape:\n"
            "{\n"
            '  "concept_id": "concept_xxxx",\n'
            '  "beats": [\n'
            "    {\n"
            '      "idx": 1,\n'
            '      "purpose": "hook",\n'
            '      "bottom_half_message": "...",\n'
            '      "top_half_source_type": "public_page_capture",\n'
            '      "top_half_target": "Hero Section",\n'
            '      "top_half_capture_hint": "scroll",\n'
            '      "top_half_follow_links": true,\n'
            '      "top_half_max_capture_seconds": 45,\n'
            '      "source_ref": null,\n'
            '      "overlay_text": "...",\n'
            '      "duration_sec": 4\n'
            "    }\n"
            "  ]\n"
            "}\n"
            f"Input context:\n{json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True)}"
        )
        async with cls._openclaw_service_class() as service:
            response = await service.execute_task(
                task_type="video_preproduction_beat_sheet",
                prompt=prompt,
                user_id=f"creative-director:{concept_brief.persona_id}",
                context=context,
            )
        contract = BeatSheetContract.model_validate(
            cls._require_mapping(response, label="BeatSheet")
        )
        cls._validate_beat_sheet_quality(
            concept_brief=concept_brief,
            beat_sheet=contract,
        )
        return contract

    @classmethod
    def build_approved_package(
        cls,
        concept_brief: ConceptBriefContract,
        beat_sheet: BeatSheetContract,
        persona_snapshot: Dict[str, Any],
    ) -> ApprovedProductionPackageContract:
        return ApprovedProductionPackageContract(
            concept_brief=concept_brief,
            beat_sheet=beat_sheet,
            persona_snapshot=persona_snapshot,
        )
