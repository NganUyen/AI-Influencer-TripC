"""Interactive Daily Story generation and routing skill."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from services.ai_service import AIService
from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

logger = logging.getLogger(__name__)

_DEFINITION = get_skill_definition("daily-story")

_STORY_PROMPT = """You are an engaging social media content creator writing a micro-story.

Brand/App to promote: {app_name}
Persona language: {language}
Topic: {topic}
Extra feedback instructions: {feedback}

Output ONLY valid JSON with exactly these keys:
{{
  "title": "<story title, max 10 words>",
  "body": "<story text, 80-200 words, hooks in first sentence>",
  "hashtags": ["<3-5 relevant hashtags without #>"]
}}

No markdown, no extra keys, ONLY the JSON object."""

class DailyStorySkill(BaseSkill):
    name = "daily-story"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = "ai_service_direct"
    backend_status = _DEFINITION.get("status", "implemented_backing")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = _DEFINITION.get("session_shape", BaseSkill.session_shape)

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)

        # 1. Collect initial fields
        if not cls._has_value(current.collected.get("persona_id")):
            return cls._collecting_result(current, next_step="pick_persona")
            
        if not cls._has_value(current.collected.get("topic")):
            return cls._collecting_result(current, next_step="collect_content")

        # 2. If user already chose a media action, handle it
        media_action = current.collected.get("media_action")
        if cls._has_value(media_action):
            action = str(media_action)
            
            if action == "cancel":
                current.control.status = SkillStatus.cancelled
                return cls._cancelled_result(current)
                
            if action == "regenerate_story":
                # Clear action to fall through to generating
                current.collected["media_action"] = None
                return cls._collecting_result(current, next_step="collect_feedback")
                
            # Otherwise it's a forward
            story_body = current.artifacts.get("story_body", current.collected.get("topic"))
            
            if action == "forward_image":
                current.control.status = SkillStatus.done
                return SkillResult(
                    success=True, status=SkillStatus.FORWARD, next_skill="image-scene",
                    initial_data={"topic_or_prompt": story_body, "persona_id": current.collected.get("persona_id")},
                    session=current
                )
            elif action == "forward_video":
                current.control.status = SkillStatus.done
                return SkillResult(
                    success=True, status=SkillStatus.FORWARD, next_skill="video-ai",
                    initial_data={"topic": story_body, "persona_id": current.collected.get("persona_id")},
                    session=current
                )
            elif action == "forward_carousel":
                current.control.status = SkillStatus.done
                return SkillResult(
                    success=True, status=SkillStatus.FORWARD, next_skill="carousel",
                    initial_data={"topic": story_body, "persona_id": current.collected.get("persona_id")},
                    session=current
                )

        # 3. If we are regenerating, make sure we have feedback first
        if current.collected.get("media_action") == "regenerate_story":
            if not cls._has_value(current.collected.get("feedback")):
                return cls._collecting_result(current, next_step="collect_feedback")

        # 4. Generate the draft
        topic = str(current.collected.get("topic", ""))
        feedback = str(current.collected.get("feedback") or "None")
        app_name = str(current.collected.get("app_name") or "the user's chosen brand/product")
        
        # Fetch persona language
        language = "English"
        persona_id = current.collected.get("persona_id")
        if persona_id:
            try:
                persona_data = await cls._request_json(
                    http_client,
                    "GET",
                    backend_url,
                    f"/api/personas/{persona_id}"
                )
                if persona_data and persona_data.get("language"):
                    language = persona_data["language"]
            except Exception as e:
                logger.warning(f"Could not fetch persona language for {persona_id}: {e}")
        
        user_prompt = _STORY_PROMPT.format(app_name=app_name, language=language, topic=topic, feedback=feedback)
        
        try:
            logger.info(f"Generating daily story draft for topic: {topic}")
            async with AIService() as ai:
                raw = await ai.generate_text(
                    prompt=user_prompt,
                    model="models/gemini-2.0-flash",
                    temperature=0.75,
                    max_tokens=800,
                )
                
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            elif cleaned.startswith("JSON"):
                 cleaned = cleaned[4:].strip()
            
            data = json.loads(cleaned)
            current.artifacts["story_draft"] = data
            current.artifacts["story_body"] = data.get("body", topic)
            
            # Clear feedback so it doesn't loop accidentally
            current.collected["feedback"] = None
            
            # Formulate the response display text
            title = data.get('title', 'Daily Story')
            body = data.get('body', '')
            tags = " ".join(f"#{t}" for t in data.get("hashtags", []))
            
            output_text = f"*{title}*\n\n{body}\n\n{tags}"
            
            # Transition to pick media
            return cls._collecting_result(current, next_step="choose_media_action", output={
                "text": output_text
            })
            
        except Exception as e:
            logger.error(f"Failed to generate story draft: {e}")
            return cls._error_result(current, f"Failed to generate story draft: {str(e)}")
