"""Image scene skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("image-scene")


class ImageSceneSkill(BaseSkill):
    name = "image-scene"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "POST /api/media/generate/image")
    backend_status = _DEFINITION.get("status", "implemented")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def _build_prompt(cls, collected: Dict[str, Any]) -> str:
        lines = [str(collected["topic_or_prompt"]).strip()]
        if collected.get("scene_type"):
            lines.append(f"Scene type: {collected['scene_type']}")
        if collected.get("style"):
            lines.append(f"Style: {collected['style']}")
        if collected.get("persona_id"):
            lines.append(f"Persona reference: {collected['persona_id']}")
        if collected.get("freeform_brief"):
            lines.append(f"Brief: {collected['freeform_brief']}")
        if collected.get("creative_notes"):
            lines.append(f"Creative notes: {collected['creative_notes']}")
        return "\n".join(lines)

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        missing = cls._missing_required_params(current)
        if missing:
            if "topic_or_prompt" in missing:
                next_step = "collect_prompt"
            elif "style" in missing:
                next_step = "choose_style"
            else:
                next_step = "choose_ratio"

            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        if current.artifacts.get("preview_image_url"):
            current.step_key = "done"
            current.control.status = SkillStatus.done
            return SkillResult(
                success=True,
                next_step="done",
                output={
                    "image_url": current.artifacts.get("final_image_url")
                    or current.artifacts.get("preview_image_url"),
                    "storage_key": current.artifacts.get("storage_key"),
                },
                session=current,
            )

        payload = {
            "prompt": cls._build_prompt(current.collected),
            "aspect_ratio": current.collected.get("aspect_ratio") or "16:9",
        }
        response = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            cls._extract_path(),
            json=payload,
        )
        image_url = response.get("url")
        if not image_url:
            return cls._error_result(current, "Image endpoint returned no URL.")

        current.artifacts["preview_image_url"] = image_url
        current.artifacts["final_image_url"] = image_url
        current.step_key = "confirm_or_regenerate"
        current.control.status = SkillStatus.preview_ready
        return SkillResult(
            success=True,
            next_step="confirm_or_regenerate",
            output={
                "preview_image_url": image_url,
                "model": response.get("model"),
                "prompt": response.get("prompt"),
            },
            session=current,
        )
