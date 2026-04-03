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
    "walkthrough",
    # Deprecated: "awareness" - auto-migrated to "feature_demo" for backward compatibility
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
# Single source of truth for valid top_half_source_type values
# Used across: script_service, creative_director_service, media_activities
#
# Source Type Behavior Matrix:
# ┌─────────────────────────────┬──────────────┬───────────────────────────────────────────┐
# │ source_type                 │ has_source_ref │ Behavior                                │
# ├─────────────────────────────┼──────────────┼───────────────────────────────────────────┤
# │ public_page_capture         │ Yes          │ Browser capture, ERROR on fail           │
# │ public_page_capture         │ No           │ ERROR (non-retryable)                    │
# │ hybrid_candidate            │ Yes          │ Browser capture, AI FALLBACK on fail     │
# │ hybrid_candidate            │ No           │ AI visual directly (no browser attempt)  │
# │ ai_visual_fallback          │ *            │ AI visual directly                       │
# │ uploaded_demo_video         │ Yes          │ Extract segment from demo video          │
# │ uploaded_demo_video         │ No           │ ERROR (non-retryable)                    │
# │ authenticated_capture_later │ Yes          │ Browser capture, ERROR on fail           │
# │ authenticated_capture_later │ No           │ ERROR (non-retryable)                    │
# └─────────────────────────────┴──────────────┴───────────────────────────────────────────┘
VALID_TOP_HALF_SOURCE_TYPES = {
    "public_page_capture",         # Browser capture required, no fallback
    "authenticated_capture_later", # Browser capture required (with auth), no fallback  
    "ai_visual_fallback",          # Pure AI generation
    "hybrid_candidate",            # Browser capture with AI fallback on failure
    "uploaded_demo_video",         # Extract from uploaded video file
}

# Backward compatibility alias
_TOP_HALF_SOURCE_TYPES = VALID_TOP_HALF_SOURCE_TYPES
_VALID_TOP_HALF_SOURCE_TYPES = VALID_TOP_HALF_SOURCE_TYPES

# Source types that REQUIRE a URL but support fallback if it fails
URL_REQUIRED_SOURCE_TYPES = {
    "public_page_capture",         # Strict: must have URL, fails if capture fails
    "authenticated_capture_later", # Strict: must have URL, fails if capture fails
}

# Source types that benefit from URL but can fall back to AI
URL_OPTIONAL_WITH_FALLBACK_TYPES = {
    "hybrid_candidate",  # Uses URL if present, falls back to AI on failure or missing URL
}


# ==============================================================================
# Recorded Demo Video Analysis Contracts (Phase 4)
# ==============================================================================


class KeyframeContract(BaseModel):
    """A single keyframe extracted from demo video."""

    frame_id: str
    timestamp_sec: float
    image_path: Optional[str] = None  # Local temp path during analysis
    image_url: Optional[str] = None  # Storage URL after upload (optional)


class TimelineSegmentContract(BaseModel):
    """A logical segment of the demo video timeline."""

    segment_id: str
    start_sec: float
    end_sec: float
    segment_type: Literal["intro", "feature_demo", "transition", "outro", "unknown"] = (
        "unknown"
    )
    description: str = ""
    keyframe_ids: List[str] = Field(default_factory=list)
    ocr_texts: List[str] = Field(default_factory=list)


class ExtractedFeatureContract(BaseModel):
    """A feature detected in the demo video via OCR/analysis."""

    feature_id: str
    name: str
    description: str = ""
    timestamp_start_sec: float
    timestamp_end_sec: float
    confidence: Literal["high", "medium", "low"] = "medium"
    ocr_evidence: List[str] = Field(default_factory=list)
    keyframe_ids: List[str] = Field(default_factory=list)


class GroundedFeatureContract(BaseModel):
    """
    A feature after OpenClaw grounding against official sources (Phase 5).

    Source-of-truth priority:
    1. official site/docs (grounded=True)
    2. user confirmation
    3. video evidence
    4. model inference (grounded=False)
    """

    feature_id: str  # Reference to ExtractedFeatureContract
    original_name: str  # Name from OCR/analysis
    grounded: bool = False  # True if verified against official source
    official_name: Optional[str] = None  # Corrected name from official docs
    official_description: Optional[str] = None  # Description from official source
    value_proposition: Optional[str] = None  # Why this feature matters
    source_url: Optional[str] = None  # URL where verified
    grounding_confidence: Literal["high", "medium", "low"] = "low"
    grounding_note: str = ""  # Explanation of grounding result


class RecordedDemoEvidenceContract(BaseModel):
    """
    Evidence extracted from uploaded demo video (Phase 4-5).

    This is the internal analysis output contract.
    Kept separate from ConceptBrief until Phase 6 integration.

    Structured data (segments, keyframes, features) is separate from
    human-readable summaries (timeline_narrative, feature_candidates).
    """

    # Source video info
    demo_video_asset_url: str
    original_filename: str = ""
    duration_sec: float
    width: int
    height: int

    # Extracted keyframes (representative, not all frames)
    keyframes: List[KeyframeContract] = Field(default_factory=list)

    # Timeline segmentation
    segments: List[TimelineSegmentContract] = Field(default_factory=list)

    # Extracted features from OCR and analysis (Phase 4)
    extracted_features: List[ExtractedFeatureContract] = Field(default_factory=list)

    # Grounded features after OpenClaw verification (Phase 5)
    grounded_features: List[GroundedFeatureContract] = Field(default_factory=list)

    # Summary outputs for downstream phases (Phase 5+)
    # Note: segments (above) contain structured timeline data
    # timeline_narrative is human-readable text for preview/debugging
    timeline_narrative: str = ""  # Human-readable summary of timeline flow
    feature_candidates: List[str] = Field(
        default_factory=list
    )  # Top feature names to highlight (updated after grounding)

    # Grounding metadata (Phase 5)
    grounding_reference_url: Optional[str] = None  # URL used for grounding
    grounding_project_name: Optional[str] = None  # Project name if provided
    grounding_completed: bool = False  # Whether grounding step has run

    # Confidence scoring
    analysis_confidence_overall: Literal["high", "medium", "low"] = "low"
    confidence_signals: Dict[str, Any] = Field(default_factory=dict)  # Debug/audit info

    # Analysis metadata
    analysis_version: str = "1.0"
    ocr_enabled: bool = False
    vision_model_used: Optional[str] = None  # None if OCR-only fallback


# ==============================================================================
# ConceptBrief and related contracts
# ==============================================================================


class ConceptBriefContract(BaseModel):
    persona_id: str
    creative_input_mode: Literal["idea_brief", "recorded_demo_video"] = "idea_brief"
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

    # Optional fields for recorded_demo_video mode (Phase 2-3)
    demo_video_telegram_file_id: Optional[str] = None
    demo_video_asset_url: Optional[str] = None

    # Note: demo_evidence integration deferred to Phase 6 (ConceptBrief generation changes)
    # For now, evidence is stored in session artifacts, not in ConceptBrief

    @field_validator("video_goal")
    @classmethod
    def validate_video_goal(cls, value: str) -> str:
        normalized = str(value).strip().lower()

        # Backward compatibility: auto-migrate "awareness" to "feature_demo"
        if normalized == "awareness":
            import logging

            logging.warning(
                "video_goal='awareness' is deprecated and auto-migrated to 'feature_demo'. "
                "Please update to use one of: feature_demo, walkthrough, conversion"
            )
            return "feature_demo"

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
    trim_confidence: Optional[float] = None

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
    def validate_top_half_max_capture_seconds(
        cls, value: Optional[int]
    ) -> Optional[int]:
        if value is None:
            return None
        if value < 8 or value > 60:
            raise ValueError("top_half_max_capture_seconds must be between 8 and 60")
        return value

    @field_validator("trim_confidence")
    @classmethod
    def validate_trim_confidence(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if value < 0 or value > 1:
            raise ValueError("trim_confidence must be between 0 and 1")
        return round(float(value), 3)


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
