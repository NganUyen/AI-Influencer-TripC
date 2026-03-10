"""
Media API Routes
Endpoints for media generation and management
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging

from services import FalAIService, PlayHTService, StorageService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate/image")
async def generate_image(
    prompt: str, model: str = "fal-ai/flux-pro", aspect_ratio: str = "16:9"
):
    """Generate an image using fal.ai"""
    try:
        fal_service = FalAIService()

        result = await fal_service.generate_image(
            prompt=prompt, model=model, aspect_ratio=aspect_ratio
        )

        await fal_service.close()

        return result

    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/video")
async def generate_video(prompt: str, duration: int = 5):
    """Generate a video using fal.ai"""
    try:
        fal_service = FalAIService()

        result = await fal_service.generate_video(prompt=prompt, duration=duration)

        await fal_service.close()

        return result

    except Exception as e:
        logger.error(f"Video generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/audio")
async def generate_audio(text: str, voice_id: str):
    """Generate audio using PlayHT"""
    try:
        playht_service = PlayHTService()

        result = await playht_service.generate_audio(text=text, voice_id=voice_id)

        await playht_service.close()

        return result

    except Exception as e:
        logger.error(f"Audio generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def list_voices(language: str = None):
    """List available voices from PlayHT"""
    try:
        playht_service = PlayHTService()

        voices = await playht_service.list_voices(language=language)

        await playht_service.close()

        return voices

    except Exception as e:
        logger.error(f"Failed to list voices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage/list")
async def list_storage_files(prefix: str = ""):
    """List files in R2 storage"""
    try:
        storage_service = StorageService()

        files = await storage_service.list_files(prefix=prefix)

        return {"files": files}

    except Exception as e:
        logger.error(f"Failed to list files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
