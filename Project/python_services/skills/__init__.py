"""OpenClaw skill integration package."""

from .base import BaseSkill, SkillControl, SkillResult, SkillSession, SkillStatus
from .carousel import CarouselSkill
from .image_scene import ImageSceneSkill
from .long_post import LongPostSkill
from .persona_creator import PersonaCreatorSkill
from .persona_inspector import PersonaInspectorSkill
from .quota_inspector import QuotaInspectorSkill
from .video_ai import VideoAISkill
from .weekly_planner import WeeklyPlannerSkill

# Active Phase 1 skills for the current OpenClaw integration pass.
SKILL_REGISTRY = {
    "image-scene": ImageSceneSkill,
    "carousel": CarouselSkill,
    "quota-inspector": QuotaInspectorSkill,
    "persona-inspector": PersonaInspectorSkill,
    "persona-creator": PersonaCreatorSkill,
    "video-ai": VideoAISkill,
    "weekly-planner": WeeklyPlannerSkill,
}

# Backend-pending skills are documented for the Telegram layer but intentionally inactive.
STUB_SKILL_REGISTRY = {
    "long-post": LongPostSkill,
}

__all__ = [
    "BaseSkill",
    "SkillControl",
    "SkillResult",
    "SkillSession",
    "SkillStatus",
    "ImageSceneSkill",
    "QuotaInspectorSkill",
    "PersonaInspectorSkill",
    "PersonaCreatorSkill",
    "VideoAISkill",
    "WeeklyPlannerSkill",
    "CarouselSkill",
    "LongPostSkill",
    "SKILL_REGISTRY",
    "STUB_SKILL_REGISTRY",
]
