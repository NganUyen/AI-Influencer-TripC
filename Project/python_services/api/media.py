"""
Media API Routes
Endpoints for media generation and management
"""

import base64
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.security import require_internal_api_token
from services import FalAIService, GoogleTTSService, StorageService
from services.carousel_service import CarouselService

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


class ImageGenerateRequest(BaseModel):
    prompt: str
    model: str = "fal-ai/nano-banana-2"
    aspect_ratio: str = "16:9"

class VideoGenerateRequest(BaseModel):
    prompt: str
    duration: int = 5

class AudioGenerateRequest(BaseModel):
    text: str
    voice_id: str


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


@router.post("/generate/image")
async def generate_image(request: ImageGenerateRequest):
    """Generate an image using fal.ai"""
    try:
        fal_service = FalAIService()

        result = await fal_service.generate_image(
            prompt=request.prompt, model=request.model, aspect_ratio=request.aspect_ratio
        )

        await fal_service.close()

        return result

    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/video")
async def generate_video(request: VideoGenerateRequest):
    """Generate a video using fal.ai"""
    try:
        fal_service = FalAIService()

        result = await fal_service.generate_video(prompt=request.prompt, duration=request.duration)

        await fal_service.close()

        return result

    except Exception as e:
        logger.error(f"Video generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/audio")
async def generate_audio(request: AudioGenerateRequest):
    """Generate audio using Google Cloud Text-to-Speech."""
    try:
        tts_service = GoogleTTSService()
        available_voices = tts_service.get_voices()
        voice = available_voices.get(request.voice_id, request.voice_id)

        audio_bytes = await tts_service.generate_audio(
            text=request.text,
            voice=voice,
        )

        return {
            "voice": voice,
            "format": "mp3",
            "byte_length": len(audio_bytes),
            "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        }

    except Exception as e:
        logger.error(f"Audio generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def list_voices(language: str = None):
    """List available voices from Google TTS."""
    try:
        voices = GoogleTTSService().get_voices()
        if language:
            normalized_language = language.lower()
            voices = {
                name: voice
                for name, voice in voices.items()
                if normalized_language in voice.lower()
            }
        return {"voices": voices}

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
