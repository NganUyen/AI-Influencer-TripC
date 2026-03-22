"""Weekly planner skill wrapper."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("weekly-planner")


class WeeklyPlannerSkill(BaseSkill):
    name = "weekly-planner"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "POST /api/workflows/start-weekly")
    backend_status = _DEFINITION.get("status", "implemented_backing")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def _normalize_brand_config(cls, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return deepcopy(value)
        if isinstance(value, str) and value.strip():
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("brand_config must be a JSON object or JSON-encoded object.")

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
            return cls._collecting_result(
                current,
                next_step="collect_brand_config",
                output={"missing_params": missing},
            )

        try:
            brand_config = cls._normalize_brand_config(current.collected["brand_config"])
        except ValueError as exc:
            return cls._error_result(current, str(exc))

        if current.collected.get("freeform_brief"):
            brand_config = deepcopy(brand_config)
            brand_config["planning_brief"] = current.collected["freeform_brief"]

        user_id = current.collected.get("user_id") or "telegram-openclaw"
        response = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            cls._extract_path(),
            params={"user_id": user_id},
            json=brand_config,
        )

        workflow_id = response.get("workflow_id")
        current.artifacts["workflow_id"] = workflow_id
        current.artifacts["run_id"] = response.get("run_id")
        current.control.status = SkillStatus.waiting_approval
        current.control.workflow_id = workflow_id
        current.control.approval_required = True
        current.step_key = "await_approval"
        return SkillResult(
            success=True,
            next_step="poll_status",
            output={
                "workflow_id": workflow_id,
                "run_id": response.get("run_id"),
                "status": response.get("status"),
                "approval_required": True,
            },
            session=current,
        )
