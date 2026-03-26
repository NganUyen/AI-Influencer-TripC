"""Marketing poster skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("image-poster")


class ImagePosterSkill(BaseSkill):
    name = "image-poster"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "POST /api/media/generate/image")
    backend_status = _DEFINITION.get("status", "implemented_backing")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def _build_prompt(cls, collected: Dict[str, Any]) -> str:
        app_name = collected.get("app_name") or "TripC"
        lines = [
            f"Create a premium marketing poster for {app_name}.",
            f"Core brief: {str(collected['topic_or_brief']).strip()}",
            f"Style: {collected.get('style') or 'clean'}",
            f"Tone: {collected.get('tone') or 'premium'}",
            "Layout: bold focal point, clean spacing, marketing-ready composition.",
        ]
        if collected.get("cta_text"):
            lines.append(f"CTA text: {collected['cta_text']}")
        if collected.get("freeform_brief"):
            lines.append(f"Extra brief: {collected['freeform_brief']}")
        if collected.get("creative_notes"):
            lines.append(f"Creative notes: {collected['creative_notes']}")
        return "\n".join(lines)

    @classmethod
    def _done_output(cls, session: SkillSession) -> Dict[str, Any]:
        return {
            "image_url": session.artifacts.get("final_image_url"),
            "storage_key": session.artifacts.get("storage_key"),
            "preview_image_url": session.artifacts.get("preview_image_url"),
            "prompt": session.artifacts.get("poster_prompt"),
            "style": session.collected.get("style"),
            "tone": session.collected.get("tone"),
        }

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)

        if not cls._has_value(current.collected.get("topic_or_brief")):
            return cls._collecting_result(current, next_step="collect_brief")
        if not cls._has_value(current.collected.get("style")):
            return cls._collecting_result(current, next_step="choose_style")
        if not cls._has_value(current.collected.get("tone")):
            return cls._collecting_result(current, next_step="choose_tone")

        if current.artifacts.get("final_image_url"):
            current.step_key = "done"
            current.control.status = SkillStatus.done
            return SkillResult(
                success=True,
                next_step="done",
                output=cls._done_output(current),
                session=current,
            )

        generated_image = current.artifacts.get("generated_image")
        if generated_image:
            current.artifacts["final_image_url"] = generated_image.get("url")
            current.artifacts["storage_key"] = generated_image.get("storage_key")
            current.step_key = "done"
            current.control.status = SkillStatus.done
            return SkillResult(
                success=True,
                next_step="done",
                output=cls._done_output(current),
                session=current,
            )

        prompt = cls._build_prompt(current.collected)
        response = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            cls._extract_path(),
            json={
                "prompt": prompt,
                "aspect_ratio": current.collected.get("aspect_ratio") or "4:5",
            },
        )
        image_url = response.get("url")
        if not image_url:
            return cls._error_result(current, "Poster generation failed. Please try again.")

        generated_image = {
            "url": image_url,
            "storage_key": response.get("storage_key"),
            "model": response.get("model"),
            "prompt": response.get("prompt") or prompt,
        }
        current.artifacts["generated_image"] = generated_image
        current.artifacts["preview_image_url"] = image_url
        current.artifacts["poster_prompt"] = generated_image["prompt"]
        current.step_key = "confirm_or_regenerate"
        current.control.status = SkillStatus.preview_ready

        return SkillResult(
            success=True,
            next_step="confirm_or_regenerate",
            output={
                "preview_image_url": image_url,
                "image_url": image_url,
                "storage_key": generated_image.get("storage_key"),
                "prompt": generated_image["prompt"],
                "style": current.collected.get("style"),
                "tone": current.collected.get("tone"),
            },
            session=current,
        )
