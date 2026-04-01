"""
Demo Feature Grounding Service (Phase 5).

Uses OpenClaw to verify and enrich feature candidates against official sources.

Source-of-truth priority:
1. Official site/docs (grounded=True)
2. User confirmation
3. Video evidence
4. Model inference (grounded=False)

This service:
- Takes extracted features from Phase 4 analysis
- Uses OpenClaw to browse reference_url and verify features
- Enriches feature names with official terminology
- Adds value propositions from official marketing
- Does NOT treat ungrounded OCR-derived names as facts
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

from services.contracts import (
    ExtractedFeatureContract,
    GroundedFeatureContract,
    RecordedDemoEvidenceContract,
    TimelineSegmentContract,
)
from services.openclaw_service import OpenClawService

logger = logging.getLogger(__name__)


class DemoFeatureGroundingService:
    """
    Grounds extracted features against official website documentation.

    Uses OpenClaw for web grounding - never parses raw video directly.
    """

    def __init__(self, openclaw_service: Optional[OpenClawService] = None):
        """Initialize with optional OpenClaw service instance."""
        self._openclaw = openclaw_service

    def _get_openclaw(self) -> OpenClawService:
        """Get or create OpenClaw service instance."""
        if self._openclaw is None:
            self._openclaw = OpenClawService()
        return self._openclaw

    async def ground_features(
        self,
        evidence: RecordedDemoEvidenceContract,
        reference_url: str,
        *,
        project_name: Optional[str] = None,
        video_goal: Optional[str] = None,
        audience: Optional[str] = None,
        cta: Optional[str] = None,
        user_id: str = "system",
    ) -> RecordedDemoEvidenceContract:
        """
        Ground extracted features against official website.

        Args:
            evidence: RecordedDemoEvidence from Phase 4 analysis
            reference_url: Official website URL for grounding
            project_name: Project/product name if known
            video_goal: Goal of the video (feature_demo, conversion, etc.)
            audience: Target audience description
            cta: Call-to-action
            user_id: User ID for OpenClaw requests

        Returns:
            Updated evidence with grounded_features populated
        """
        logger.info(
            "Starting feature grounding: %d features against %s",
            len(evidence.extracted_features),
            reference_url,
        )

        # Store grounding context
        evidence.grounding_reference_url = reference_url
        evidence.grounding_project_name = project_name

        if not evidence.extracted_features and not evidence.feature_candidates:
            logger.info("No features to ground")
            evidence.grounding_completed = True
            return evidence

        try:
            # Build grounding context
            grounding_context = self._build_grounding_context(
                evidence=evidence,
                reference_url=reference_url,
                project_name=project_name,
                video_goal=video_goal,
                audience=audience,
                cta=cta,
            )

            # Call OpenClaw to ground features
            grounded_result = await self._call_openclaw_grounding(
                grounding_context, user_id
            )

            # Parse and validate grounding results
            grounded_features = self._parse_grounding_result(
                grounded_result, evidence.extracted_features
            )

            evidence.grounded_features = grounded_features

            # Update feature_candidates with grounded names (official names preferred)
            evidence.feature_candidates = self._update_feature_candidates(
                grounded_features, evidence.feature_candidates
            )

            # Update confidence based on grounding success
            evidence = self._update_confidence_after_grounding(evidence)

            evidence.grounding_completed = True
            logger.info(
                "Grounding complete: %d/%d features grounded",
                sum(1 for f in grounded_features if f.grounded),
                len(grounded_features),
            )

        except Exception as exc:
            logger.warning("Feature grounding failed: %s", exc)
            # Create ungrounded entries for all features
            evidence.grounded_features = [
                GroundedFeatureContract(
                    feature_id=f.feature_id,
                    original_name=f.name,
                    grounded=False,
                    grounding_confidence="low",
                    grounding_note=f"Grounding failed: {exc}",
                )
                for f in evidence.extracted_features
            ]
            evidence.grounding_completed = True
            # Don't update feature_candidates - keep OCR-derived names but mark as ungrounded

        return evidence

    def _build_grounding_context(
        self,
        evidence: RecordedDemoEvidenceContract,
        reference_url: str,
        project_name: Optional[str],
        video_goal: Optional[str],
        audience: Optional[str],
        cta: Optional[str],
    ) -> dict[str, Any]:
        """Build context dict for OpenClaw grounding request."""
        # Extract feature names and OCR evidence
        feature_names = [f.name for f in evidence.extracted_features]
        all_ocr_texts = []
        for segment in evidence.segments:
            all_ocr_texts.extend(segment.ocr_texts)

        # Build timeline summary for context
        timeline_summary = []
        for seg in evidence.segments:
            timeline_summary.append(
                {
                    "type": seg.segment_type,
                    "start": seg.start_sec,
                    "end": seg.end_sec,
                    "texts": seg.ocr_texts[:5],  # Limit for context size
                }
            )

        return {
            "reference_url": reference_url,
            "project_name": project_name or "Unknown",
            "video_goal": video_goal or "feature_demo",
            "audience": audience or "general users",
            "cta": cta or "",
            "feature_candidates": feature_names,
            "feature_candidate_count": len(feature_names),
            "ocr_evidence_sample": list(set(all_ocr_texts))[:20],
            "timeline_segments": timeline_summary[:10],
            "video_duration_sec": evidence.duration_sec,
        }

    async def _call_openclaw_grounding(
        self, context: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """Call OpenClaw to ground features against official website."""
        openclaw = self._get_openclaw()

        prompt = f"""You are verifying features detected in a demo video against official documentation.

TASK: Ground the following feature candidates against the official website at {context["reference_url"]}

Project: {context["project_name"]}
Video Goal: {context["video_goal"]}
Target Audience: {context["audience"]}

DETECTED FEATURE CANDIDATES (from OCR/video analysis):
{", ".join(context["feature_candidates"][:10])}

OCR EVIDENCE SAMPLE:
{", ".join(context["ocr_evidence_sample"][:15])}

INSTRUCTIONS:
1. Browse {context["reference_url"]} to find official feature names and descriptions
2. For each detected feature candidate, determine if it matches an official feature
3. If matched, provide the official name, description, and value proposition
4. If not matched, mark as ungrounded but keep the original name
5. Prioritize official terminology over OCR-detected text

Return JSON with this structure:
{{
  "grounded_features": [
    {{
      "original_name": "detected feature name",
      "grounded": true/false,
      "official_name": "name from website or null",
      "official_description": "description from website or null",
      "value_proposition": "why this matters to users or null",
      "source_url": "specific page URL where found or null",
      "confidence": "high/medium/low",
      "note": "explanation of grounding result"
    }}
  ],
  "project_summary": "brief description of what the product does",
  "key_value_props": ["main value proposition 1", "main value proposition 2"]
}}"""

        result = await openclaw.execute_task(
            task_type="feature_grounding",
            prompt=prompt,
            user_id=user_id,
            context=context,
        )

        return result

    def _parse_grounding_result(
        self,
        result: dict[str, Any],
        extracted_features: list[ExtractedFeatureContract],
    ) -> list[GroundedFeatureContract]:
        """Parse OpenClaw result into GroundedFeatureContract list."""
        grounded_features: list[GroundedFeatureContract] = []

        # Extract grounded_features from result
        raw_grounded = result.get("grounded_features") or result.get("result", {}).get(
            "grounded_features", []
        )

        if not isinstance(raw_grounded, list):
            raw_grounded = []

        # Build lookup for extracted features
        feature_by_name = {f.name.lower(): f for f in extracted_features}

        # Process each grounded result
        seen_ids: set[str] = set()
        for item in raw_grounded:
            if not isinstance(item, dict):
                continue

            original_name = item.get("original_name", "")
            if not original_name:
                continue

            # Find matching extracted feature
            matched_feature = feature_by_name.get(original_name.lower())
            feature_id = (
                matched_feature.feature_id
                if matched_feature
                else f"ground_{uuid4().hex[:8]}"
            )

            # Avoid duplicates
            if feature_id in seen_ids:
                continue
            seen_ids.add(feature_id)

            # Map confidence
            conf_str = str(item.get("confidence", "low")).lower()
            if conf_str not in {"high", "medium", "low"}:
                conf_str = "low"

            grounded_features.append(
                GroundedFeatureContract(
                    feature_id=feature_id,
                    original_name=original_name,
                    grounded=bool(item.get("grounded", False)),
                    official_name=item.get("official_name"),
                    official_description=item.get("official_description"),
                    value_proposition=item.get("value_proposition"),
                    source_url=item.get("source_url"),
                    grounding_confidence=conf_str,  # type: ignore
                    grounding_note=item.get("note", ""),
                )
            )

        # Add ungrounded entries for any extracted features not in result
        for feature in extracted_features:
            if feature.feature_id not in seen_ids:
                grounded_features.append(
                    GroundedFeatureContract(
                        feature_id=feature.feature_id,
                        original_name=feature.name,
                        grounded=False,
                        grounding_confidence="low",
                        grounding_note="Not found in grounding results",
                    )
                )

        return grounded_features

    def _update_feature_candidates(
        self,
        grounded_features: list[GroundedFeatureContract],
        original_candidates: list[str],
    ) -> list[str]:
        """
        Update feature_candidates with official names where available.

        Prioritizes grounded features with official names.
        """
        updated: list[str] = []

        # First add grounded features with official names
        for gf in grounded_features:
            if gf.grounded and gf.official_name:
                if gf.official_name not in updated:
                    updated.append(gf.official_name)

        # Then add high-confidence ungrounded features (user may want to keep)
        for gf in grounded_features:
            if not gf.grounded and gf.grounding_confidence == "high":
                if gf.original_name not in updated:
                    updated.append(gf.original_name)

        # Fill remaining slots from original candidates if needed
        for name in original_candidates:
            if name not in updated and len(updated) < 8:
                updated.append(name)

        return updated[:8]  # Max 8 candidates

    def _update_confidence_after_grounding(
        self, evidence: RecordedDemoEvidenceContract
    ) -> RecordedDemoEvidenceContract:
        """Update overall confidence based on grounding results."""
        grounded_count = sum(1 for f in evidence.grounded_features if f.grounded)
        total_count = len(evidence.grounded_features)

        # Update confidence signals
        evidence.confidence_signals["grounded_feature_count"] = grounded_count
        evidence.confidence_signals["total_feature_count"] = total_count
        evidence.confidence_signals["grounding_ratio"] = (
            grounded_count / total_count if total_count > 0 else 0
        )

        # Adjust overall confidence based on grounding success
        current_score = evidence.confidence_signals.get("weighted_score", 0.5)

        if total_count > 0:
            grounding_bonus = (grounded_count / total_count) * 0.2
            new_score = min(1.0, current_score + grounding_bonus)
            evidence.confidence_signals["weighted_score"] = round(new_score, 3)

            if new_score >= 0.7:
                evidence.analysis_confidence_overall = "high"
            elif new_score >= 0.4:
                evidence.analysis_confidence_overall = "medium"
            else:
                evidence.analysis_confidence_overall = "low"

        return evidence


def build_preview_summary(
    evidence: RecordedDemoEvidenceContract,
    video_goal: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a preview summary for user confirmation (Phase 5).

    Returns structured data for Telegram rendering.
    """
    # Determine what features to show
    grounded_names = [
        gf.official_name or gf.original_name
        for gf in evidence.grounded_features
        if gf.grounded
    ]
    ungrounded_names = [
        gf.original_name for gf in evidence.grounded_features if not gf.grounded
    ]

    # Build segment summary
    segment_types = [seg.segment_type for seg in evidence.segments]
    has_intro = "intro" in segment_types
    has_outro = "outro" in segment_types
    feature_demo_count = segment_types.count("feature_demo")

    # Build summary text
    summary_lines = [
        f"Duration: {evidence.duration_sec:.0f}s",
        f"Resolution: {evidence.width}x{evidence.height}",
        f"Segments: {len(evidence.segments)}",
    ]

    if has_intro:
        summary_lines.append("Has intro segment")
    if has_outro:
        summary_lines.append("Has outro segment")
    if feature_demo_count > 0:
        summary_lines.append(f"Feature demos: {feature_demo_count}")

    # Confidence indicator
    conf = evidence.analysis_confidence_overall
    conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
    summary_lines.append(f"Analysis confidence: {conf_emoji} {conf}")

    return {
        "video_info": {
            "duration_sec": evidence.duration_sec,
            "resolution": f"{evidence.width}x{evidence.height}",
            "segment_count": len(evidence.segments),
        },
        "summary_text": "\n".join(summary_lines),
        "grounded_features": grounded_names[:5],
        "ungrounded_features": ungrounded_names[:3],
        "feature_candidates": evidence.feature_candidates[:5],
        "timeline_narrative": evidence.timeline_narrative,
        "confidence": evidence.analysis_confidence_overall,
        "grounding_completed": evidence.grounding_completed,
        "suggested_video_goal": video_goal or "feature_demo",
    }
