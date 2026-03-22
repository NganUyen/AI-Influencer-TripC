"""Carousel skill stub."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseSkill, SkillResult, SkillSession


class CarouselSkill(BaseSkill):
    name = "carousel"
    required_params = ["topic", "platform"]
    optional_params = ["persona_id", "tone", "num_slides", "freeform_brief", "creative_notes"]
    backend_status = "BACKEND_PENDING"
    api_target = "POST /api/media/carousel"

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
            error="Backend endpoint not yet available: POST /api/media/carousel",
            session=current,
        )
