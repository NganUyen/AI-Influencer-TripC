"""Quota inspection skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("quota-inspector")


class QuotaInspectorSkill(BaseSkill):
    name = "quota-inspector"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "GET /api/quota/*")
    backend_status = _DEFINITION.get("status", "implemented")
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
        provider = current.collected.get("provider")
        if provider:
            path = f"/api/quota/providers/{provider}"
        else:
            path = "/api/quota/summary"
        response = await cls._request_json(http_client, "GET", backend_url, path)

        if provider:
            current.artifacts["quota_detail"] = response
            output = {"provider": provider, "quota_detail": response}
        else:
            current.artifacts["quota_summary"] = response
            output = {"quota_summary": response}

        current.step_key = "done"
        current.control.status = SkillStatus.done
        return SkillResult(
            success=True,
            next_step="done",
            output=output,
            session=current,
        )
