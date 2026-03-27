"""OpenClaw skill integration package."""

from .base import BaseSkill, SkillControl, SkillResult, SkillSession, SkillStatus
from .carousel import CarouselSkill
from .image_scene import ImageSceneSkill
from .image_poster import ImagePosterSkill
from .long_post import LongPostSkill
from .persona_creator import PersonaCreatorSkill
from .persona_inspector import PersonaInspectorSkill
from .publish_manager import PublishManagerSkill
from .quota_inspector import QuotaInspectorSkill
from .video_ai import VideoAISkill
from .weekly_planner import WeeklyPlannerSkill
from .daily_story import DailyStorySkill

# Active Phase 1 skills for the current OpenClaw integration pass.
SKILL_REGISTRY = {
    "image-poster": ImagePosterSkill,
    "image-scene": ImageSceneSkill,
    "carousel": CarouselSkill,
    "quota-inspector": QuotaInspectorSkill,
    "persona-inspector": PersonaInspectorSkill,
    "persona-creator": PersonaCreatorSkill,
    "publish-manager": PublishManagerSkill,
    "video-ai": VideoAISkill,
    "weekly-planner": WeeklyPlannerSkill,
    "daily-story": DailyStorySkill,
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
    "ImagePosterSkill",
    "ImageSceneSkill",
    "QuotaInspectorSkill",
    "PersonaInspectorSkill",
    "PersonaCreatorSkill",
    "PublishManagerSkill",
    "VideoAISkill",
    "WeeklyPlannerSkill",
    "DailyStorySkill",
    "CarouselSkill",
    "LongPostSkill",
    "SKILL_REGISTRY",
    "STUB_SKILL_REGISTRY",
]
