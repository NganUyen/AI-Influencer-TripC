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
import os
from io import BytesIO

from services.fal_service import FalAIService
from services.google_tts_service import GoogleTTSService
from services.heygen_service import HeyGenService
from services.storage_service import StorageService
from services.media_storage_service import MediaStorageService
from services.image_generation_service import ImageGenerationService
from services.contracts import AudioInput, ImageInput, VideoInput
from .video_activities import build_split_screen_video
import services.media_storage_service as media_storage_service_module
try:
    import services.browser_automation as browser_automation_module
except ImportError:  # pragma: no cover - exercised in slim runtime images
    browser_automation_module = None
BrowserAutomationService = None
_DEFAULT_MEDIA_STORAGE_SERVICE_CLASS = MediaStorageService
from services.content_scenes_service import (
    generate_content_scenes as get_scenes,
    generate_app_tutorial_scenes as get_app_scenes,
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
    language = config.get("language") or prompt_config.get("language")
    requested = (
        config.get("voice") or prompt_config.get("voice_id") or "vi-VN-Wavenet-D"
    )
    return GoogleTTSService.resolve_voice_name(requested, language=language)


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

    metadata = _prompt_metadata(prompt_config)
    campaign_id = prompt_config.get("campaign_id") or metadata.get("campaign_id")
    persona_id = prompt_config.get("persona_id") or metadata.get("persona_id")
    owner_key = prompt_config.get("owner_key") or metadata.get("owner_key")
    user_id = prompt_config.get("user_id") or metadata.get("user_id")
    image_service = ImageGenerationService()
    try:
        result = await image_service.generate_images(
            prompt=image_input.prompt,
            model=image_input.config.model or "fal-ai/flux-pro",
            aspect_ratio=image_input.config.aspect_ratio or "16:9",
            safety_tolerance=image_input.config.safety_tolerance or 2,
            num_images=1,
            campaign_id=str(campaign_id) if campaign_id else None,
            user_id=user_id,
            owner_key=owner_key,
            persona_id=persona_id,
            metadata=metadata,
            file_name_hint=f"{metadata.get('platform', 'image')}-{metadata.get('day', '1')}",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to generate image HTTP error: {str(e)}")
        # Do not retry on 4xx clients errors to prevent burning limits/billing
        non_retryable = 400 <= e.response.status_code < 500
        raise ApplicationError(
            f"Image generation HTTP error: {str(e)}", non_retryable=non_retryable
        )
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise ApplicationError(
            f"Image generation failed: {str(e)}", non_retryable=False
        )
    finally:
        await image_service.close()

    return {
        "type": "image",
        "service": "fal_ai",
        "url": result.get("url"),
        "source_url": result.get("source_url"),
        "storage_url": result.get("storage_url") or result.get("url"),
        "storage_key": result.get("storage_key"),
        "status": "completed",
        "data": result,
        "images": result.get("images", []),
        "metadata": metadata,
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

    metadata = _prompt_metadata(prompt_config)
    campaign_id = prompt_config.get("campaign_id") or metadata.get("campaign_id")
    persona_id = prompt_config.get("persona_id") or metadata.get("persona_id")
    owner_key = prompt_config.get("owner_key") or metadata.get("owner_key")
    user_id = prompt_config.get("user_id") or metadata.get("user_id")
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
        raise ApplicationError(
            f"Video generation HTTP error: {str(e)}", non_retryable=non_retryable
        )
    except Exception as e:
        logger.error(f"Failed to generate video: {str(e)}")
        raise ApplicationError(
            f"Video generation failed: {str(e)}", non_retryable=False
        )
    finally:
        await fal_service.close()

    storage_result = None
    if result.get("url"):
        storage_result = await MediaStorageService().upload_from_url(
            url=result["url"],
            campaign_id=str(campaign_id) if campaign_id else None,
            asset_type="VIDEO",
            generation_prompt=video_input.prompt,
            provider_job_id=result.get("request_id"),
            user_id=user_id,
            owner_key=owner_key,
            persona_id=persona_id,
            metadata=metadata,
            file_name_hint=f"{metadata.get('platform', 'video')}-{metadata.get('day', '1')}",
        )
    storage_url = None
    if storage_result:
        if isinstance(storage_result, dict):
            storage_url = storage_result.get("access_url") or storage_result.get("url")
        else:
            storage_url = str(storage_result)
    effective_url = storage_url or result.get("url")

    return {
        "type": "video",
        "service": "fal_ai",
        "url": effective_url,
        "source_url": result.get("url"),
        "storage_url": effective_url,
        "storage_key": storage_result.get("storage_path")
        if isinstance(storage_result, dict)
        else None,
        "status": "completed",
        "data": result,
        "metadata": {
            **metadata,
            "storage_status": "stored" if storage_url else "source_only",
        },
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
        config={
            **(prompt_config.get("config") or {}),
            "voice": _prompt_voice(prompt_config),
        },
    )
    logger.info(f"Generating audio for platform: {audio_input.metadata.platform}")

    voice_language = (prompt_config.get("config") or {}).get(
        "language"
    ) or prompt_config.get("language")
    voice_mapped = GoogleTTSService.resolve_voice_name(
        audio_input.config.voice or "vi-VN-Wavenet-D",
        language=voice_language,
    )
    metadata = _prompt_metadata(prompt_config)

    text_to_speak = audio_input.script
    if not text_to_speak:
        raise ApplicationError("Missing audio script in prompt", non_retryable=True)

    try:
        tts_service = GoogleTTSService()
        audio_bytes = await tts_service.generate_audio(
            text=text_to_speak,
            voice=voice_mapped,
            language=voice_language,
        )

        campaign_id = prompt_config.get("campaign_id") or metadata.get("campaign_id")
        persona_id = prompt_config.get("persona_id") or metadata.get("persona_id")
        owner_key = prompt_config.get("owner_key") or metadata.get("owner_key")
        user_id = prompt_config.get("user_id") or metadata.get("user_id")
        file_extension = "mp3"
        day = audio_input.metadata.day
        platform = audio_input.metadata.platform
        storage_result = None
        if campaign_id or persona_id or user_id or owner_key:
            storage_result = await MediaStorageService().upload_bytes(
                data=audio_bytes,
                content_type=f"audio/{file_extension}",
                campaign_id=str(campaign_id) if campaign_id else None,
                asset_type="AUDIO",
                asset_kind="audio",
                generation_prompt=text_to_speak,
                user_id=user_id,
                owner_key=owner_key,
                persona_id=persona_id,
                metadata=metadata,
                file_name_hint=f"{platform or 'audio'}-{day or '1'}",
            )

        if storage_result and storage_result.get("access_url"):
            public_url = storage_result["access_url"]
        else:
            storage_service = StorageService()
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
            "storage_url": public_url,
            "voice": voice_mapped,
            "metadata": metadata,
            "status": "completed",
        }

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code if e.response is not None else None
        error_message = str(e)
        non_retryable = bool(status_code and 400 <= status_code < 500 and status_code != 429)

        if status_code in {401, 403}:
            error_message = (
                "Google TTS authentication/configuration failed. "
                "Check GOOGLE_TTS_API_KEY and Google Cloud Text-to-Speech access. "
                f"Provider response: {e}"
            )
        elif status_code == 400:
            error_message = (
                "Google TTS rejected the request. "
                f"Check the configured voice '{voice_mapped}' and payload. "
                f"Provider response: {e}"
            )

        logger.error("Failed to generate audio HTTP error: %s", error_message)
        raise ApplicationError(
            f"Failed to generate audio via Google TTS: {error_message}",
            non_retryable=non_retryable,
        )
    except ValueError as e:
        logger.error("Failed to initialize Google TTS: %s", str(e))
        raise ApplicationError(
            f"Failed to generate audio via Google TTS: {str(e)}",
            non_retryable=True,
        )
    except Exception as e:
        logger.error(f"Failed to generate audio: {str(e)}")
        raise ApplicationError(
            f"Failed to generate audio via Google TTS: {str(e)}",
            non_retryable=False,
        )


@activity.defn
async def upload_to_storage(media_asset: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upload generated media to the configured object storage backend
    Returns public URL for distribution
    """
    logger.info(f"Uploading {media_asset.get('type')} to object storage")

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
            f"Failed to download media for upload: {str(e)}",
            non_retryable=non_retryable,
        )
    except httpx.HTTPError as e:
        logger.error(f"Failed to download generated media: {str(e)}")
        raise ApplicationError(
            f"Failed to download media for upload: {str(e)}", non_retryable=False
        )

    # Upload to object storage
    file_extension = (
        "mp4"
        if media_asset["type"] == "video"
        else "mp3"
        if media_asset["type"] == "audio"
        else "png"
    )

    _campaign_id = media_asset.get("campaign_id") or asset_metadata.get("campaign_id")
    _persona_id = media_asset.get("persona_id") or asset_metadata.get("persona_id")
    _owner_key = media_asset.get("owner_key") or asset_metadata.get("owner_key")
    _user_id = media_asset.get("user_id") or asset_metadata.get("user_id")
    storage_result = None
    if _campaign_id or _persona_id or _user_id or _owner_key:
        storage_result = await MediaStorageService().upload_bytes(
            data=response.content,
            content_type=f"{media_asset['type']}/{file_extension}",
            campaign_id=str(_campaign_id) if _campaign_id else None,
            asset_type=media_asset["type"].upper(),
            asset_kind=media_asset["type"],
            generation_prompt=media_asset.get("prompt", ""),
            user_id=_user_id,
            owner_key=_owner_key,
            persona_id=_persona_id,
            metadata={
                "day": asset_metadata.get("day"),
                "platform": asset_metadata.get("platform"),
            },
            file_name_hint=f"{media_asset['type']}-{asset_metadata.get('platform', 'default')}",
        )

    if storage_result and storage_result.get("access_url"):
        public_url = storage_result["access_url"]
    else:
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
        raise ApplicationError(
            "create_slideshow: missing 'image_urls'", non_retryable=True
        )
    if not audio_url:
        raise ApplicationError(
            "create_slideshow: missing 'audio_url'", non_retryable=True
        )

    result = await build_split_screen_video(
        {
            "image_urls": image_urls,
            "audio_url": audio_url,
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
    """Generate a talking-head asset via HeyGen and store it in object storage."""
    avatar_id: str = config.get("avatar_id", "")
    audio_url: str = config.get("audio_url", "")
    background: str = config.get("background", "blur")
    day: int = config.get("day", 1)
    topic: str = config.get("topic", "episode")
    persona_id: str = config.get("persona_id", "legacy")
    owner_key = config.get("owner_key")
    user_id = config.get("user_id")

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
        width=1080,
        height=1920,
        allow_aspect_ratio_fallback=True,
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

    storage_result = None
    if persona_id or user_id or owner_key:
        storage_result = await MediaStorageService().upload_bytes(
            data=video_bytes,
            content_type="video/mp4",
            campaign_id=config.get("campaign_id"),
            asset_type="VIDEO",
            asset_kind="video",
            generation_prompt=topic,
            user_id=user_id,
            owner_key=owner_key,
            persona_id=persona_id,
            metadata={"day": day, "source": "talking_head"},
            file_name_hint=topic,
        )

    if storage_result and storage_result.get("access_url"):
        public_url = storage_result["access_url"]
    else:
        filename = f"videos/{persona_id}/talking_head/day{day}/{topic.replace(' ', '_')[:30]}.mp4"
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
async def generate_app_tutorial_activity(
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Activity sinh 8 scenes hướng dẫn App cho 1 châu lục cụ thể.
    """
    app_name = config.get("app_name", "TripC")
    continent = config.get("continent", "asia")
    use_ai = config.get("use_ai_captions", True)

    return await get_app_scenes(
        app_name=app_name, continent=continent, use_ai_captions=use_ai
    )


@activity.defn
async def generate_web_tutorial_activity(
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Activity nâng cao: Đọc website và sinh hướng dẫn sử dụng tự động.
    """
    from services.browser_automation import BrowserAutomationService
    from services.content_scenes_service import RegionService

    url = config.get("url")
    country_code = config.get("country_code")  # Manual override (VPN mode)

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
    """Generate top-half scene assets as Playwright browser recordings only."""

    raw_limit = os.getenv("TOP_HALF_CAPTURE_CONCURRENCY", "2")
    try:
        max_parallel = max(1, int(raw_limit))
    except ValueError:
        max_parallel = 2
    semaphore = asyncio.Semaphore(max_parallel)

    async def gen_one(scene: dict) -> dict:
        async with semaphore:
            scene_metadata = dict(scene.get("metadata") or {})
            top_half_type = scene.get("top_half_source_type")
            source_ref = scene.get("source_ref")
            scene_id = scene.get("id", "unknown")
            browser = None

            if top_half_type != "public_page_capture":
                raise ApplicationError(
                    (
                        "Top-half scene must use public_page_capture for Playwright "
                        f"recording (scene={scene_id}, source_type={top_half_type!r})"
                    ),
                    non_retryable=True,
                )

            if not source_ref:
                raise ApplicationError(
                    (
                        "Top-half scene is missing source_ref URL required for "
                        f"Playwright recording (scene={scene_id})"
                    ),
                    non_retryable=True,
                )

            try:
                browser_service_class = BrowserAutomationService
                if browser_service_class is None and browser_automation_module is not None:
                    browser_service_class = browser_automation_module.BrowserAutomationService
                if browser_service_class is None:
                    raise RuntimeError(
                        "Browser automation dependencies are not installed in this runtime image."
                    )

                browser = browser_service_class()
                os.makedirs("/tmp/tutorials_videos", exist_ok=True)

                # Inject region and proxy to avoid being blocked (white screen)
                region_info = None
                proxy_config = None
                user_id = scene_metadata.get("user_id") or scene_metadata.get("uid")
                
                # Determine platform for viewport (mobile vs desktop)
                # If metadata mentions tiktok or portrait format, use mobile settings
                platform_hint = "generic"
                video_format = scene_metadata.get("video_format", "").lower()
                if "tiktok" in str(scene_metadata.get("platform", "")).lower() or "portrait" in video_format or "9:16" in video_format:
                    platform_hint = "tiktok"

                try:
                    from services.region_service import RegionService
                    from services.proxy_manager_service import ProxyManagerService

                    # 1. Get region profile
                    region_info = await RegionService().build_region_profile()

                    # 2. Lease a generic proxy to avoid datacenter IP blocks
                    if user_id:
                        try:
                            lease = await ProxyManagerService.lease_proxy(
                                account_key=str(user_id),
                                platform="generic"
                            )
                            proxy_config = lease.get("proxy")
                            logger.info(f"Leased proxy for capture | user_id={user_id} | server={proxy_config.get('server')}")
                        except Exception as pe:
                            logger.warning(f"Failed to lease proxy for capture: {pe}. Proceeding without proxy.")
                except ImportError:
                    logger.warning("Region/Proxy services not available. Proceeding with defaults.")

                await browser.initialize_browser(
                    record_video_dir="/tmp/tutorials_videos",
                    record_video_size={"width": 1080, "height": 960},
                    region_info=region_info,
                    proxy_config=proxy_config,
                    platform=platform_hint
                )

                capture_hint = scene.get("top_half_capture_hint", "scroll")
                target_selector = scene.get("top_half_target")
                max_capture_seconds = (
                    scene.get("top_half_max_capture_seconds")
                    or scene_metadata.get("top_half_max_capture_seconds")
                    or 60
                )
                follow_relevant_links = scene.get("top_half_follow_links")
                if follow_relevant_links is None:
                    follow_relevant_links = scene_metadata.get("top_half_follow_links")
                if follow_relevant_links is None:
                    follow_relevant_links = True
                
                logger.info(
                    "Starting browser capture | scene=%s | url=%s | hint=%s | target=%s | platform=%s | max_seconds=%s | follow_links=%s",
                    scene_id,
                    source_ref[:60],
                    capture_hint,
                    target_selector,
                    platform_hint,
                    max_capture_seconds,
                    follow_relevant_links,
                )
                
                video_path = await browser.record_video_for_tutorial(
                    source_ref,
                    capture_hint=capture_hint,
                    target_selector=target_selector,
                    viewport_width=1080,
                    viewport_height=960,
                    max_capture_seconds=int(max_capture_seconds),
                    follow_relevant_links=bool(follow_relevant_links),
                )

                # CRITICAL: Close browser BEFORE reading the file to ensure Playwright finalizes the .webm
                await browser.close()
                browser = None

                if not video_path or not os.path.exists(video_path):
                    raise RuntimeError(
                        f"Playwright recording did not produce a video file for scene {scene_id}"
                    )

                for _ in range(120):
                    if os.path.exists(video_path) and os.path.getsize(video_path) >= 1024:
                        break
                    await asyncio.sleep(0.25)

                # Guard against 0-byte or corrupted (tiny header only) captures
                file_size = os.path.getsize(video_path)
                if file_size < 2000:
                    raise RuntimeError(
                        f"Browser capture produced an invalid/tiny file ({file_size} bytes) for scene {scene_id}"
                    )

                with open(video_path, "rb") as f:
                    data = f.read()

                if len(data) < 1024:
                    raise RuntimeError(
                        f"Playwright recording is too small for scene {scene_id}: {len(data)} bytes"
                    )

                media_storage_service_class = MediaStorageService
                if media_storage_service_class is _DEFAULT_MEDIA_STORAGE_SERVICE_CLASS:
                    media_storage_service_class = media_storage_service_module.MediaStorageService
                media_storage = media_storage_service_class()
                run_suffix = str(
                    scene_metadata.get("workflow_run_id")
                    or scene_metadata.get("workflow_id")
                    or "run"
                ).replace("/", "-")
                storage_result = await media_storage.upload_bytes(
                    data=data,
                    destination_path=None,
                    content_type="video/webm",
                    asset_kind="video",
                    asset_origin="generated",
                    persona_id=scene.get("persona_id") or scene_metadata.get("persona_id"),
                    owner_key=scene.get("owner_key") or scene_metadata.get("owner_key"),
                    campaign_id=scene.get("campaign_id") or scene_metadata.get("campaign_id"),
                    user_id=scene.get("user_id") or scene_metadata.get("user_id"),
                    file_name_hint=f"browser-capture-scene-{scene_id}-{run_suffix[:24]}",
                )

                if storage_result is None:
                    raise RuntimeError(
                        "MediaStorageService.upload_bytes returned None for Playwright recording"
                    )

                final_url = storage_result.get("url") or storage_result.get("storage_url")
                if not final_url:
                    raise RuntimeError(
                        f"Playwright recording uploaded but URL is missing for scene {scene_id}"
                    )

                logger.info(
                    "Scene asset resolved | scene=%s | type=%s | url=%s | is_video=%s",
                    scene_id,
                    top_half_type,
                    final_url[:80],
                    True,
                )

                return {
                    **scene,
                    "image_url": final_url,
                    "source_image_url": final_url,
                    "storage_image_url": storage_result.get("storage_url"),
                    "image_storage_key": storage_result.get("storage_key"),
                    "media_asset_id": storage_result.get("media_asset_id"),
                    "status": "completed",
                    "is_video": True,
                }
            except Exception as e:
                logger.error(
                    "Browser capture FAILED for scene %s | url=%s | error_type=%s | error=%s",
                    scene_id,
                    source_ref[:80],
                    type(e).__name__,
                    str(e)[:300],
                )
                raise ApplicationError(
                    f"Playwright top-half recording failed for scene {scene_id}: {e}",
                    non_retryable=False,
                )
            finally:
                if browser is not None:
                    try:
                        await browser.close()
                    except Exception as close_exc:
                        logger.warning(
                            "Failed to close browser after scene %s capture attempt: %s",
                            scene_id,
                            close_exc,
                        )

    logger.info(
        "Generating %s top-half browser recordings with concurrency=%s...",
        len(scenes),
        max_parallel,
    )
    tasks = [gen_one(scene) for scene in scenes]
    enriched = await asyncio.gather(*tasks)
    logger.info("Top-half browser recording completed")
    return list(enriched)


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
        raise ApplicationError(
            "create_split_screen_video: missing 'scenes'", non_retryable=True
        )

    logger.info("create_split_screen_video is delegating to build_split_screen_video")
    result = await build_split_screen_video(
        {
            "image_urls": [
                scene.get("image_url") for scene in scenes if scene.get("image_url")
            ],
            "audio_url": config.get("audio_url", ""),
            "talking_head_url": config.get("heygen_video_url", ""),
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
