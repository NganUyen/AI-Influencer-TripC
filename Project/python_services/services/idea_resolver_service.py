"""
Idea Resolver Service (Phase 4a - V3.1)

Resolves the main idea from video evidence using hard precedence scoring.
Implements Fix 1 (catalog gate) and Fix 5 (feature name accessor).
"""

import logging
from typing import List, Optional, Dict

from services.contracts import (
    GroundedFeatureContract,
    OfficialFeatureCatalogContract,
    GroundingAuditContract,
    RecordedDemoEvidenceContract,
    ResolvedIdeaContract,
    TimelineStepContract,
)
from services.ai_service import AIService

logger = logging.getLogger(__name__)


class IdeaResolverService:
    """
    Resolves main idea from video evidence using hard precedence scoring.

    Precedence hierarchy:
    1. Official site/docs (highest)
    2. Video evidence (timeline steps)
    3. User thesis
    """

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    def _get_feature_display_name(self, feature: GroundedFeatureContract) -> str:
        """
        Normalized accessor for feature name (Fix 5 - V3.1).

        Returns official_name if available, otherwise original_name.
        """
        return feature.official_name or feature.original_name

    async def resolve(
        self,
        evidence: RecordedDemoEvidenceContract,
        user_video_thesis: Optional[str] = None,
        content_scope: Optional[str] = None,
    ) -> ResolvedIdeaContract:
        """
        Resolve main idea from evidence.

        Args:
            evidence: RecordedDemoEvidenceContract with all analysis data
            user_video_thesis: User's description of video
            content_scope: "single_feature"|"single_flow"|"product_overview"

        Returns:
            ResolvedIdeaContract with resolved idea or low confidence + open questions
        """
        logger.info("Starting idea resolution")

        official_catalog = evidence.official_catalog
        grounding_audit = evidence.grounding_audit
        grounded_features = evidence.grounded_features
        timeline_steps = evidence.timeline_steps or []

        # Fix 1 (V3.1): Check has_official_source_evidence
        has_official_source = bool(official_catalog and official_catalog.features)
        has_fallback_grounded = any(
            f.grounded and f.source_url for f in grounded_features
        )
        has_official_source_evidence = has_official_source or has_fallback_grounded

        if not has_official_source_evidence:
            logger.warning("No official source evidence available")
            return ResolvedIdeaContract(
                resolved_main_idea="",
                canonical_feature_focus="",
                top_half_flow=[],
                bottom_half_claim="",
                supporting_evidence=[],
                consistency_score=0.0,
                open_questions=[
                    f"Không extract được feature list từ {evidence.grounding_reference_url or 'official source'}"
                ],
                idea_confidence="low",
            )

        # Determine grounding source
        grounding_source = (
            "jina_only"
            if (grounding_audit and not grounding_audit.browser_used)
            else "mixed"
        )
        logger.info(f"Grounding source: {grounding_source}")

        # Step 2: Score candidates using hard precedence
        scored_features = self._score_candidates(
            grounded_features=grounded_features,
            official_catalog=official_catalog,
            timeline_steps=timeline_steps,
            user_video_thesis=user_video_thesis,
        )

        if not scored_features:
            return ResolvedIdeaContract(
                resolved_main_idea="",
                canonical_feature_focus="",
                top_half_flow=[],
                bottom_half_claim="",
                supporting_evidence=[],
                consistency_score=0.0,
                open_questions=["Không có feature candidates để score"],
                idea_confidence="low",
            )

        # Step 3: Select winner
        top_candidate = max(scored_features, key=lambda x: x["score"])
        top_score = top_candidate["score"]

        # Determine idea_confidence with ceiling for jina_only
        if grounding_source == "jina_only":
            idea_confidence = "medium" if top_score >= 0.5 else "low"
        elif top_score >= 0.7:
            idea_confidence = "high"
        elif top_score >= 0.5:
            idea_confidence = "medium"
        else:
            idea_confidence = "low"

        logger.info(
            f"Top candidate: {self._get_feature_display_name(top_candidate['feature'])} (score={top_score:.2f}, confidence={idea_confidence})"
        )

        # If low confidence, return early with open questions
        if idea_confidence == "low":
            return ResolvedIdeaContract(
                resolved_main_idea="",
                canonical_feature_focus=self._get_feature_display_name(
                    top_candidate["feature"]
                ),
                top_half_flow=[],
                bottom_half_claim="",
                supporting_evidence=[],
                consistency_score=top_score,
                open_questions=["Không đủ evidence để chọn feature chính"],
                idea_confidence="low",
            )

        # Step 4: Synthesize final idea using GPT-4o mini
        resolved_idea = await self._synthesize_idea(
            top_candidate=top_candidate,
            official_catalog=official_catalog,
            timeline_steps=timeline_steps,
            user_video_thesis=user_video_thesis,
        )

        resolved_idea.consistency_score = top_score
        resolved_idea.idea_confidence = idea_confidence

        logger.info(f"Idea resolved: {resolved_idea.resolved_main_idea}")
        return resolved_idea

    def _score_candidates(
        self,
        grounded_features: List[GroundedFeatureContract],
        official_catalog: Optional[OfficialFeatureCatalogContract],
        timeline_steps: List[TimelineStepContract],
        user_video_thesis: Optional[str],
    ) -> List[Dict]:
        """
        Score candidates using hard precedence (Phase 4a - V3.1).

        Returns:
            List of {feature, score} dicts
        """
        official_names = set()
        if official_catalog:
            official_names = {f.name.lower() for f in official_catalog.features}

        scored = []
        for candidate in grounded_features:
            score = 0.0
            feature_name = self._get_feature_display_name(candidate)

            # Official source (highest precedence)
            if feature_name.lower() in official_names:
                score += 0.5
            elif candidate.source_url and "://" in candidate.source_url:
                # Homepage-only source_url gets lower score
                from urllib.parse import urlparse

                parsed = urlparse(candidate.source_url)
                path = parsed.path.strip("/")
                if not path or path in ["", "index", "home"]:
                    score += 0.2  # Homepage only
                else:
                    score += 0.5  # Specific page

            # Video evidence (second precedence)
            matching_steps = []
            for step in timeline_steps:
                if step.frame_understanding:
                    if feature_name.lower() in (
                        step.frame_understanding.feature_demonstrated or ""
                    ).lower() or any(
                        feature_name.lower() in text.lower() for text in step.ocr_text
                    ):
                        matching_steps.append(step)
                elif any(
                    feature_name.lower() in text.lower() for text in step.ocr_text
                ):
                    matching_steps.append(step)

            if len(matching_steps) >= 2:
                score += 0.3
            elif len(matching_steps) == 1:
                score += 0.15

            # User thesis (third precedence)
            if user_video_thesis and feature_name.lower() in user_video_thesis.lower():
                score += 0.2

            scored.append({"feature": candidate, "score": score})

        return scored

    async def _synthesize_idea(
        self,
        top_candidate: Dict,
        official_catalog: Optional[OfficialFeatureCatalogContract],
        timeline_steps: List[TimelineStepContract],
        user_video_thesis: Optional[str],
    ) -> ResolvedIdeaContract:
        """
        Synthesize final idea using GPT-4o mini (Phase 4a - V3.1).

        Returns:
            ResolvedIdeaContract
        """
        feature = top_candidate["feature"]
        feature_name = self._get_feature_display_name(feature)

        # Build official terminology dict
        official_terminology = {}
        if official_catalog:
            official_terminology = official_catalog.official_terminology or {}

        # Build timeline summary
        timeline_summary = []
        for step in timeline_steps[:5]:  # Limit to 5 steps
            timeline_summary.append(f"{step.start_sec:.0f}s: {step.summary}")

        system_prompt = """You synthesize video demo analysis into a structured brief.
Use ONLY terminology from official_terminology dict provided.
Do not invent features not in official_catalog."""

        user_prompt = f"""Top candidate: {feature_name}
Official description: {feature.official_description or "Not available"}

Official terminology: {official_terminology}

Video steps:
{chr(10).join(timeline_summary)}

User stated: {user_video_thesis or "Not provided"}

Return JSON:
{{
  "resolved_main_idea": "one factual sentence",
  "canonical_feature_focus": "{feature_name}",
  "top_half_flow": ["step 1", "step 2", "step 3"],
  "bottom_half_claim": "one audience-facing value statement",
  "supporting_evidence": ["evidence 1", "evidence 2"]
}}"""

        try:
            response = await self.ai_service.chat_completion(
                model="gpt-4o-mini",
                system_message=system_prompt,
                user_message=user_prompt,
                temperature=0.0,
            )

            content = response.get("content", "").strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1]) if len(lines) > 2 else content

            import json

            data = json.loads(content)

            return ResolvedIdeaContract(
                resolved_main_idea=data.get("resolved_main_idea", ""),
                canonical_feature_focus=data.get(
                    "canonical_feature_focus", feature_name
                ),
                top_half_flow=data.get("top_half_flow", []),
                bottom_half_claim=data.get("bottom_half_claim", ""),
                supporting_evidence=data.get("supporting_evidence", []),
                consistency_score=0.0,  # Will be set by caller
                open_questions=[],
                idea_confidence="medium",  # Will be set by caller
            )

        except Exception as e:
            logger.warning(f"Failed to synthesize idea via GPT-4o mini: {e}")
            # Fallback to manual construction
            return ResolvedIdeaContract(
                resolved_main_idea=f"This video demonstrates {feature_name}",
                canonical_feature_focus=feature_name,
                top_half_flow=[step.summary for step in timeline_steps[:3]],
                bottom_half_claim=feature.value_proposition
                or f"Learn about {feature_name}",
                supporting_evidence=[f"Official source: {feature.source_url}"]
                if feature.source_url
                else [],
                consistency_score=0.0,
                open_questions=[],
                idea_confidence="medium",
            )
