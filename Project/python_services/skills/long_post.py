"""Long-post skill stub."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession


class LongPostSkill(BaseSkill):
    name = "long-post"
    required_params = ["topic", "platform"]
    optional_params = ["persona_id", "tone", "freeform_brief", "creative_notes"]
    backend_status = "BACKEND_PENDING"
    api_target = "POST /api/media/long-post"

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        return SkillResult(
            success=False,
            error="Backend endpoint not yet available: POST /api/media/long-post",
            session=current,
        )
