"""
Media Generation Activities
Integrates with fal.ai, PlayHT, Google TTS, HeyGen, and storage services
"""

from temporalio import activity
from temporalio.exceptions import ApplicationError
from typing import Dict, Any, List
import logging
import httpx
import asyncio
from io import BytesIO

from services.fal_service import FalAIService
from services.google_tts_service import GoogleTTSService
from services.heygen_service import HeyGenService
from services.storage_service import StorageService
from services.contracts import AudioInput, ImageInput, VideoInput
from .video_activities import build_split_screen_video
from services.content_scenes_service import (
    generate_content_scenes as get_scenes,
    generate_app_tutorial_scenes as get_app_scenes
)

logger = logging.getLogger(__name__)


def _prompt_metadata(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    metadata = dict(prompt_config.get("metadata") or {})
    if "day" not in metadata and prompt_config.get("day") is not None:
        metadata["day"] = prompt_config.get("day")
    if "platform" not in metadata and prompt_config.get("platform") is not None:
        metadata["platform"] = prompt_config.get("platform")
    return metadata


def _prompt_voice(prompt_config: Dict[str, Any]) -> str:
    config = prompt_config.get("config") or {}
    return config.get("voice") or prompt_config.get("voice_id") or "vi-VN-Wavenet-D"


@activity.defn
async def generate_image(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate image using fal.ai
    Supports models like Flux.1 Pro, SDXL, etc.
    """
    image_input = ImageInput(
        prompt=prompt_config.get("prompt", ""),
        metadata=_prompt_metadata(prompt_config),
        config=prompt_config.get("config") or {},
    )
    logger.info(f"Generating image for day {image_input.metadata.day}")

    fal_service = FalAIService()

    try:
        result = await fal_service.generate_image(
            prompt=image_input.prompt,
            model=image_input.config.model or "fal-ai/flux-pro",
            aspect_ratio=image_input.config.aspect_ratio or "16:9",
            safety_tolerance=image_input.config.safety_tolerance or 2,
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to generate image HTTP error: {str(e)}")
        # Do not retry on 4xx clients errors to prevent burning limits/billing
        non_retryable = 400 <= e.response.status_code < 500
        raise ApplicationError(f"Image generation HTTP error: {str(e)}", non_retryable=non_retryable)
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise ApplicationError(f"Image generation failed: {str(e)}", non_retryable=False)
    finally:
        await fal_service.close()

    return {
        "type": "image",
        "service": "fal_ai",
        "url": result.get("url"),
        "status": "completed",
        "data": result,
        "metadata": image_input.model_dump(),
    }


@activity.defn
async def generate_video(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate video using fal.ai video models
    """
    video_input = VideoInput(
        prompt=prompt_config.get("prompt", ""),
        metadata=_prompt_metadata(prompt_config),
        config=prompt_config.get("config") or {},
    )
    logger.info(f"Generating video for day {video_input.metadata.day}")

    fal_service = FalAIService()

    try:
        result = await fal_service.generate_video(
            prompt=video_input.prompt,
            duration=int(video_input.config.duration or 5),
            fps=video_input.config.fps or 24,
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to generate video HTTP error: {str(e)}")
        non_retryable = 400 <= e.response.status_code < 500
        raise ApplicationError(f"Video generation HTTP error: {str(e)}", non_retryable=non_retryable)
    except Exception as e:
        logger.error(f"Failed to generate video: {str(e)}")
        raise ApplicationError(f"Video generation failed: {str(e)}", non_retryable=False)
    finally:
        await fal_service.close()

    return {
        "type": "video",
        "service": "fal_ai",
        "url": result.get("url"),
        "status": "completed",
        "data": result,
        "metadata": video_input.model_dump(),
    }


@activity.defn
async def generate_audio(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate audio using Google TTS API
    Returns URL of generated audio
    """
    audio_input = AudioInput(
        script=prompt_config.get("script", ""),
        metadata=_prompt_metadata(prompt_config),
        config={**(prompt_config.get("config") or {}), "voice": _prompt_voice(prompt_config)},
    )
    logger.info(f"Generating audio for platform: {audio_input.metadata.platform}")

    tts_service = GoogleTTSService()
    voice_mapped = audio_input.config.voice or "vi-VN-Wavenet-D"

    text_to_speak = audio_input.script
    if not text_to_speak:
        raise ApplicationError("Missing audio script in prompt", non_retryable=True)

    try:
        audio_bytes = await tts_service.generate_audio(
            text=text_to_speak,
            voice=voice_mapped,
        )
        
        storage_service = StorageService()
        file_extension = "mp3"
        day = audio_input.metadata.day
        platform = audio_input.metadata.platform
        filename = f"{day}/audio_{platform}.{file_extension}"
        
        public_url = await storage_service.upload(
            file_data=BytesIO(audio_bytes),
            filename=filename,
            content_type=f"audio/{file_extension}",
        )
        
        logger.info(f"Audio generated and uploaded successfully")
        
        return {
            "type": "audio",
            "service": "google_tts",
            "url": public_url,
            "voice": voice_mapped,
            "metadata": audio_input.model_dump(),
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Failed to generate audio: {str(e)}")
        # If it's auth failure, don't retry
        non_retryable = "API" in str(e) or "key" in str(e).lower()
        raise ApplicationError(
            f"Failed to generate audio via Google TTS: {str(e)}", non_retryable=non_retryable
        )


@activity.defn
async def upload_to_storage(media_asset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upload generated media to Cloudflare R2 storage
    Returns public URL for distribution
    """
    logger.info(f"Uploading {media_asset.get('type')} to R2 storage")

    storage_service = StorageService()
    asset_metadata = _prompt_metadata(media_asset.get("metadata") or {})

    # Download media from generation service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(media_asset["url"], timeout=60.0)
            response.raise_for_status()
            media_data = BytesIO(response.content)
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to download generated media: {str(e)}")
        non_retryable = 400 <= e.response.status_code < 500
        raise ApplicationError(
            f"Failed to download media for upload: {str(e)}", non_retryable=non_retryable
        )
    except httpx.HTTPError as e:
        logger.error(f"Failed to download generated media: {str(e)}")
        raise ApplicationError(
            f"Failed to download media for upload: {str(e)}", non_retryable=False
        )

    # Upload to R2
    file_extension = (
        "mp4"
        if media_asset["type"] == "video"
        else "mp3" if media_asset["type"] == "audio" else "png"
    )

    filename = f"{asset_metadata['day']}/{media_asset['type']}_{asset_metadata.get('platform', 'default')}.{file_extension}"

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


# ─────────────────────────────────────────────────────────────────────────────
# Nhánh 2: Slideshow Video (ffmpeg)
# ─────────────────────────────────────────────────────────────────────────────

@activity.defn
async def create_slideshow(config: Dict[str, Any]) -> Dict[str, Any]:
    """DEPRECATED compatibility wrapper around build_split_screen_video()."""
    image_urls: List[str] = config.get("image_urls", [])
    audio_url: str = config.get("audio_url", "")

    if not image_urls:
        raise ApplicationError("create_slideshow: missing 'image_urls'", non_retryable=True)
    if not audio_url:
        raise ApplicationError("create_slideshow: missing 'audio_url'", non_retryable=True)

    result = await build_split_screen_video(
        {
            "image_urls": image_urls,
            "audio_url": audio_url,
            "scene_captions": config.get("scene_captions", []),
            "persona_id": config.get("persona_id", "legacy"),
            "topic": config.get("topic", config.get("output_filename", "slideshow")),
            "duration_per_image": config.get("duration_per_image", 4.0),
        }
    )

    return {
        "type": "slideshow_video",
        "url": result["video_url"],
        "storage_url": result["video_url"],
        "preview_url": result.get("preview_url"),
        "storage_key": result.get("storage_key"),
        "status": result.get("status", "completed"),
        "duration": result.get("duration"),
        "image_count": len(image_urls),
        "day": config.get("day", 1),
        "metadata": result.get("metadata", config),
    }
# ─────────────────────────────────────────────────────────────────────────────
# Nhánh 1: Talking Head (HeyGen)
# ─────────────────────────────────────────────────────────────────────────────

@activity.defn
async def create_talking_head_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a talking-head asset via HeyGen and store it in R2."""
    avatar_id: str = config.get("avatar_id", "")
    audio_url: str = config.get("audio_url", "")
    background: str = config.get("background", "blur")
    day: int = config.get("day", 1)
    topic: str = config.get("topic", "episode")

    if not avatar_id or not audio_url:
        raise ApplicationError(
            "create_talking_head_video: missing 'avatar_id' or 'audio_url'",
            non_retryable=True,
        )

    heygen = HeyGenService()
    storage = StorageService()

    logger.info(f"Creating talking head | avatar: {avatar_id} | day: {day}")

    video_job = await heygen.create_video(
        avatar_id=avatar_id,
        audio_url=audio_url,
        background=background,
        aspect_ratio="9:16",
    )

    video_id = video_job.get("video_id")
    if not video_id:
        raise ApplicationError("HeyGen did not return video_id", non_retryable=False)

    logger.info(f"Polling HeyGen video {video_id}...")
    heygen_video_url = await heygen.poll_video_status(video_id, timeout_seconds=600)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(heygen_video_url)
        response.raise_for_status()
        video_bytes = response.content

    filename = f"videos/talking_head/day{day}/{topic.replace(' ', '_')[:30]}.mp4"
    public_url = await storage.upload_bytes(
        data=video_bytes,
        filename=filename,
        content_type="video/mp4",
    )

    return {
        "type": "talking_head_video",
        "url": public_url,
        "storage_url": public_url,
        "heygen_video_id": video_id,
        "status": "completed",
        "day": day,
        "topic": topic,
        "metadata": config,
    }
@activity.defn
async def generate_app_tutorial_activity(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Activity sinh 8 scenes hướng dẫn App cho 1 châu lục cụ thể.
    """
    app_name = config.get("app_name", "TripC")
    continent = config.get("continent", "asia")
    use_ai = config.get("use_ai_captions", True)
    
    return await get_app_scenes(app_name=app_name, continent=continent, use_ai_captions=use_ai)

@activity.defn
async def generate_web_tutorial_activity(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Activity nâng cao: Đọc website và sinh hướng dẫn sử dụng tự động.
    """
    from services.browser_automation import BrowserAutomationService
    from services.content_scenes_service import RegionService
    
    url = config.get("url")
    country_code = config.get("country_code") # Manual override (VPN mode)
    
    # 1. Nhận diện vùng miền (có hỗ trợ override)
    region_svc = RegionService()
    region_info = await region_svc.get_region_info(country_code_override=country_code)
    continent = region_info.get("continent", "asia")
    
    # 2. Đọc nội dung web
    browser = BrowserAutomationService()
    try:
        # web_content = await browser.get_page_content(url) # Để AI phân tích sau
        # Giả định app_name từ URL
        app_name = url.split("//")[-1].split(".")[0].capitalize()
        
        # 3. Sinh scenes (Dùng lại logic sinh scene tutorial có sẵn)
        scenes = await get_app_scenes(app_name=app_name, continent=continent)
        
        # Ghi chú thêm vào kịch bản
        for s in scenes:
            s["source"] = f"AI analyzed from {url}"
            
        return scenes
    finally:
        await browser.close()


# ─────────────────────────────────────────────────────────────────────────────
# Scene Images Generation (fal.ai, song song)
# ─────────────────────────────────────────────────────────────────────────────

@activity.defn
async def generate_scene_images(scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate scene images in parallel and return enriched scene payloads."""
    fal = FalAIService()

    async def gen_one(scene: dict) -> dict:
        result = await fal.generate_image(
            prompt=scene["image_prompt"],
            model=scene.get("config", {}).get("model", "fal-ai/flux/schnell"),
            aspect_ratio="9:16",
            safety_tolerance=2,
        )
        return {**scene, "image_url": result.get("url"), "status": "completed"}

    logger.info(f"Generating {len(scenes)} scene images in parallel...")
    try:
        tasks = [gen_one(scene) for scene in scenes]
        enriched = await asyncio.gather(*tasks)
        logger.info("Scene image generation completed")
        return list(enriched)
    finally:
        await fal.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE: Split Screen 9:16
# ┌─────────────────┐
# │   TOP (1080x960)│  ← Slideshow + caption overlay (Ken Burns)
# ├─────────────────┤
# │   BOT (1080x960)│  ← HeyGen talking head (no bg)
# └─────────────────┘
# ─────────────────────────────────────────────────────────────────────────────

@activity.defn
async def create_split_screen_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """DEPRECATED compatibility wrapper around build_split_screen_video()."""
    scenes: List[dict] = config.get("scenes", [])
    if not scenes:
        raise ApplicationError("create_split_screen_video: missing 'scenes'", non_retryable=True)

    logger.info("create_split_screen_video is delegating to build_split_screen_video")
    result = await build_split_screen_video(
        {
            "image_urls": [scene.get("image_url") for scene in scenes if scene.get("image_url")],
            "audio_url": config.get("audio_url", ""),
            "talking_head_url": config.get("heygen_video_url", ""),
            "scene_captions": [scene.get("caption", "") for scene in scenes],
            "persona_id": config.get("persona_id", "legacy"),
            "topic": config.get("topic", "episode"),
            "duration_per_image": config.get("duration_per_image", 4.0),
        }
    )
    return {
        "type": "split_screen_video",
        "url": result["video_url"],
        "storage_url": result["video_url"],
        "preview_url": result.get("preview_url"),
        "storage_key": result.get("storage_key"),
        "status": result.get("status", "completed"),
        "scene_count": len(scenes),
        "day": config.get("day", 1),
        "topic": config.get("topic", "episode"),
        "metadata": result.get("metadata", config),
    }
