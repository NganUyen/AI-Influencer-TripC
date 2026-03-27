"""Schema-first creative direction helpers for video pre-production."""

from __future__ import annotations

import json
from typing import Any, Dict

from .contracts import (
    ApprovedProductionPackageContract,
    BeatSheetContract,
    ConceptBriefContract,
)
from .openclaw_service import OpenClawService


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

    @classmethod
    def _validate_concept_quality(
        cls,
        *,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
        concept: ConceptBriefContract,
    ) -> None:
        expected_tone = str(persona_snapshot.get("tone_default") or "natural").strip() or "natural"
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
            raise ValueError(f"BeatSheet idx values must be contiguous starting at 1: {actual_idx}")

        middle_purposes = {beat.purpose for beat in beats[1:-1]}
        if not middle_purposes.intersection(
            {"problem", "solution_intro", "feature_demo", "product_positioning", "proof", "benefit"}
        ):
            raise ValueError("BeatSheet middle beats do not build toward the CTA")

        if concept_brief.access_level == "public_page_only":
            if any(beat.top_half_source_type == "authenticated_capture_later" for beat in beats):
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
    async def build_concept_brief(
        cls,
        collected: Dict[str, Any],
        persona_snapshot: Dict[str, Any],
    ) -> ConceptBriefContract:
        context = cls._prompt_context(collected=collected, persona_snapshot=persona_snapshot)
        prompt = (
            "You are the creative director for a short AI influencer video.\n"
            "Normalize the operator input into a single conservative ConceptBrief JSON object.\n"
            "Rules:\n"
            "- Output JSON only.\n"
            "- creative_input_mode must be 'idea_brief'.\n"
            "- Keep platform as the provided platform.\n"
            "- Keep video_goal exactly within: feature_demo, conversion, awareness, walkthrough.\n"
            "- Infer a short angle that matches the goal and idea.\n"
            "- source_summary must be conservative and avoid claiming product details that are not explicitly visible from the provided source context.\n"
            "- tone_resolved must prefer the provided persona tone_default, otherwise 'natural'.\n"
            "- Do not invent new fields.\n"
            "Return this exact shape:\n"
            "{\n"
            '  "persona_id": "...",\n'
            '  "creative_input_mode": "idea_brief",\n'
            '  "feature_focus": "...",\n'
            '  "video_goal": "feature_demo|conversion|awareness|walkthrough",\n'
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
            "- bottom_half_message should be concise and production-friendly.\n"
            "- top_half_target should name the source area or section to capture later, not a full storyboard.\n"
            "- top_half_capture_hint should be practical and conservative.\n"
            "- Do not repeat the full URL on every beat.\n"
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
            '      "top_half_target": "...",\n'
            '      "top_half_capture_hint": "...",\n'
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
