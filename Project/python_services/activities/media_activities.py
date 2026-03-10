"""
Media Generation Activities
Integrates with fal.ai, PlayHT, and storage services
"""

from temporalio import activity
from typing import Dict, Any
import logging
import httpx
from io import BytesIO

from services.fal_service import FalAIService
from services.playht_service import PlayHTService
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


@activity.defn
async def generate_image(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate image using fal.ai
    Supports models like Flux.1 Pro, SDXL, etc.
    """
    logger.info(f"Generating image for day {prompt_config.get('day')}")

    fal_service = FalAIService()

    result = await fal_service.generate_image(
        prompt=prompt_config.get("prompt"),
        model=prompt_config.get("config", {}).get("model", "fal-ai/flux-pro"),
        aspect_ratio=prompt_config.get("config", {}).get("aspect_ratio", "16:9"),
        safety_tolerance=prompt_config.get("config", {}).get("safety_tolerance", 2),
    )

    return {
        "type": "image",
        "service": "fal_ai",
        "url": result.get("url"),
        "data": result,
        "metadata": prompt_config,
    }


@activity.defn
async def generate_video(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate video using fal.ai video models
    """
    logger.info(f"Generating video for day {prompt_config.get('day')}")

    fal_service = FalAIService()

    result = await fal_service.generate_video(
        prompt=prompt_config.get("prompt"),
        duration=prompt_config.get("config", {}).get("duration", 5),
        fps=prompt_config.get("config", {}).get("fps", 24),
    )

    return {
        "type": "video",
        "service": "fal_ai",
        "url": result.get("url"),
        "data": result,
        "metadata": prompt_config,
    }


@activity.defn
async def generate_audio(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate audio using PlayHT
    Supports 900+ voices across 142 languages
    """
    logger.info(f"Generating audio for day {prompt_config.get('day')}")

    playht_service = PlayHTService()

    result = await playht_service.generate_audio(
        text=prompt_config.get("script"),
        voice_id=prompt_config.get("voice_id"),
        voice_engine=prompt_config.get("config", {}).get("voice_engine", "PlayHT2.0"),
        output_format=prompt_config.get("config", {}).get("output_format", "mp3"),
    )

    return {
        "type": "audio",
        "service": "playht",
        "url": result.get("url"),
        "data": result,
        "metadata": prompt_config,
    }


@activity.defn
async def upload_to_storage(media_asset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upload generated media to Cloudflare R2 storage
    Returns public URL for distribution
    """
    logger.info(f"Uploading {media_asset.get('type')} to R2 storage")

    storage_service = StorageService()

    # Download media from generation service
    async with httpx.AsyncClient() as client:
        response = await client.get(media_asset["url"])
        media_data = BytesIO(response.content)

    # Upload to R2
    file_extension = (
        "mp4"
        if media_asset["type"] == "video"
        else "mp3" if media_asset["type"] == "audio" else "png"
    )

    filename = f"{media_asset['metadata']['day']}/{media_asset['type']}_{media_asset['metadata'].get('platform', 'default')}.{file_extension}"

    public_url = await storage_service.upload(
        file_data=media_data,
        filename=filename,
        content_type=f"{media_asset['type']}/{file_extension}",
    )

    return {
        **media_asset,
        "storage_url": public_url,
        "uploaded_at": activity.info().current_attempt_scheduled_time.isoformat(),
    }
