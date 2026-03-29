"""
Media API Routes
Endpoints for media generation and management
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.security import require_internal_api_token
from services import FalAIService, GoogleTTSService, ImageGenerationService, StorageService
from services.carousel_service import CarouselService

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


class ImageGenerateRequest(BaseModel):
    prompt: str
    model: str = "fal-ai/nano-banana-2"
    aspect_ratio: str = "16:9"
    num_images: int = Field(default=1, ge=1, le=8)
    safety_tolerance: int = Field(default=2, ge=1, le=6)
    user_id: Optional[str] = None
    owner_key: Optional[str] = None
    persona_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class VideoGenerateRequest(BaseModel):
    prompt: str
    duration: int = 5

class AudioGenerateRequest(BaseModel):
    text: str
    voice: str = "vi-VN-Wavenet-D"  # Default to friendly male voice ("Minh")
    speaking_rate: float = 1.05     # Slightly faster, natural pacing
    pitch: float = 0.0              # Standard pitch


class CarouselGenerateRequest(BaseModel):
    topic: str
    app_name: str = "TripC"
    platform: str = "instagram"
    persona_id: Optional[str] = None
    tone: Optional[str] = None
    style: Optional[str] = None
    num_slides: int = Field(default=8, ge=2, le=12)
    aspect_ratio: str = "4:5"
    image_model: str = "fal-ai/nano-banana-2"
    planning_model: str = "models/gemini-2.0-flash"
    safety_tolerance: int = Field(default=2, ge=1, le=6)
    freeform_brief: Optional[str] = None
    creative_notes: Optional[str] = None
    language: Optional[str] = None
    skin_color: Optional[str] = None
    include_text_overlay: bool = True
    user_id: Optional[str] = None
    owner_key: Optional[str] = None


@router.post("/generate/image")
async def generate_image(request: ImageGenerateRequest):
    """Generate an image using fal.ai"""
    service = ImageGenerationService()
    try:
        return await service.generate_images(
            prompt=request.prompt,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            safety_tolerance=request.safety_tolerance,
            num_images=request.num_images,
            user_id=request.user_id,
            owner_key=request.owner_key,
            persona_id=request.persona_id,
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await service.close()


@router.post("/generate/video")
async def generate_video(request: VideoGenerateRequest):
    """Generate a video using fal.ai"""
    try:
        fal_service = FalAIService()

        result = await fal_service.generate_video(prompt=request.prompt, duration=request.duration)

        return result

    except Exception as e:
        logger.error(f"Video generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/audio")
async def generate_audio(request: AudioGenerateRequest):
    """Generate audio using Google Cloud TTS (Vietnamese Wavenet voices)"""
    try:
        tts_service = GoogleTTSService()
        resolver = getattr(tts_service, "resolve_voice_name", None)
        resolved_voice = resolver(request.voice) if callable(resolver) else request.voice

        audio_bytes = await tts_service.generate_audio(
            text=request.text,
            voice=resolved_voice,
            speaking_rate=request.speaking_rate,
            pitch=request.pitch,
        )

        return {
            "status": "success",
            "audio_bytes_length": len(audio_bytes),
            "voice": resolved_voice,
            "text_length": len(request.text),
            "note": "Audio bytes available for download or further processing",
        }

    except Exception as e:
        logger.error(f"Audio generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def list_voices():
    """List available Vietnamese voices from Google Cloud TTS"""
    try:
        tts_service = GoogleTTSService()

        voices = tts_service.get_voices()

        return {
            "status": "success",
            "voices": voices,
            "default_voice": "vi-VN-Wavenet-D",
            "note": "Voice presets map to provider voices; aliases are normalized automatically."
        }

    except Exception as e:
        logger.error(f"Failed to list voices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage/list")
async def list_storage_files(prefix: str = ""):
    """List files in the configured object storage backend."""
    try:
        storage_service = StorageService()

        files = await storage_service.list_files(prefix=prefix)

        return {"files": files}

    except Exception as e:
        logger.error(f"Failed to list files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/carousel")
async def generate_carousel(request: CarouselGenerateRequest):
    """Generate a full carousel artifact with slide images and text overlays."""
    try:
        service = CarouselService()
        return await service.generate_carousel(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Carousel generation failed: {str(exc)}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
