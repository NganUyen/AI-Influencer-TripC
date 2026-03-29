"""
Script Generation Service (TripC v2 Standard)
===============================================
Wrapper trên AIService để sinh ScriptContract theo đúng schema.
Output phải vượt qua Pydantic validation trước khi vào pipeline.
"""

import json
import logging
import asyncio
from typing import Optional, Set

from services.ai_service import AIService
from services.contracts import ScriptContract, SceneContract

# [MEDIUM-3] Import valid source types for validation
_VALID_TOP_HALF_SOURCE_TYPES: Set[str] = {
    "public_page_capture",
    "authenticated_capture_later",
    "ai_visual_fallback",
    "hybrid_candidate",
    "search",  # Default fallback type
}

from services.errors import ScriptGenerationError, ScriptContractError

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
        model: str = "models/gemini-2.0-flash",
    ) -> ScriptContract:
        """
        Generate a validated ScriptContract.

        Args:
            app_name: Name of the app being promoted.
            topic: Content topic (e.g., "Da Nang beach guide").
            language: Output language for the script narration.
            voice_style: Tone description for persona style.
            market: Target market for context.
            model: AI model to use.

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
            async with AIService() as ai:
                raw = await ai.generate_text(
                    prompt=user_prompt,
                    system_prompt=SYSTEM_PROMPT,
                    model=model,
                    temperature=0.7,
                    max_tokens=2000,
                )
        except Exception as e:
            raise ScriptGenerationError(f"AI call failed: {e}") from e

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(
                lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            )

        # Parse JSON
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"AI returned non-JSON:\n{cleaned[:500]}")
            raise ScriptGenerationError(f"AI response is not valid JSON: {e}") from e

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
        model: str = "models/gemini-2.0-flash",
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
            model=model,
        )

    async def generate_script_from_package(
        self,
        app_name: str,
        package: dict,
        persona_config: dict,
        model: str = "models/gemini-2.0-flash",
    ) -> ScriptContract:
        """
        Generates a ScriptContract directly from an ApprovedProductionPackage.
        It maps Pre-Production beats directly to Top-Half Scene Contracts.
        """
        if "beat_sheet" not in package or "beats" not in package["beat_sheet"]:
            raise ValueError("Package does not contain a valid beat sheet")

        beats = package["beat_sheet"]["beats"]

        # We need to construct the script string by concatenating bottom_half_message from beats
        script_text = " ".join(
            [b.get("bottom_half_message", "") for b in beats]
        ).strip()

        # Calculate total duration from beat duration_sec fields
        duration_estimate = sum(b.get("duration_sec", 0) for b in beats)
        if duration_estimate < 10.0:
            duration_estimate = 30.0

        scenes = []
        current_timestamp = 0.0
        for index, beat in enumerate(beats, start=1):
            # [MEDIUM-3 FIX] Validate top_half_source_type against allowed set
            raw_source_type = beat.get("top_half_source_type", "search")
            if raw_source_type not in _VALID_TOP_HALF_SOURCE_TYPES:
                logger.warning(
                    "Beat %s has invalid top_half_source_type=%s — defaulting to 'ai_visual_fallback'",
                    index,
                    raw_source_type,
                )
                top_half_source_type = "ai_visual_fallback"
            else:
                top_half_source_type = raw_source_type

            top_half_target = beat.get("top_half_target", "")
            beat_duration = float(beat.get("duration_sec", 4))

            # Use bottom_half_message for narration and overlay_text for captions
            narration = beat.get("bottom_half_message", "")
            overlay_text = beat.get("overlay_text", "")

            scene = SceneContract(
                id=index,
                timestamp_start=current_timestamp,
                timestamp_end=current_timestamp + beat_duration,
                caption=overlay_text or narration[:30],
                prompt=top_half_target,
                # New fields from top-half update
                top_half_source_type=top_half_source_type,
                top_half_target=top_half_target,
                top_half_capture_hint=beat.get("top_half_capture_hint", "medium"),
                source_ref=beat.get("source_ref"),
            )

            # [CP1] Log SceneContract after build
            logger.info(
                "SceneContract built | scene=%s | top_half_type=%s | has_source_ref=%s | target=%s",
                scene.id,
                scene.top_half_source_type,
                bool(scene.source_ref),
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
