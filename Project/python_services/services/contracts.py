"""
Pipeline Internal Contracts (TripC v2 Standard)
=================================================
Tất cả các "contract" nội bộ được khóa tại đây.
Mọi service và activity PHẢI trả về đúng cấu trúc này.
"""
from typing import Optional, List
from pydantic import BaseModel, Field


# ─── Scene Contract ───────────────────────────────────────────────────────────

class SceneContract(BaseModel):
    """Một phân cảnh trong kịch bản video."""
    id: int
    timestamp_start: float  # seconds
    timestamp_end: float    # seconds
    caption: str
    prompt: str             # Visual prompt for fal.ai


# ─── Script Contract ─────────────────────────────────────────────────────────

class ScriptContract(BaseModel):
    """Output từ AIService.generate_script(). Phải validate trước khi đưa vào pipeline."""
    script: str
    duration_estimate: float  # Total video duration in seconds
    scenes: List[SceneContract]


# ─── Image Contract ───────────────────────────────────────────────────────────

class ImageContract(BaseModel):
    """Output từ FalAIService.generate_image()."""
    type: str = "image"
    url: str
    width: Optional[int] = None
    height: Optional[int] = None
    model: str
    prompt: str
    scene_id: Optional[int] = None  # Which scene this image belongs to


# ─── Audio Contract ───────────────────────────────────────────────────────────

class AudioContract(BaseModel):
    """Output từ GoogleTTSService.synthesize()."""
    type: str = "audio"
    url: str           # R2 public URL
    voice: str         # e.g. vi-VN-Wavenet-C
    duration: Optional[float] = None  # seconds


# ─── Talking Head Contract ────────────────────────────────────────────────────

class TalkingHeadContract(BaseModel):
    """Output từ HeyGenService.create_video()."""
    type: str = "talking_head_video"
    url: str
    avatar_id: str
    heygen_video_id: str
    duration: Optional[float] = None
    status: str = "completed"


# ─── Final Output Contract ────────────────────────────────────────────────────

class FinalVideoContract(BaseModel):
    """Output từ video assembly activity."""
    video_url: str
    preview_url: Optional[str] = None
    storage_key: str
    duration: Optional[float] = None
    resolution: str = "1080x1920"
    persona_id: Optional[str] = None
    topic: Optional[str] = None
