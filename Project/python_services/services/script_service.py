"""
Script Generation Service (TripC v2 Standard)
===============================================
Wrapper using OpenClaw to generate ScriptContract.
Output must pass Pydantic validation before entering pipeline.
"""

import json
import logging
import asyncio
from typing import Optional, Set

from services.openclaw_service import OpenClawService
from services.contracts import (
    ScriptContract,
    SceneContract,
    ApprovedProductionPackageContract,
    VALID_TOP_HALF_SOURCE_TYPES,
    URL_REQUIRED_SOURCE_TYPES,
)
from services.errors import ScriptGenerationError, ScriptContractError
from utils.beat_normalization import normalize_beats
from utils.json_helpers import extract_json_from_llm_response

logger = logging.getLogger(__name__)

# ─── Persona-aware prompt templates ──────────────────────────────────────────

SYSTEM_PROMPT = """You are a short-form video scriptwriter for AI influencer social media campaigns.

Output ONLY valid JSON matching this exact structure:
{
  "script": "<full narration text, max 150 words>",
  "duration_estimate": <float seconds, 30-60>,
  "scenes": [
    {
      "id": <int starting at 1>,
      "timestamp_start": <float>,
      "timestamp_end": <float>,
      "caption": "<short overlay text, max 8 words>",
      "prompt": "<fal.ai image generation prompt for this scene>"
    }
  ]
}

Rules:
- Exactly 5-8 scenes
- Scene prompts must be visual, specific, and in English
- Script must be in the persona's language
- Hook must appear in the first 5 seconds
- End with a natural CTA
- No markdown, no extra keys, ONLY the JSON object
"""

USER_TEMPLATE = """
Generate a short-form video script for:
- App/Product: {app_name}
- Topic: {topic}
- Persona language: {language}
- Persona voice style: {voice_style}
- Target market: {market}

Scenes should show app UI, features, or lifestyle moments relevant to the topic.
"""


class ScriptService:
    """
    Generates validated ScriptContract from persona + topic.
    Follows the v2 pattern: service → contract validation → pipeline.
    """

    async def generate_script(
        self,
        app_name: str,
        topic: str,
        language: str = "Vietnamese",
        voice_style: str = "friendly and energetic",
        market: str = "Vietnam",
    ) -> ScriptContract:
        """
        Generate a validated ScriptContract using OpenClaw.

        Args:
            app_name: Name of the app being promoted.
            topic: Content topic (e.g., "Da Nang beach guide").
            language: Output language for the script narration.
            voice_style: Tone description for persona style.
            market: Target market for context.

        Returns:
            ScriptContract (Pydantic-validated).

        Raises:
            ScriptGenerationError: If AI call fails or returns non-JSON.
            ScriptContractError: If JSON is valid but doesn't match schema.
        """
        user_prompt = USER_TEMPLATE.format(
            app_name=app_name,
            topic=topic,
            language=language,
            voice_style=voice_style,
            market=market,
        )

        logger.info(
            f"Generating script | app={app_name} | topic={topic} | lang={language}"
        )

        try:
            openclaw = OpenClawService()
            full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"
            result = await openclaw.execute_task(
                task_type="script_generation",
                prompt=full_prompt,
                user_id="system",
                context={"app_name": app_name, "topic": topic, "language": language},
            )
            
            # Extract JSON from OpenClaw result
            data = result if isinstance(result.get("script"), str) else result.get("result", result)
            if isinstance(data, str):
                data = extract_json_from_llm_response(data)
        except Exception as e:
            raise ScriptGenerationError(f"AI call failed: {e}") from e

        # Validate contract
        try:
            contract = ScriptContract(**data)
        except Exception as e:
            raise ScriptContractError(
                f"Script does not match ScriptContract schema: {e}"
            ) from e

        logger.info(
            f"Script generated | scenes={len(contract.scenes)} | "
            f"duration={contract.duration_estimate}s"
        )
        return contract

    async def generate_script_for_persona(
        self,
        app_name: str,
        topic: str,
        persona_config: dict,
    ) -> ScriptContract:
        """
        Convenience method: generate script using persona config directly.

        persona_config expects keys: language_name, voice, (optional) skin_color.
        """
        return await self.generate_script(
            app_name=app_name,
            topic=topic,
            language=persona_config.get("language_name", "English"),
            voice_style=f"natural, conversational, targeting {persona_config.get('language_name', 'global')} audience",
            market=persona_config.get("language_name", "Global"),
        )

    async def generate_script_from_package(
        self,
        app_name: str,
        package: dict,
        persona_config: dict,
    ) -> ScriptContract:
        """
        Generates a ScriptContract directly from an ApprovedProductionPackage.
        It maps Pre-Production beats directly to Top-Half Scene Contracts.
        """
        if "beat_sheet" not in package or "beats" not in package["beat_sheet"]:
            raise ValueError("Package does not contain a valid beat sheet")

        beats = package["beat_sheet"]["beats"]
        concept_brief = package.get("concept_brief") or {}
        default_source_ref = str(concept_brief.get("reference_url") or "").strip() or None

        # Log the default source_ref for debugging
        logger.info(
            "Generating script from package | beats=%d | default_source_ref=%s",
            len(beats),
            default_source_ref[:60] if default_source_ref else "NONE (no reference_url in concept_brief)",
        )

        # Normalize beats: backfill missing source_ref from alternative field names
        # This handles CreativeDirector using reference_url, url, page_url, etc.
        try:
            normalized_beats = normalize_beats(beats, default_source_ref)
        except ValueError as e:
            raise ScriptContractError(str(e)) from e

        # We need to construct the script string by concatenating bottom_half_message from beats
        script_text = " ".join(
            [b.get("bottom_half_message", "") for b in normalized_beats]
        ).strip()

        # Calculate total duration from beat duration_sec fields
        duration_estimate = sum(b.get("duration_sec", 0) for b in normalized_beats)
        if duration_estimate < 10.0:
            duration_estimate = 30.0

        scenes = []
        current_timestamp = 0.0
        for index, beat in enumerate(normalized_beats, start=1):
            raw_source_type = beat.get("top_half_source_type")

            # Strict, case-sensitive validation with no defaults or fallbacks.
            if not isinstance(raw_source_type, str) or not raw_source_type.strip():
                raise ValueError(
                    f"Invalid top_half_source_type {raw_source_type!r} for Beat {index}. "
                    f"Valid options are: {sorted(VALID_TOP_HALF_SOURCE_TYPES)}"
                )
            
            if raw_source_type not in VALID_TOP_HALF_SOURCE_TYPES:
                raise ValueError(
                    f"Invalid top_half_source_type {raw_source_type!r} for Beat {index}. "
                    f"Valid options are: {sorted(VALID_TOP_HALF_SOURCE_TYPES)}"
                )
            top_half_source_type = raw_source_type

            top_half_target = beat.get("top_half_target", "")
            beat_duration = float(beat.get("duration_sec", 4))
            
            # After normalization, source_ref should be present for URL-required types
            source_ref = beat.get("source_ref")

            # Final safety check (should not trigger after normalization)
            if top_half_source_type in URL_REQUIRED_SOURCE_TYPES and not source_ref:
                raise ScriptContractError(
                    f"Beat {index} type '{top_half_source_type}' requires source_ref "
                    f"but normalization failed to provide one"
                )

            # Keep captions aligned to narration to avoid top-half overlay text paths.
            narration = beat.get("bottom_half_message", "")

            scene = SceneContract(
                id=index,
                timestamp_start=current_timestamp,
                timestamp_end=current_timestamp + beat_duration,
                caption=narration[:30],
                narration_text=narration,
                prompt=top_half_target,
                # New fields from top-half update
                top_half_source_type=top_half_source_type,
                top_half_target=top_half_target,
                top_half_capture_hint=beat.get("top_half_capture_hint", "medium"),
                top_half_follow_links=bool(beat.get("top_half_follow_links", True)),
                top_half_max_capture_seconds=int(
                    beat.get("top_half_max_capture_seconds", 60)
                ),
                source_ref=source_ref,
            )

            # [CP1] Log SceneContract after build
            logger.info(
                "SceneContract built | scene=%s | top_half_type=%s | has_source_ref=%s | source_ref=%s | target=%s",
                scene.id,
                scene.top_half_source_type,
                bool(scene.source_ref),
                scene.source_ref[:60] if scene.source_ref else "NONE",
                scene.top_half_target[:50] if scene.top_half_target else "NONE",
            )

            scenes.append(scene)
            current_timestamp += beat_duration

        # Assemble the full ScriptContract
        # ScriptContract currently expects script, duration_estimate, and scenes from AI
        contract = ScriptContract(
            script=script_text, duration_estimate=duration_estimate, scenes=scenes
        )

        logger.info(
            "ScriptContract assembled from package | scenes=%s | total_duration=%.1fs",
            len(scenes),
            duration_estimate,
        )

        return contract
