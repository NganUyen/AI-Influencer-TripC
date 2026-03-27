"""Carousel skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("carousel")


class CarouselSkill(BaseSkill):
    name = "carousel"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "POST /api/media/carousel")
    backend_status = _DEFINITION.get("status", "implemented_backing")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        if current.artifacts.get("carousel_artifact"):
            current.step_key = "done"
            current.control.status = SkillStatus.done
            return SkillResult(
                success=True,
                next_step="done",
                output=current.artifacts["carousel_artifact"],
                session=current,
            )

        missing = cls._missing_required_params(current)
        if missing:
            next_step = "pick_persona"
            if "topic" in missing:
                next_step = "collect_topic"
            elif "platform" in missing:
                next_step = "choose_platform"
            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        payload = {
            "topic": current.collected["topic"],
            "platform": current.collected["platform"],
        }
        optional_map = (
            "persona_id",
            "tone",
            "num_slides",
            "freeform_brief",
            "creative_notes",
        )
        for field in optional_map:
            value = current.collected.get(field)
            if cls._has_value(value):
                payload[field] = value

        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        if telegram_chat_id:
            payload["owner_key"] = f"telegram:{telegram_chat_id}"

        artifact = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            cls._extract_path(),
            json=payload,
        )
        slides = artifact.get("slides") or []
        current.artifacts["slides_json"] = slides
        current.artifacts["image_urls"] = [
            slide.get("image_url") for slide in slides if slide.get("image_url")
        ]
        current.artifacts["storage_keys"] = [
            slide.get("storage_key") for slide in slides if slide.get("storage_key")
        ]
        current.artifacts["manifest_url"] = artifact.get("manifest_url")
        current.artifacts["carousel_artifact"] = artifact
        current.step_key = "preview"
        current.control.status = SkillStatus.preview_ready
        return SkillResult(
            success=True,
            next_step="preview",
            output=artifact,
            session=current,
        )
