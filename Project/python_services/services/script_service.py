"""
Script Generation Service (TripC v2 Standard)
===============================================
Wrapper trên AIService để sinh ScriptContract theo đúng schema.
Output phải vượt qua Pydantic validation trước khi vào pipeline.
"""

import json
import logging
import asyncio
from typing import Optional

from services.ai_service import AIService
from services.contracts import ScriptContract, SceneContract
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

        logger.info(f"Generating script | app={app_name} | topic={topic} | lang={language}")

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
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

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
            raise ScriptContractError(f"Script does not match ScriptContract schema: {e}") from e

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
