"""AI influencer video skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("video-ai")


class VideoAISkill(BaseSkill):
    name = "video-ai"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "POST /api/workflows/start-video")
    backend_status = _DEFINITION.get("status", "implemented_backing")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def _composite_topic(cls, collected: Dict[str, Any]) -> str:
        lines = [str(collected["topic"]).strip()]
        if collected.get("hook_idea"):
            lines.append(f"Hook idea: {collected['hook_idea']}")
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
            next_step = "pick_persona"
            if "topic" in missing:
                next_step = "collect_topic"
            elif "tone" in missing:
                next_step = "choose_tone"
            return cls._collecting_result(
                current,
                next_step=next_step,
                output={"missing_params": missing},
            )

        readiness = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{current.collected['persona_id']}/readiness",
        )
        if not readiness.get("ready"):
            return cls._error_result(
                current,
                readiness.get("blocking_reason") or "Selected persona is not ready.",
            )

        payload = {
            "persona_id": current.collected["persona_id"],
            "topic": cls._composite_topic(current.collected),
            "tone": current.collected["tone"],
            "platform": current.collected.get("platform") or "tiktok",
        }
        response = await cls._request_json(
            http_client,
            "POST",
            backend_url,
            cls._extract_path(),
            json=payload,
        )

        workflow_id = response.get("workflow_id")
        current.artifacts["workflow_id"] = workflow_id
        current.artifacts["run_id"] = response.get("run_id")
        current.control.status = SkillStatus.waiting_approval
        current.control.workflow_id = workflow_id
        current.control.approval_required = True
        current.step_key = "approve_video"
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
