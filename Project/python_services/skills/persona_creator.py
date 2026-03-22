"""Persona creation skill wrapper."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("persona-creator")


class PersonaCreatorSkill(BaseSkill):
    name = "persona-creator"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get(
        "target",
        "POST /api/personas + PATCH /api/personas/{persona_id} + GET /api/personas/{persona_id}/readiness",
    )
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def _display_name_from_persona_id(cls, persona_id: str) -> str:
        parts = [part for part in re.split(r"[_-]+", persona_id.strip()) if part]
        if not parts:
            return persona_id
        return " ".join(part.capitalize() for part in parts)

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
            next_step = current.step_key or "collect_persona_id"
            if "persona_id" in missing:
                next_step = "collect_persona_id"
            elif "language" in missing:
                next_step = "choose_language"
            elif "voice" in missing:
                next_step = "choose_voice"
            elif "appearance_prompt_or_photo" in missing:
                next_step = "collect_appearance"
            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        payload = {
            "persona_id": current.collected["persona_id"],
            "display_name": cls._display_name_from_persona_id(current.collected["persona_id"]),
            "language": current.collected["language"],
            "tts_voice": current.collected["voice"],
            "avatar_prompt": current.collected["appearance_prompt_or_photo"],
        }
        persona = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            "/api/personas",
            json=payload,
        )
        readiness = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{current.collected['persona_id']}/readiness",
        )

        current.artifacts["preview_image_url"] = persona.get("avatar_image_url")
        current.artifacts["avatar_image_url"] = persona.get("avatar_image_url")
        current.artifacts["heygen_avatar_id"] = persona.get("heygen_avatar_id")
        current.step_key = "done"
        current.control.status = SkillStatus.done
        return SkillResult(
            success=True,
            next_step="done",
            output={
                "persona": persona,
                "readiness": readiness,
                "backend_status": cls.backend_status,
                "note": (
                    "Persona CRUD/readiness is available, but avatar generation and "
                    "HeyGen registration still need router-layer orchestration."
                ),
            },
            session=current,
        )
