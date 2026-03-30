"""
Pipeline internal contracts.
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class SceneContract(BaseModel):
    id: int
    timestamp_start: float
    timestamp_end: float
    caption: str
    narration_text: Optional[str] = None
    prompt: Optional[str] = None
    top_half_source_type: Optional[str] = None
    top_half_target: Optional[str] = None
    top_half_capture_hint: Optional[str] = None
    top_half_follow_links: Optional[bool] = None
    top_half_max_capture_seconds: Optional[int] = None
    source_ref: Optional[str] = None


class ScriptContract(BaseModel):
    script: str
    duration_estimate: float
    scenes: List[SceneContract]


class PromptMetadata(BaseModel):
    day: int = 1
    platform: str = "default"


class MediaConfig(BaseModel):
    voice: Optional[str] = None
    duration: Optional[float] = None
    fps: Optional[int] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    safety_tolerance: Optional[int] = None


class ImageInput(BaseModel):
    type: str = "image"
    prompt: str
    metadata: PromptMetadata = Field(default_factory=PromptMetadata)
    config: MediaConfig = Field(default_factory=MediaConfig)


class VideoInput(BaseModel):
    type: str = "video"
    prompt: str
    metadata: PromptMetadata = Field(default_factory=PromptMetadata)
    config: MediaConfig = Field(default_factory=MediaConfig)


class AudioInput(BaseModel):
    type: str = "audio"
    script: str
    metadata: PromptMetadata = Field(default_factory=PromptMetadata)
    config: MediaConfig = Field(default_factory=MediaConfig)


class SplitScreenVideoInput(BaseModel):
    image_urls: List[str]
    audio_url: str
    talking_head_url: Optional[str] = None
    subtitle_script: str = ""
    subtitle_segments: List[Dict[str, Any]] = Field(default_factory=list)
    scene_durations: List[float] = Field(default_factory=list)
    # [SAFETY-4] Explicit is_video flags from top-half generation
    is_video_flags: List[bool] = Field(default_factory=list)
    persona_id: str = "unknown"
    topic: str = "topic"
    duration_per_image: float = 4.0


class ImageContract(BaseModel):
    type: str = "image"
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    model: str
    prompt: str
    scene_id: Optional[int] = None


class AudioContract(BaseModel):
    type: str = "audio"
    url: str
    voice: str
    duration: Optional[float] = None


class TalkingHeadContract(BaseModel):
    type: str = "talking_head_video"
    url: str
    avatar_id: str
    heygen_video_id: str
    duration: Optional[float] = None
    status: str = "completed"


class VideoArtifact(BaseModel):
    type: str = "video"
    url: str
    storage_key: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    preview_url: Optional[str] = None
    duration: Optional[float] = None
    resolution: str = "1080x1920"
    persona_id: Optional[str] = None
    topic: Optional[str] = None


class FinalVideoContract(BaseModel):
    type: str = "video"
    url: Optional[str] = None
    video_url: str
    preview_url: Optional[str] = None
    storage_key: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    duration: Optional[float] = None
    resolution: str = "1080x1920"
    persona_id: Optional[str] = None
    topic: Optional[str] = None


class CarouselSlideContract(BaseModel):
    slide_num: int
    image_prompt: str
    caption: str
    cta_overlay: Optional[str] = None
    image_url: str
    source_image_url: Optional[str] = None
    storage_key: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CarouselArtifact(BaseModel):
    type: str = "carousel"
    app_name: str
    topic: str
    platform: str
    persona_id: Optional[str] = None
    slides: List[CarouselSlideContract]
    platform_caption: str
    hashtags: List[str] = Field(default_factory=list)
    status: str = "completed"
    metadata: Dict[str, Any] = Field(default_factory=dict)


_VIDEO_GOALS = {
    "feature_demo",
    "conversion",
    "awareness",
    "walkthrough",
}
_ACCESS_LEVELS = {
    "public_page_only",
    "has_logged_in_access",
    "login_required_but_not_available",
    "unknown",
}
_BEAT_PURPOSES = {
    "hook",
    "problem",
    "solution_intro",
    "feature_demo",
    "product_positioning",
    "proof",
    "benefit",
    "expectation_setting",
    "cta",
}
_TOP_HALF_SOURCE_TYPES = {
    "public_page_capture",
    "authenticated_capture_later",
    "ai_visual_fallback",
    "hybrid_candidate",
}


class ConceptBriefContract(BaseModel):
    persona_id: str
    creative_input_mode: Literal["idea_brief"] = "idea_brief"
    feature_focus: str
    video_goal: str
    audience: str
    angle: str
    platform: str = "tiktok"
    cta: str
    reference_url: str
    access_level: str
    source_summary: str
    tone_resolved: str

    @field_validator("video_goal")
    @classmethod
    def validate_video_goal(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in _VIDEO_GOALS:
            raise ValueError(f"Unsupported video_goal: {value}")
        return normalized

    @field_validator("access_level")
    @classmethod
    def validate_access_level(cls, value: str) -> str:
        normalized = str(value).strip()
        if normalized not in _ACCESS_LEVELS:
            raise ValueError(f"Unsupported access_level: {value}")
        return normalized

    @field_validator("reference_url")
    @classmethod
    def validate_reference_url(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("reference_url must start with http:// or https://")
        return normalized


class BeatContract(BaseModel):
    idx: int
    purpose: str
    bottom_half_message: str
    top_half_source_type: str
    top_half_target: str
    top_half_capture_hint: str
    top_half_follow_links: Optional[bool] = True
    top_half_max_capture_seconds: Optional[int] = 60
    source_ref: Optional[str] = None
    overlay_text: str
    duration_sec: int

    @field_validator("purpose")
    @classmethod
    def validate_purpose(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in _BEAT_PURPOSES:
            raise ValueError(f"Unsupported beat purpose: {value}")
        return normalized

    @field_validator("top_half_source_type")
    @classmethod
    def validate_top_half_source_type(cls, value: str) -> str:
        normalized = str(value).strip()
        if normalized not in _TOP_HALF_SOURCE_TYPES:
            raise ValueError(f"Unsupported top_half_source_type: {value}")
        return normalized

    @field_validator("duration_sec")
    @classmethod
    def validate_duration_sec(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("duration_sec must be positive")
        return value

    @field_validator("top_half_max_capture_seconds")
    @classmethod
    def validate_top_half_max_capture_seconds(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 8 or value > 60:
            raise ValueError("top_half_max_capture_seconds must be between 8 and 60")
        return value


class BeatSheetContract(BaseModel):
    concept_id: str = Field(default_factory=lambda: f"concept_{uuid4().hex[:8]}")
    beats: List[BeatContract]

    @model_validator(mode="after")
    def validate_beat_count(self) -> "BeatSheetContract":
        if len(self.beats) not in {5, 6}:
            raise ValueError(
                "BeatSheet must contain 5 beats by default, or 6 for complex demos"
            )
        return self


class ApprovedProductionPackageContract(BaseModel):
    concept_brief: ConceptBriefContract
    beat_sheet: BeatSheetContract
    persona_snapshot: Dict[str, Any] = Field(default_factory=dict)


class VideoWorkflowPersonaSnapshotContract(BaseModel):
    language: str = "English"
    tts_voice: str
    heygen_avatar_id: Optional[str] = None
    display_name: Optional[str] = None


class VideoWorkflowStartPayloadContract(BaseModel):
    persona_id: str
    topic: str
    tone: str = "natural"
    platform: str = "tiktok"
    telegram_chat_id: Optional[str] = None
    user_id: Optional[str] = None
    owner_key: Optional[str] = None
    talking_head_optional: bool = False
    approved_package: Optional[ApprovedProductionPackageContract] = None
    persona_snapshot: VideoWorkflowPersonaSnapshotContract
