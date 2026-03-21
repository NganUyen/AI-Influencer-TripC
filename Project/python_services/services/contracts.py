"""
Pipeline internal contracts.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SceneContract(BaseModel):
    id: int
    timestamp_start: float
    timestamp_end: float
    caption: str
    prompt: str


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
    scene_captions: List[str] = Field(default_factory=list)
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
