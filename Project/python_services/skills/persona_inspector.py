"""Persona inspection skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("persona-inspector")


class PersonaInspectorSkill(BaseSkill):
    name = "persona-inspector"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get(
        "target",
        "GET /api/personas + GET /api/personas/{persona_id} + GET /api/personas/{persona_id}/readiness",
    )
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    async def _list_personas(
        cls,
        backend_url: str,
        http_client: Any,
        owner_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params = {"owner_key": owner_key} if owner_key else None
        response = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            "/api/personas",
            params=params,
        )
        items = response.get("items")
        if isinstance(items, list):
            return items
        if isinstance(response, list):
            return response
        return []

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        persona_id = current.collected.get("persona_id")
        telegram_chat_id = current.artifacts.get("telegram_chat_id")
        owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None

        if not persona_id:
            personas = await cls._list_personas(backend_url, http_client, owner_key=owner_key)
            current.artifacts["available_personas"] = personas
            current.step_key = "select_persona"
            current.control.status = SkillStatus.collecting
            return SkillResult(
                success=True,
                next_step="select_persona",
                output={"available_personas": personas},
                session=current,
            )

        persona = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{persona_id}",
            params={"owner_key": owner_key} if owner_key else None,
        )
        readiness = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{persona_id}/readiness",
            params={"owner_key": owner_key} if owner_key else None,
        )
        current.artifacts["preview_image_url"] = persona.get("avatar_image_url")
        current.artifacts["persona_summary"] = {
            "persona": persona,
            "readiness": readiness,
        }
        current.step_key = "done"
        current.control.status = SkillStatus.done
        return SkillResult(
            success=True,
            next_step="done",
            output={
                "persona": persona,
                "readiness": readiness,
                "preview_image_url": persona.get("avatar_image_url"),
                "available_personas": current.artifacts.get("available_personas", []),
            },
            session=current,
        )
