"""
Media Generation Activities
Integrates with fal.ai, PlayHT, Google TTS, HeyGen, and storage services
"""

from temporalio import activity
from temporalio.exceptions import ApplicationError
from typing import Dict, Any, List
import json
import logging
import httpx
import asyncio
import os
from io import BytesIO

from config.settings import settings
from services.did_service import DIDService
from services.fal_service import FalAIService
from services.google_tts_service import GoogleTTSService
from services.heygen_service import HeyGenService
from services.storage_service import StorageService
from services.media_storage_service import MediaStorageService
from services.image_generation_service import ImageGenerationService
from services.errors import QuotaExceededError
from services.contracts import (
    AudioInput,
    ImageInput,
    VALID_TOP_HALF_SOURCE_TYPES,
    VideoInput,
)
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

# Import metrics module (optional - gracefully degrades if not available)
try:
    from services.browser_capture_metrics import capture_metrics, domain_tracker
    _METRICS_AVAILABLE = True
except ImportError:
    capture_metrics = None
    domain_tracker = None
    _METRICS_AVAILABLE = False

logger = logging.getLogger(__name__)

SAFE_FALLBACK_SOURCE_TYPE = "ai_visual_fallback"
_SHARED_ASYNC_SEMAPHORES: Dict[str, Dict[str, Any]] = {}


def _positive_int_env(name: str, default: int) -> int:
    raw_value = str(os.getenv(name, str(default))).strip()
    try:
        return max(1, int(raw_value))
    except (TypeError, ValueError):
        return default


def _truthy_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def _shared_async_semaphore(name: str, default: int) -> asyncio.Semaphore:
    limit = _positive_int_env(name, default)
    cached = _SHARED_ASYNC_SEMAPHORES.get(name)
    if cached and cached.get("limit") == limit:
        semaphore = cached.get("semaphore")
        if isinstance(semaphore, asyncio.Semaphore):
            return semaphore

    semaphore = asyncio.Semaphore(limit)
    _SHARED_ASYNC_SEMAPHORES[name] = {
        "limit": limit,
        "semaphore": semaphore,
    }
    return semaphore


def resolve_top_half_source_type(
    raw_type: str | None, logger: logging.Logger, beat: dict | None = None
) -> str:
    if raw_type in VALID_TOP_HALF_SOURCE_TYPES:
        return raw_type

    logger.error(
        "Unknown top_half_source_type; falling back to ai_visual_fallback",
        extra={
            "raw_type": raw_type,
            "beat_idx": beat.get("idx") if beat else None,
            "source_ref": beat.get("source_ref") if beat else None,
        },
    )
    return SAFE_FALLBACK_SOURCE_TYPE


def normalize_unknown_source_type_beat(beat: dict) -> dict:
    normalized = dict(beat)

    if normalized.get("top_half_source_type") == SAFE_FALLBACK_SOURCE_TYPE:
        normalized["top_half_prompt"] = (
            normalized.get("top_half_prompt")
            or normalized.get("prompt")
            or normalized.get("bottom_half_message")
            or "Create a relevant visual for this scene"
        )

    return normalized


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
            f"Image generation failed: {str(e)}",
            non_retryable=not getattr(e, "retryable", False),
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
            f"Video generation failed: {str(e)}",
            non_retryable=not getattr(e, "retryable", False),
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

    campaign_id = prompt_config.get("campaign_id") or metadata.get("campaign_id")
    persona_id = prompt_config.get("persona_id") or metadata.get("persona_id")
    owner_key = prompt_config.get("owner_key") or metadata.get("owner_key")
    user_id = prompt_config.get("user_id") or metadata.get("user_id")

    try:
        tts_service = GoogleTTSService()
        audio_bytes = await tts_service.generate_audio(
            text=text_to_speak,
            voice=voice_mapped,
            language=voice_language,
            user_id=user_id,
        )

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
        non_retryable = bool(
            status_code and 400 <= status_code < 500 and status_code != 429
        )

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
            non_retryable=not getattr(e, "retryable", False),
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


def _is_heygen_insufficient_credit_error(exc: Exception) -> bool:
    candidates = [str(exc)]
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            response_text = (response.text or "").strip()
        except Exception:
            response_text = ""
        if response_text:
            candidates.append(response_text)

        try:
            response_json = response.json()
        except Exception:
            response_json = None
        if response_json is not None:
            candidates.append(json.dumps(response_json, ensure_ascii=True))

    return any(
        "MOVIO_PAYMENT_INSUFFICIENT_CREDIT" in candidate
        or "Insufficient credit" in candidate
        for candidate in candidates
    )


def _is_provider_quota_error(exc: Exception, provider_name: str) -> bool:
    if isinstance(exc, QuotaExceededError):
        return provider_name.lower() in str(exc).lower()
    return False


def _raise_talking_head_activity_error(
    message: str,
    *,
    exc: Exception,
) -> None:
    if isinstance(exc, QuotaExceededError):
        raise ApplicationError(message, non_retryable=True) from exc

    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status_code = exc.response.status_code
        raise ApplicationError(
            message,
            non_retryable=400 <= status_code < 500 and status_code != 429,
        ) from exc

    raise ApplicationError(
        message,
        non_retryable=not getattr(exc, "retryable", False),
    ) from exc


async def _download_video_bytes(video_url: str) -> bytes:
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        return response.content


async def _store_talking_head_video(
    *,
    source_video_url: str,
    config: Dict[str, Any],
    provider: str,
    provider_job_id_key: str,
    provider_job_id: str,
) -> Dict[str, Any]:
    day: int = config.get("day", 1)
    topic: str = config.get("topic", "episode")
    persona_id: str = config.get("persona_id", "legacy")
    owner_key = config.get("owner_key")
    user_id = config.get("user_id")

    storage = StorageService()
    video_bytes = await _download_video_bytes(source_video_url)

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
            metadata={"day": day, "source": "talking_head", "provider": provider},
            file_name_hint=topic,
        )

    if storage_result and storage_result.get("access_url"):
        public_url = storage_result["access_url"]
    else:
        filename = (
            f"videos/{persona_id}/talking_head/day{day}/{topic.replace(' ', '_')[:30]}.mp4"
        )
        public_url = await storage.upload_bytes(
            data=video_bytes,
            filename=filename,
            content_type="video/mp4",
        )

    return {
        "type": "talking_head_video",
        "provider": provider,
        "url": public_url,
        "storage_url": public_url,
        provider_job_id_key: provider_job_id,
        "status": "completed",
        "day": day,
        "topic": topic,
        "metadata": {
            **config,
            "talking_head_provider": provider,
        },
    }


async def _create_did_talking_head_fallback(config: Dict[str, Any]) -> Dict[str, Any]:
    script_text = str(config.get("script_text") or "").strip()
    presenter_id = (
        str(config.get("did_presenter_id") or settings.DID_DEFAULT_PRESENTER_ID or "")
        .strip()
    )
    user_id = config.get("user_id")

    if not settings.DID_API_KEY:
        raise ValueError("D-ID fallback is unavailable because DID_API_KEY is not configured")
    if not script_text:
        raise ValueError("D-ID fallback requires script_text in the talking-head config")
    if not presenter_id:
        raise ValueError(
            "D-ID fallback requires DID_DEFAULT_PRESENTER_ID or did_presenter_id"
        )

    did = DIDService()
    clip_job = await did.create_clip(
        presenter_id=presenter_id,
        script_text=script_text,
        user_id=user_id,
    )
    clip_id = clip_job.get("clip_id")
    if not clip_id:
        raise ValueError("D-ID did not return clip_id")

    logger.warning(
        "Falling back from HeyGen to D-ID | presenter_id=%s | clip_id=%s",
        presenter_id,
        clip_id,
    )
    did_video_url = await did.poll_clip_status(
        clip_id,
        timeout_seconds=600,
        user_id=user_id,
    )
    return await _store_talking_head_video(
        source_video_url=did_video_url,
        config=config,
        provider="d_id",
        provider_job_id_key="did_clip_id",
        provider_job_id=clip_id,
    )


@activity.defn
async def create_talking_head_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a talking-head asset via HeyGen, with D-ID fallback on quota exhaustion."""
    avatar_id: str = config.get("avatar_id", "")
    audio_url: str = config.get("audio_url", "")
    background: str = config.get("background", "blur")
    platform: str = str(config.get("platform", "tiktok")).lower().strip()
    requested_ratio: str = str(config.get("aspect_ratio") or "").strip()
    day: int = config.get("day", 1)
    user_id = config.get("user_id")

    if not avatar_id or not audio_url:
        raise ApplicationError(
            "create_talking_head_video: missing 'avatar_id' or 'audio_url'",
            non_retryable=True,
        )

    heygen = HeyGenService()

    logger.info(f"Creating talking head | avatar: {avatar_id} | day: {day}")

    # HeyGen currently supports only 9:16 and 16:9 for create_video.
    if requested_ratio in {"9:16", "16:9"}:
        aspect_ratio = requested_ratio
    elif platform in {"youtube", "linkedin", "x", "twitter"}:
        aspect_ratio = "16:9"
    else:
        aspect_ratio = "9:16"

    width, height = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)

    try:
        video_job = await heygen.create_video(
            avatar_id=avatar_id,
            audio_url=audio_url,
            background=background,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
            allow_aspect_ratio_fallback=True,
            user_id=user_id,
        )
    except Exception as exc:
        if _is_heygen_insufficient_credit_error(exc) or _is_provider_quota_error(
            exc, "heygen"
        ):
            try:
                return await _create_did_talking_head_fallback(config)
            except Exception as fallback_exc:
                if isinstance(fallback_exc, ValueError) and "d-id fallback" in str(
                    fallback_exc
                ).lower():
                    raise ApplicationError(
                        f"HeyGen has insufficient API credits and D-ID fallback is unavailable: {fallback_exc}",
                        non_retryable=True,
                    ) from fallback_exc
                _raise_talking_head_activity_error(
                    "HeyGen quota is exhausted and D-ID fallback failed.",
                    exc=fallback_exc,
                )
        _raise_talking_head_activity_error(
            "Talking-head generation failed during HeyGen create_video.",
            exc=exc,
        )

    video_id = video_job.get("video_id")
    if not video_id:
        raise ApplicationError("HeyGen did not return video_id", non_retryable=False)

    logger.info(f"Polling HeyGen video {video_id}...")
    try:
        heygen_video_url = await heygen.poll_video_status(
            video_id,
            timeout_seconds=600,
            user_id=user_id,
        )
    except Exception as exc:
        if _is_heygen_insufficient_credit_error(exc) or _is_provider_quota_error(
            exc, "heygen"
        ):
            try:
                return await _create_did_talking_head_fallback(config)
            except Exception as fallback_exc:
                if isinstance(fallback_exc, ValueError) and "d-id fallback" in str(
                    fallback_exc
                ).lower():
                    raise ApplicationError(
                        f"HeyGen has insufficient API credits and D-ID fallback is unavailable: {fallback_exc}",
                        non_retryable=True,
                    ) from fallback_exc
                _raise_talking_head_activity_error(
                    "HeyGen quota is exhausted and D-ID fallback failed.",
                    exc=fallback_exc,
                )
        _raise_talking_head_activity_error(
            "Talking-head generation failed while polling HeyGen status.",
            exc=exc,
        )

    try:
        return await _store_talking_head_video(
            source_video_url=heygen_video_url,
            config=config,
            provider="heygen",
            provider_job_id_key="heygen_video_id",
            provider_job_id=video_id,
        )
    except Exception as exc:
        _raise_talking_head_activity_error(
            "Talking-head video storage failed after HeyGen completed.",
            exc=exc,
        )


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
# Scene Images Generation (Multi-source: Browser capture + AI fallback)
# ─────────────────────────────────────────────────────────────────────────────

# Source Type Decision Matrix:
# ┌─────────────────────────────┬──────────────┬─────────────────────────────────────────┐
# │ source_type                 │ has_source_ref │ Behavior                              │
# ├─────────────────────────────┼──────────────┼─────────────────────────────────────────┤
# │ public_page_capture         │ Yes          │ Browser capture, ERROR on fail         │
# │ public_page_capture         │ No           │ ERROR (non-retryable)                  │
# │ hybrid_candidate            │ Yes          │ Browser capture, AI FALLBACK on fail   │
# │ hybrid_candidate            │ No           │ AI visual directly                     │
# │ ai_visual_fallback          │ *            │ AI visual directly                     │
# │ uploaded_demo_video         │ Yes          │ Extract segment from video             │
# │ uploaded_demo_video         │ No           │ ERROR (non-retryable)                  │
# │ authenticated_capture_later │ Yes          │ Browser capture, ERROR on fail         │
# │ authenticated_capture_later │ No           │ ERROR (non-retryable)                  │
# └─────────────────────────────┴──────────────┴─────────────────────────────────────────┘

# Browser capture types that REQUIRE source_ref and have NO fallback
_STRICT_BROWSER_CAPTURE_TYPES = {
    "public_page_capture",
    "authenticated_capture_later",
}

# Hybrid type: tries browser first, falls back to AI on failure
_HYBRID_CAPTURE_TYPE = "hybrid_candidate"

# Pure AI generation types
_AI_FALLBACK_TYPES = {"ai_visual_fallback"}

# All browser-capable types (for error message grouping)
_BROWSER_CAPTURE_TYPES = _STRICT_BROWSER_CAPTURE_TYPES | {_HYBRID_CAPTURE_TYPE}

_ALL_SOURCE_TYPES = VALID_TOP_HALF_SOURCE_TYPES  # Use unified definition

# Minimum valid video file size (bytes)
_MIN_VIDEO_FILE_SIZE = 2000
_MIN_IMAGE_FILE_SIZE = 1000

# Default duration for AI visual videos (seconds)
_AI_VISUAL_VIDEO_DURATION_SEC = 5


async def _convert_image_to_video(
    image_url: str,
    scene_id: str,
    scene_metadata: Dict[str, Any],
    duration_sec: float = _AI_VISUAL_VIDEO_DURATION_SEC,
) -> Dict[str, Any]:
    """
    Convert a static image to a looping video for top-half compatibility.

    This ensures AI-generated images can be used in the video assembly pipeline
    which requires all top-half assets to be videos.

    Args:
        image_url: URL of the source image
        scene_id: Scene identifier for logging
        scene_metadata: Metadata for storage (campaign_id, user_id, etc.)
        duration_sec: Duration of the output video in seconds

    Returns:
        Dict with url, storage_url, storage_key, is_video=True, generation_method
    """
    import subprocess
    import tempfile
    from pathlib import Path

    # Known magic-byte prefixes for valid image formats
    _IMAGE_MAGIC = {
        b"\x89PNG": "PNG",
        b"\xff\xd8\xff": "JPEG",
        b"RIFF": "WEBP",  # RIFF....WEBP
        b"GIF8": "GIF",
    }

    ffmpeg_timeout_sec = _positive_int_env(
        "AI_VISUAL_VIDEO_FFMPEG_TIMEOUT_SEC",
        90,
    )
    ffmpeg_gate = _shared_async_semaphore(
        "AI_VISUAL_VIDEO_GLOBAL_CONCURRENCY",
        1,
    )

    logger.info(
        "Converting AI image to video | scene=%s | url=%s | duration=%ss",
        scene_id,
        image_url[:80] if image_url else "NONE",
        duration_sec,
    )

    tmp_dir = Path(tempfile.mkdtemp(prefix="ai_visual_video_"))
    image_path = tmp_dir / "input_image.png"
    video_output_path = tmp_dir / f"ai_visual_{scene_id}.mp4"

    try:
        # Download the AI-generated image
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_path.write_bytes(response.content)

        image_size = image_path.stat().st_size
        logger.debug(
            "Downloaded AI image | scene=%s | size_kb=%.1f",
            scene_id,
            image_size / 1024,
        )

        # Validate input image before invoking ffmpeg
        if image_size < _MIN_IMAGE_FILE_SIZE:
            raise ApplicationError(
                f"Scene {scene_id}: downloaded image too small ({image_size} bytes) — likely corrupt or empty",
                non_retryable=True,
            )

        header = image_path.read_bytes()[:8]
        detected_format = None
        for magic, fmt in _IMAGE_MAGIC.items():
            if header.startswith(magic):
                detected_format = fmt
                break
        if detected_format is None:
            logger.warning(
                "Unknown image format | scene=%s | header_hex=%s | size=%d",
                scene_id,
                header[:8].hex(),
                image_size,
            )
            # Don't hard-fail — ffmpeg may still handle it — but log for diagnostics

        # Convert image to video using ffmpeg
        # -loop 1: loop the input image
        # -i INPUT: input image
        # -t DURATION: output duration
        # -vf scale=...: scale to 1080x960 (top-half standard dimensions)
        # -c:v libx264: encode with h264
        # -pix_fmt yuv420p: pixel format for compatibility
        # -preset ultrafast + -threads 1: keep fallback encodes cheap under worker load
        # -crf 23: quality (default)
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-loop", "1",  # Loop the input image
            "-i", str(image_path),
            "-t", str(duration_sec),  # Duration in seconds
            "-vf", "scale=1080:960:force_original_aspect_ratio=decrease,pad=1080:960:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",  # Required for compatibility with most players
            "-crf", "23",
            "-movflags", "+faststart",
            "-an",  # No audio (top-half is silent)
            "-threads", "1",
            str(video_output_path),
        ]

        logger.debug(
            "Running ffmpeg for AI visual video | scene=%s | cmd=%s",
            scene_id,
            " ".join(ffmpeg_cmd),
        )

        try:
            async with ffmpeg_gate:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=ffmpeg_timeout_sec,
                )
        except subprocess.TimeoutExpired:
            logger.error(
                "ffmpeg image-to-video TIMED OUT | scene=%s | timeout=%ds | image_size=%d | duration=%s",
                scene_id,
                ffmpeg_timeout_sec,
                image_size,
                duration_sec,
            )
            raise ApplicationError(
                f"Scene {scene_id}: ffmpeg timed out after {ffmpeg_timeout_sec}s converting image to video "
                f"(image_size={image_size}, duration={duration_sec}s)",
                non_retryable=False,
            )

        if result.returncode != 0:
            error_output = result.stderr[-500:] if result.stderr else "no stderr"
            logger.error(
                "ffmpeg image-to-video failed | scene=%s | returncode=%s | stderr=%s",
                scene_id,
                result.returncode,
                error_output,
            )
            raise ApplicationError(
                f"Scene {scene_id}: ffmpeg failed to convert image to video (rc={result.returncode})",
                non_retryable=False,
            )

        if (
            not video_output_path.exists()
            or video_output_path.stat().st_size < _MIN_VIDEO_FILE_SIZE
        ):
            raise ApplicationError(
                f"Scene {scene_id}: converted video is too small or missing",
                non_retryable=False,
            )

        video_bytes = video_output_path.read_bytes()
        logger.info(
            "AI visual converted to video | scene=%s | size_mb=%.2f",
            scene_id,
            len(video_bytes) / (1024 * 1024),
        )

        # Upload to storage
        media_storage = MediaStorageService()
        campaign_id = scene_metadata.get("campaign_id")
        user_id = scene_metadata.get("user_id")
        owner_key = scene_metadata.get("owner_key")
        persona_id = scene_metadata.get("persona_id")

        storage_result = await media_storage.upload_bytes(
            data=video_bytes,
            content_type="video/mp4",
            asset_kind="video",
            asset_type="VIDEO",
            metadata={
                "source_type": "ai_visual_video",
                "scene_id": scene_id,
                "original_image_url": image_url[:500],  # Truncate long URLs
                "duration_sec": duration_sec,
                **scene_metadata,
            },
            campaign_id=str(campaign_id) if campaign_id else None,
            user_id=user_id,
            owner_key=owner_key,
            persona_id=persona_id,
            file_name_hint=f"ai_visual_video_{scene_id}",
        )

        if storage_result is None:
            raise ApplicationError(
                f"Scene {scene_id}: failed to upload AI visual video",
                non_retryable=False,
            )

        logger.info(
            "AI visual video uploaded | scene=%s | storage_url=%s | media_asset_id=%s",
            scene_id,
            storage_result.get("url", "")[:80],
            storage_result.get("media_asset_id"),
        )

        return {
            "url": storage_result.get("url"),
            "storage_url": storage_result.get("storage_url")
            or storage_result.get("access_url")
            or storage_result.get("url"),
            "storage_key": storage_result.get("storage_key")
            or storage_result.get("storage_path")
            or storage_result.get("key"),
            "media_asset_id": storage_result.get("media_asset_id"),
            "is_video": True,  # Now it's a video!
            "generation_method": "ai_visual_video",
        }

    finally:
        # Cleanup temp files
        try:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as cleanup_exc:
            logger.warning(
                "Failed to cleanup temp dir for AI visual video scene %s: %s",
                scene_id,
                cleanup_exc,
            )


async def _generate_ai_visual(
    scene: Dict[str, Any],
    scene_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate an AI visual for a scene using fal.ai and convert to video.

    Uses top_half_target and top_half_capture_hint to build a contextual prompt.
    The generated image is converted to a short video for top-half compatibility.
    Returns storage result dict with url, storage_key, is_video=True, etc.
    """
    scene_id = scene.get("id", "unknown")
    top_half_target = scene.get("top_half_target", "")
    capture_hint = scene.get("top_half_capture_hint", "")
    image_prompt = scene.get("image_prompt") or scene.get("prompt", "")
    # Get duration from scene for video length, default to 5 seconds
    duration_sec = float(scene.get("duration_sec") or scene.get("duration") or _AI_VISUAL_VIDEO_DURATION_SEC)

    # Build an enriched prompt from available context
    prompt_parts = []
    if top_half_target:
        prompt_parts.append(f"Scene depicting: {top_half_target}")
    if capture_hint and capture_hint not in {"scroll", "static", "none"}:
        prompt_parts.append(f"Visual style: {capture_hint}")
    if image_prompt:
        prompt_parts.append(image_prompt)

    if not prompt_parts:
        prompt_parts.append(
            "Modern app interface screenshot, clean UI design, professional look"
        )

    final_prompt = ". ".join(prompt_parts)

    logger.info(
        "Generating AI visual | scene=%s | prompt=%s",
        scene_id,
        final_prompt[:100],
    )

    image_service = ImageGenerationService()

    try:
        result = await image_service.generate_images(
            prompt=final_prompt,
            model="fal-ai/flux-pro",
            aspect_ratio="9:8",  # Top-half aspect ratio
            safety_tolerance=2,
            num_images=1,
            campaign_id=scene_metadata.get("campaign_id"),
            user_id=scene_metadata.get("user_id"),
            owner_key=scene_metadata.get("owner_key"),
            persona_id=scene_metadata.get("persona_id"),
            metadata=scene_metadata,
            file_name_hint=f"ai-visual-scene-{scene_id}",
        )

        if not result or not result.get("images"):
            raise RuntimeError(
                f"AI image generation returned no images for scene {scene_id}"
            )

        image_data = result["images"][0]
        image_url = image_data.get("url") or image_data.get("storage_url")

        if not image_url:
            raise RuntimeError(
                f"AI image generation returned no URL for scene {scene_id}"
            )

        logger.info(
            "AI image generated, converting to video | scene=%s | image_url=%s",
            scene_id,
            image_url[:80],
        )

        # Convert static image to video for top-half compatibility
        video_result = await _convert_image_to_video(
            image_url=image_url,
            scene_id=scene_id,
            scene_metadata=scene_metadata,
            duration_sec=duration_sec,
        )

        # Preserve original image info in result
        video_result["original_image_url"] = image_url
        video_result["original_image_storage_key"] = image_data.get("storage_key")
        video_result["original_image_media_asset_id"] = image_data.get("media_asset_id")

        logger.info(
            "AI visual video ready | scene=%s | video_url=%s | is_video=%s",
            scene_id,
            video_result.get("url", "")[:80],
            video_result.get("is_video"),
        )

        return video_result

    except Exception as e:
        logger.error(
            "AI visual generation FAILED | scene=%s | error=%s",
            scene_id,
            str(e)[:200],
        )
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Pre-Capture URL Validation
# ─────────────────────────────────────────────────────────────────────────────

# Known domains with aggressive bot detection
_BOT_DETECTION_DOMAINS = {
    "linkedin.com",
    "facebook.com", 
    "instagram.com",
    "twitter.com",
    "x.com",
    "cloudflare.com",
}

# Patterns in URL that suggest auth is required
_AUTH_PATTERNS = {
    "/login",
    "/signin",
    "/auth",
    "/account",
    "/dashboard",
    "/admin",
    "/my-",
    "/private",
}


async def _pre_validate_url(url: str, timeout_seconds: float = 10.0) -> Dict[str, Any]:
    """
    Pre-capture URL validation to detect potential issues before browser capture.
    
    Checks:
    - URL is accessible (HEAD request)
    - Known bot-detection domains
    - Auth-required URL patterns
    - robots.txt blocking
    
    Returns:
        Dict with validation results: accessible, has_bot_detection, requires_auth, robots_blocked
    """
    from urllib.parse import urlparse
    
    result = {
        "url": url,
        "accessible": False,
        "status_code": None,
        "has_bot_detection": False,
        "requires_auth": False,
        "robots_blocked": False,
        "validation_error": None,
    }
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = (parsed.path or "/").lower()
        
        # Check for known bot-detection domains
        for bot_domain in _BOT_DETECTION_DOMAINS:
            if bot_domain in domain:
                result["has_bot_detection"] = True
                logger.warning(
                    "URL may have bot detection | url=%s | domain=%s",
                    url[:60],
                    bot_domain,
                )
                break
        
        # Check for auth-required patterns
        for auth_pattern in _AUTH_PATTERNS:
            if auth_pattern in path:
                result["requires_auth"] = True
                logger.warning(
                    "URL may require authentication | url=%s | pattern=%s",
                    url[:60],
                    auth_pattern,
                )
                break
        
        # HEAD request to check accessibility
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            try:
                response = await client.head(url)
                result["status_code"] = response.status_code
                result["accessible"] = 200 <= response.status_code < 400
                
                if not result["accessible"]:
                    logger.warning(
                        "URL returned non-success status | url=%s | status=%d",
                        url[:60],
                        response.status_code,
                    )
            except httpx.HTTPError as http_err:
                result["validation_error"] = f"HTTP error: {str(http_err)[:100]}"
                logger.warning(
                    "URL validation HTTP error | url=%s | error=%s",
                    url[:60],
                    result["validation_error"],
                )
        
        # Quick robots.txt check (non-blocking)
        try:
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            async with httpx.AsyncClient(timeout=5.0) as client:
                robots_resp = await client.get(robots_url)
                if robots_resp.status_code == 200:
                    robots_text = robots_resp.text.lower()
                    # Check if user-agent * is disallowed for the path
                    if "disallow: /" in robots_text and path != "/":
                        result["robots_blocked"] = True
                        logger.info(
                            "URL may be blocked by robots.txt | url=%s",
                            url[:60],
                        )
        except Exception:
            pass  # robots.txt check is best-effort
            
    except Exception as e:
        result["validation_error"] = str(e)[:200]
        logger.warning(
            "URL pre-validation failed | url=%s | error=%s",
            url[:60],
            result["validation_error"],
        )
    
    return result


async def _capture_with_retry(
    browser,
    source_ref: str,
    capture_hint: str,
    target_selector: str,
    action_text: str,
    visual_success_criteria: str,
    max_capture_seconds: int,
    follow_relevant_links: bool,
    scene_duration_sec: float,
    scene_id: str,
    max_attempts: int = 3,
) -> tuple:
    """
    Multi-attempt capture with progressive fallback strategy.
    
    Attempt 1: Normal capture with all features
    Attempt 2: 1.5x timeout, disable warmup, reduce link following
    Attempt 3: Static mode only, minimal features
    
    Returns:
        Tuple of (video_path, capture_metrics)
    """
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Adjust parameters based on attempt number
            if attempt == 1:
                # Normal capture
                attempt_hint = capture_hint
                attempt_max_seconds = max_capture_seconds
                attempt_follow_links = follow_relevant_links
                attempt_warmup_enabled = True
            elif attempt == 2:
                # Extended timeout, reduced features
                attempt_hint = capture_hint if capture_hint != "deep" else "scroll"
                attempt_max_seconds = min(60, int(max_capture_seconds * 1.5))
                attempt_follow_links = False
                attempt_warmup_enabled = False
                logger.info(
                    "Retry attempt 2 | scene=%s | extended_timeout=%d | no_link_follow | warmup=%s",
                    scene_id,
                    attempt_max_seconds,
                    attempt_warmup_enabled,
                )
            else:
                # Static mode fallback
                attempt_hint = "static"
                attempt_max_seconds = min(60, max(10, max_capture_seconds))
                attempt_follow_links = False
                attempt_warmup_enabled = False
                logger.info(
                    "Retry attempt 3 | scene=%s | static_mode | timeout=%d | warmup=%s",
                    scene_id,
                    attempt_max_seconds,
                    attempt_warmup_enabled,
                )
            
            result = await browser.record_video_for_tutorial(
                source_ref,
                capture_hint=attempt_hint,
                target_selector=target_selector,
                action_text=action_text,
                visual_success_criteria=visual_success_criteria,
                viewport_width=1080,
                viewport_height=960,
                max_capture_seconds=attempt_max_seconds,
                follow_relevant_links=attempt_follow_links,
                scene_duration_sec=scene_duration_sec,
                warmup_enabled=attempt_warmup_enabled,
            )
            
            # Handle both old (string) and new (tuple) return types
            if isinstance(result, tuple):
                video_path, capture_metrics = result
            else:
                video_path = result
                capture_metrics = None
            
            if video_path and os.path.exists(video_path):
                # Do not gate on file size here: Playwright may finalize bytes only
                # after the browser context is closed by the caller.
                file_size = os.path.getsize(video_path)
                if attempt > 1:
                    logger.info(
                        "Capture succeeded on attempt %d | scene=%s | pre-close_size=%d",
                        attempt,
                        scene_id,
                        file_size,
                    )
                return video_path, capture_metrics
            else:
                raise RuntimeError("Capture did not produce a video file")
                
        except Exception as e:
            last_error = e
            logger.warning(
                "Capture attempt %d failed | scene=%s | error=%s",
                attempt,
                scene_id,
                str(e)[:200],
            )
            
            if attempt < max_attempts:
                # Brief pause before retry
                await asyncio.sleep(1.0)
    
    # All attempts failed
    raise RuntimeError(
        f"All {max_attempts} capture attempts failed for scene {scene_id}. Last error: {last_error}"
    )


async def _capture_browser_video(
    scene: Dict[str, Any],
    scene_metadata: Dict[str, Any],
    source_ref: str,
) -> Dict[str, Any]:
    """
    Capture a browser recording for a scene using Playwright.

    Includes:
    - Pre-capture URL validation (accessibility, bot detection, auth patterns)
    - Multi-attempt capture with progressive fallback
    - Adaptive capture duration based on scene timestamps

    Returns storage result dict with url, storage_key, capture_metrics, etc.
    Raises on failure (caller handles fallback).
    """
    import time as _time
    from urllib.parse import urlparse as _urlparse
    
    scene_id = scene.get("id", "unknown")
    browser = None
    local_capture_metrics = None
    url_validation = None
    capture_start_time = _time.monotonic()
    
    # Extract domain for metrics tracking
    try:
        domain = _urlparse(source_ref).netloc.lower()
    except Exception:
        domain = "unknown"

    browser_service_class = BrowserAutomationService
    if browser_service_class is None and browser_automation_module is not None:
        browser_service_class = browser_automation_module.BrowserAutomationService
    if browser_service_class is None:
        raise RuntimeError(
            "Browser automation dependencies are not installed in this runtime image."
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # PRE-CAPTURE URL VALIDATION
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        url_validation = await _pre_validate_url(source_ref, timeout_seconds=10.0)
        logger.info(
            "URL pre-validation | scene=%s | accessible=%s | bot_detection=%s | requires_auth=%s | robots_blocked=%s",
            scene_id,
            url_validation.get("accessible"),
            url_validation.get("has_bot_detection"),
            url_validation.get("requires_auth"),
            url_validation.get("robots_blocked"),
        )
        
        # Warn but don't fail - let capture attempt proceed
        if url_validation.get("has_bot_detection"):
            logger.warning(
                "URL has known bot detection; capture may fail | scene=%s | url=%s",
                scene_id,
                source_ref[:60],
            )
    except Exception as val_err:
        logger.warning(
            "URL pre-validation error (non-fatal) | scene=%s | error=%s",
            scene_id,
            str(val_err)[:100],
        )
        url_validation = {"validation_error": str(val_err)[:100]}

    os.makedirs("/tmp/tutorials_videos", exist_ok=True)

    # Inject region and proxy to avoid being blocked (white screen)
    region_info = None
    proxy_config = None
    user_id = scene_metadata.get("user_id") or scene_metadata.get("uid")

    # Determine platform for viewport (mobile vs desktop)
    platform_hint = "generic"
    video_format = scene_metadata.get("video_format", "").lower()
    if (
        "tiktok" in str(scene_metadata.get("platform", "")).lower()
        or "portrait" in video_format
        or "9:16" in video_format
    ):
        platform_hint = "tiktok"

    try:
        from services.region_service import RegionService
        from services.proxy_manager_service import ProxyManagerService

        region_info = await RegionService().build_region_profile()

        if user_id:
            try:
                lease = await ProxyManagerService.lease_proxy(
                    account_key=str(user_id),
                    platform="generic",
                    include_credentials=True,
                )
                proxy_config = lease.get("proxy")
                logger.info(
                    f"Leased proxy for capture | user_id={user_id} | server={proxy_config.get('server')}"
                )
            except Exception as pe:
                logger.warning(
                    f"Failed to lease proxy for capture: {pe}. Proceeding without proxy."
                )
    except ImportError:
        logger.warning("Region/Proxy services not available. Proceeding with defaults.")

    try:
        capture_hint = scene.get("top_half_capture_hint", "scroll")
        target_selector = scene.get("top_half_target")
        action_text = str(scene.get("browser_action") or scene.get("prompt") or "").strip()
        visual_success_criteria = str(scene.get("visual_success_criteria") or "").strip()
        base_max_capture_seconds = (
            scene.get("top_half_max_capture_seconds")
            or scene_metadata.get("top_half_max_capture_seconds")
            or 60
        )
        follow_relevant_links = scene.get("top_half_follow_links")
        if follow_relevant_links is None:
            follow_relevant_links = scene_metadata.get("top_half_follow_links")
        if follow_relevant_links is None:
            follow_relevant_links = True

        # ═══════════════════════════════════════════════════════════════════════════
        # ADAPTIVE CAPTURE DURATION
        # ═══════════════════════════════════════════════════════════════════════════
        # Use scene timestamps to calculate exact needed duration with buffer.
        # CRITICAL: Assembly skips the first 8 seconds (TOP_SCENE_SKIP_SECONDS) to
        # exclude blank page loading frames. We must capture enough footage so that
        # scene_duration remains AFTER the 8-second skip.
        ASSEMBLY_SKIP_SECONDS = 8.0
        scene_duration_sec = None
        ts_start = scene.get("timestamp_start")
        ts_end = scene.get("timestamp_end")
        if ts_start is not None and ts_end is not None:
            scene_duration_sec = float(ts_end) - float(ts_start)
        
        # Calculate adaptive max_capture_seconds
        # Formula: 8s (skip) + scene_duration + 2s (buffer)
        if scene_duration_sec and scene_duration_sec > 0:
            adaptive_duration = ASSEMBLY_SKIP_SECONDS + scene_duration_sec + 2.0
            # Don't exceed base max
            adaptive_duration = min(adaptive_duration, float(base_max_capture_seconds))
            max_capture_seconds = max(8, int(adaptive_duration))
            logger.info(
                "Adaptive capture duration | scene=%s | scene_duration=%.1f | capture_budget=%d (includes %ds skip buffer)",
                scene_id,
                scene_duration_sec,
                max_capture_seconds,
                int(ASSEMBLY_SKIP_SECONDS),
            )
        else:
            max_capture_seconds = int(base_max_capture_seconds)

        logger.info(
            "Starting browser capture | scene=%s | url=%s | hint=%s | target=%s | platform=%s | max_seconds=%s | scene_duration=%s | url_validation=%s",
            scene_id,
            source_ref[:60],
            capture_hint,
            target_selector,
            platform_hint,
            max_capture_seconds,
            scene_duration_sec,
            url_validation.get("accessible") if url_validation else "skipped",
        )

        def _is_http_response_capture_error(exc: Exception) -> bool:
            text = str(exc or "").lower()
            return any(
                token in text
                for token in [
                    "err_http_response_code_failure",
                    "access denied",
                    "forbidden",
                    "challenge",
                    "captcha",
                ]
            )

        async def _run_capture_session(active_proxy_config):
            nonlocal browser, local_capture_metrics
            browser = browser_service_class()
            logger.info(
                "Initializing browser capture session | scene=%s | proxy_enabled=%s | proxy_server=%s | region=%s | platform=%s",
                scene_id,
                bool(active_proxy_config),
                (active_proxy_config or {}).get("server"),
                (region_info or {}).get("countryCode") or (region_info or {}).get("country"),
                platform_hint,
            )
            await browser.initialize_browser(
                record_video_dir="/tmp/tutorials_videos",
                record_video_size={"width": 1080, "height": 960},
                region_info=region_info,
                proxy_config=active_proxy_config,
                platform=platform_hint,
            )

            video_path, local_capture_metrics = await _capture_with_retry(
                browser=browser,
                source_ref=source_ref,
                capture_hint=capture_hint,
                target_selector=target_selector,
                action_text=action_text,
                visual_success_criteria=visual_success_criteria,
                max_capture_seconds=max_capture_seconds,
                follow_relevant_links=follow_relevant_links,
                scene_duration_sec=scene_duration_sec,
                scene_id=scene_id,
                max_attempts=3,
            )

            await browser.close()
            browser = None
            return video_path

        # ═══════════════════════════════════════════════════════════════════════════
        # MULTI-ATTEMPT CAPTURE WITH RETRY
        # ═══════════════════════════════════════════════════════════════════════════
        try:
            video_path = await _run_capture_session(proxy_config)
        except Exception as capture_err:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
                finally:
                    browser = None

            if proxy_config and _is_http_response_capture_error(capture_err):
                logger.warning(
                    "Browser capture failed with proxy-enabled session; retrying once without proxy | scene=%s | url=%s | proxy_server=%s | error=%s",
                    scene_id,
                    source_ref[:80],
                    proxy_config.get("server"),
                    str(capture_err)[:200],
                )
                try:
                    video_path = await _run_capture_session(None)
                except Exception as fallback_err:
                    raise RuntimeError(
                        f"{fallback_err} | capture_context=proxy_retry_failed proxy_enabled_initial=True proxy_server={proxy_config.get('server')}"
                    ) from fallback_err
            else:
                raise

        if not video_path or not os.path.exists(video_path):
            raise RuntimeError(
                f"Playwright recording did not produce a video file for scene {scene_id}"
            )

        # IMPROVED FILE STABILIZATION: Exponential backoff + size stability check
        # Wait until file size stops growing for 2 consecutive checks
        stabilization_start = _time.monotonic()
        max_stabilization_wait = 60.0  # Max 60 seconds (up from 30s)
        check_interval = 0.5  # Start with 0.5s checks
        max_interval = 2.0  # Max 2s between checks
        consecutive_stable = 0
        required_stable_checks = 2
        last_size = 0
        iteration = 0
        
        while (_time.monotonic() - stabilization_start) < max_stabilization_wait:
            iteration += 1
            if not os.path.exists(video_path):
                await asyncio.sleep(check_interval)
                continue
            
            current_size = os.path.getsize(video_path)
            
            if current_size >= _MIN_VIDEO_FILE_SIZE:
                if current_size == last_size:
                    consecutive_stable += 1
                    if consecutive_stable >= required_stable_checks:
                        logger.info(
                            "File stabilized | scene=%s | size=%d | iterations=%d | wait_ms=%d",
                            scene_id,
                            current_size,
                            iteration,
                            int((_time.monotonic() - stabilization_start) * 1000),
                        )
                        break
                else:
                    consecutive_stable = 0
            
            last_size = current_size
            await asyncio.sleep(check_interval)
            # Exponential backoff: increase interval up to max
            check_interval = min(check_interval * 1.5, max_interval)
        
        stabilization_wait_ms = int((_time.monotonic() - stabilization_start) * 1000)

        # Validate file size
        file_size = os.path.getsize(video_path)
        if file_size < _MIN_VIDEO_FILE_SIZE:
            raise RuntimeError(
                f"Browser capture produced an invalid/tiny file ({file_size} bytes) for scene {scene_id} after {stabilization_wait_ms}ms wait"
            )

        with open(video_path, "rb") as f:
            data = f.read()

        if len(data) < 1024:
            raise RuntimeError(
                f"Playwright recording is too small for scene {scene_id}: {len(data)} bytes"
            )

        # Upload to storage
        media_storage_service_class = MediaStorageService
        if media_storage_service_class is _DEFAULT_MEDIA_STORAGE_SERVICE_CLASS:
            media_storage_service_class = (
                media_storage_service_module.MediaStorageService
            )
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

        # Build metrics dict for logging
        metrics_dict = local_capture_metrics.to_dict() if local_capture_metrics else {}
        metrics_dict["stabilization_wait_ms"] = stabilization_wait_ms
        metrics_dict["final_file_size_bytes"] = file_size
        
        # Calculate total capture duration
        capture_duration_sec = _time.monotonic() - capture_start_time

        # ═══════════════════════════════════════════════════════════════════════════
        # RECORD METRICS (SUCCESS)
        # ═══════════════════════════════════════════════════════════════════════════
        if _METRICS_AVAILABLE and capture_metrics is not None:
            capture_metrics.record_capture(
                success=True,
                domain=domain,
                duration_sec=capture_duration_sec,
                file_size_bytes=file_size,
                fallback_used=False,
            )
        if _METRICS_AVAILABLE and domain_tracker is not None:
            try:
                await domain_tracker.record_attempt(source_ref, success=True)
            except Exception as track_err:
                logger.debug("Domain tracking failed (non-fatal): %s", track_err)

        logger.info(
            "Browser capture completed | scene=%s | url=%s | file_size=%d | stabilization_ms=%d | duration_sec=%.1f | metrics=%s",
            scene_id,
            final_url[:80],
            file_size,
            stabilization_wait_ms,
            capture_duration_sec,
            metrics_dict,
        )

        return {
            "url": final_url,
            "storage_url": storage_result.get("storage_url"),
            "storage_key": storage_result.get("storage_key"),
            "media_asset_id": storage_result.get("media_asset_id"),
            "is_video": True,
            "generation_method": "browser_capture",
            "capture_metrics": metrics_dict,
            "url_validation": url_validation,
        }
    except Exception as capture_exc:
        # ═══════════════════════════════════════════════════════════════════════════
        # RECORD METRICS (FAILURE)
        # ═══════════════════════════════════════════════════════════════════════════
        capture_duration_sec = _time.monotonic() - capture_start_time
        error_type = type(capture_exc).__name__
        
        if _METRICS_AVAILABLE and capture_metrics is not None:
            capture_metrics.record_capture(
                success=False,
                domain=domain,
                duration_sec=capture_duration_sec,
                file_size_bytes=0,
                fallback_used=False,
                error_type=error_type,
            )
        if _METRICS_AVAILABLE and domain_tracker is not None:
            try:
                await domain_tracker.record_attempt(source_ref, success=False)
            except Exception as track_err:
                logger.debug("Domain tracking failed (non-fatal): %s", track_err)
        
        # Re-raise the original exception
        raise
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


async def _extract_uploaded_demo_segment(
    scene: Dict[str, Any],
    scene_metadata: Dict[str, Any],
    source_ref: str,
) -> Dict[str, Any]:
    """
    Extract a segment from an uploaded demo video using timestamp range.

    Args:
        scene: Scene dict with top_half_target (timestamp range: "HH:MM:SS-HH:MM:SS")
        scene_metadata: Metadata for storage (campaign_id, user_id, etc.)
        source_ref: URL to the uploaded demo video

    Returns:
        Dict with url, storage_url, storage_key, is_video, generation_method
    """
    import subprocess
    import tempfile
    from pathlib import Path

    scene_id = scene.get("id", "unknown")
    top_half_target = scene.get("top_half_target", "")
    trim_confidence = scene.get("trim_confidence")

    logger.info(
        "Extracting demo segment | scene=%s | target=%s | trim_confidence=%s",
        scene_id,
        top_half_target,
        trim_confidence,
    )

    # Parse timestamp range
    if not top_half_target or "-" not in top_half_target:
        raise ApplicationError(
            f"Scene {scene_id}: invalid timestamp range '{top_half_target}' for uploaded_demo_video",
            non_retryable=True,
        )

    try:
        start_str, end_str = top_half_target.split("-", 1)
        start_str = start_str.strip()
        end_str = end_str.strip()
    except ValueError:
        raise ApplicationError(
            f"Scene {scene_id}: cannot parse timestamp range '{top_half_target}'",
            non_retryable=True,
        )

    # Phase 8: Explicit trim confidence handling per policy
    # >= 0.8: normal, 0.5-0.79: caution, < 0.5: conservative_hold
    if trim_confidence is not None:
        if trim_confidence >= 0.8:
            logger.info(
                "Scene %s trim_confidence=%.2f (normal) - proceeding with trim",
                scene_id,
                trim_confidence,
            )
        elif trim_confidence >= 0.5:
            logger.warning(
                "Scene %s trim_confidence=%.2f (caution) - segment boundaries may be approximate",
                scene_id,
                trim_confidence,
            )
        else:
            # < 0.5: conservative_hold - use conservative window, do not auto-fallback
            logger.warning(
                "Scene %s trim_confidence=%.2f (conservative_hold) - using conservative boundaries, may not be precise",
                scene_id,
                trim_confidence,
            )

    # Download demo video
    tmp_dir = Path(tempfile.mkdtemp(prefix="demo_segment_"))
    demo_video_path = tmp_dir / "demo_video.mp4"
    segment_output_path = tmp_dir / f"segment_{scene_id}.mp4"

    try:
        logger.info(
            "Downloading demo video | scene=%s | url=%s", scene_id, source_ref[:80]
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(source_ref)
            response.raise_for_status()
            demo_video_path.write_bytes(response.content)

        logger.info(
            "Downloaded demo video | scene=%s | size_mb=%.2f",
            scene_id,
            demo_video_path.stat().st_size / (1024 * 1024),
        )

        # Extract segment using ffmpeg
        # -ss START: seek to start time
        # -to END: extract until end time
        # -i INPUT: input file
        # -vf scale=...: scale to 1080x960 (top-half standard dimensions)
        # -c:v libx264: re-encode with h264
        # -preset fast: encoding speed
        # -crf 23: quality (lower = better, 23 is default)
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-ss",
            start_str,
            "-to",
            end_str,
            "-i",
            str(demo_video_path),
            "-vf",
            "scale=1080:960:force_original_aspect_ratio=decrease,pad=1080:960:(ow-iw)/2:(oh-ih)/2",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-an",  # No audio (top-half is silent)
            str(segment_output_path),
        ]

        logger.info(
            "Extracting segment | scene=%s | start=%s | end=%s",
            scene_id,
            start_str,
            end_str,
        )

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            error_output = result.stderr[-500:] if result.stderr else "no stderr"
            logger.error(
                "ffmpeg trim failed | scene=%s | returncode=%s | stderr=%s",
                scene_id,
                result.returncode,
                error_output,
            )
            raise ApplicationError(
                f"Scene {scene_id}: ffmpeg failed to extract segment (rc={result.returncode})",
                non_retryable=False,
            )

        if (
            not segment_output_path.exists()
            or segment_output_path.stat().st_size < _MIN_VIDEO_FILE_SIZE
        ):
            raise ApplicationError(
                f"Scene {scene_id}: extracted segment is too small or missing",
                non_retryable=False,
            )

        segment_bytes = segment_output_path.read_bytes()
        logger.info(
            "Segment extracted | scene=%s | size_mb=%.2f",
            scene_id,
            len(segment_bytes) / (1024 * 1024),
        )

        # Upload to storage
        media_storage = MediaStorageService()
        campaign_id = scene_metadata.get("campaign_id")
        user_id = scene_metadata.get("user_id")
        owner_key = scene_metadata.get("owner_key")
        persona_id = scene_metadata.get("persona_id")

        storage_result = await media_storage.upload_bytes(
            data=segment_bytes,
            content_type="video/mp4",
            asset_kind="video",
            asset_type="VIDEO",
            metadata={
                "source_type": "uploaded_demo_video",
                "scene_id": scene_id,
                "timestamp_range": top_half_target,
                "trim_confidence": trim_confidence,
                **scene_metadata,
            },
            campaign_id=str(campaign_id) if campaign_id else None,
            user_id=user_id,
            owner_key=owner_key,
            persona_id=persona_id,
            file_name_hint=f"demo_segment_{scene_id}",
        )

        if storage_result is None:
            raise ApplicationError(
                f"Scene {scene_id}: failed to upload extracted demo segment",
                non_retryable=False,
            )

        logger.info(
            "Segment uploaded | scene=%s | storage_url=%s | media_asset_id=%s",
            scene_id,
            storage_result.get("url", "")[:80],
            storage_result.get("media_asset_id"),
        )

        return {
            "url": storage_result.get("url"),
            "storage_url": storage_result.get("storage_url")
            or storage_result.get("access_url")
            or storage_result.get("url"),
            "storage_key": storage_result.get("storage_key")
            or storage_result.get("storage_path")
            or storage_result.get("key"),
            "media_asset_id": storage_result.get("media_asset_id"),
            "is_video": True,
            "generation_method": "uploaded_demo_segment",
        }

    finally:
        # Cleanup temp files
        try:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as cleanup_exc:
            logger.warning(
                "Failed to cleanup temp dir for scene %s: %s",
                scene_id,
                cleanup_exc,
            )


@activity.defn
async def generate_scene_images(scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate top-half scene assets using the appropriate method per scene.

    Supports multiple source types:
    - public_page_capture: Browser recording via Playwright
    - ai_visual_fallback: AI image generation via fal.ai
    - hybrid_candidate: Try browser first, fall back to AI on failure
    - uploaded_demo_video: Extract segment from uploaded demo video (Phase 7)
    """

    raw_limit = os.getenv("TOP_HALF_CAPTURE_CONCURRENCY", "2")
    try:
        max_parallel = max(1, int(raw_limit))
    except ValueError:
        max_parallel = 2
    semaphore = asyncio.Semaphore(max_parallel)
    browser_capture_gate = _shared_async_semaphore(
        "TOP_HALF_BROWSER_GLOBAL_CONCURRENCY",
        2,
    )
    browser_capture_ai_fallback_enabled = _truthy_env(
        "TOP_HALF_BROWSER_ALLOW_AI_FALLBACK",
        _truthy_env("TOP_HALF_STRICT_ALLOW_AI_FALLBACK", False),
    )

    async def gen_one(scene: dict) -> dict:
        async with semaphore:
            scene_metadata = dict(scene.get("metadata") or {})
            raw_top_half_type = scene.get("top_half_source_type")
            resolved_top_half_type = resolve_top_half_source_type(
                raw_top_half_type, logger, scene
            )
            normalized_scene = normalize_unknown_source_type_beat(
                {
                    **scene,
                    "raw_top_half_source_type": raw_top_half_type,
                    "top_half_source_type": resolved_top_half_type,
                }
            )
            top_half_type = normalized_scene.get("top_half_source_type")
            source_ref = normalized_scene.get("source_ref")
            scene_id = normalized_scene.get("id", "unknown")

            logger.info(
                "Processing scene | id=%s | raw_type=%s | resolved_type=%s | has_source_ref=%s",
                scene_id,
                raw_top_half_type,
                top_half_type,
                bool(source_ref),
            )

            # Route to appropriate generation method using decision matrix
            result = None
            fallback_triggered = False
            browser_error = None
            
            try:
                # ═══════════════════════════════════════════════════════════════
                # SOURCE TYPE DECISION MATRIX
                # ═══════════════════════════════════════════════════════════════
                
                if top_half_type == "uploaded_demo_video":
                    # uploaded_demo_video: Extract segment from uploaded demo video
                    # Requires source_ref (demo video URL)
                    if not source_ref:
                        raise ApplicationError(
                            f"Scene {scene_id} requires source_ref (demo video URL) for uploaded_demo_video type",
                            non_retryable=True,
                        )
                    result = await _extract_uploaded_demo_segment(
                        normalized_scene, scene_metadata, source_ref
                    )

                elif top_half_type in _AI_FALLBACK_TYPES:
                    # ai_visual_fallback: Pure AI generation (no browser attempt)
                    result = await _generate_ai_visual(normalized_scene, scene_metadata)

                elif top_half_type == _HYBRID_CAPTURE_TYPE:
                    # hybrid_candidate: Browser capture WITH AI fallback on failure
                    if not source_ref:
                        # No URL → use AI directly (not an error)
                        logger.info(
                            "hybrid_candidate scene %s has no source_ref, using AI visual directly",
                            scene_id,
                        )
                        result = await _generate_ai_visual(
                            normalized_scene, scene_metadata
                        )
                    else:
                        # Has URL → try browser; AI fallback is opt-in only.
                        try:
                            async with browser_capture_gate:
                                result = await _capture_browser_video(
                                    normalized_scene, scene_metadata, source_ref
                                )
                        except Exception as capture_err:
                            if not browser_capture_ai_fallback_enabled:
                                raise
                            browser_error = str(capture_err)[:300]
                            fallback_triggered = True
                            logger.warning(
                                "hybrid_candidate browser capture failed, falling back to AI | scene=%s | error=%s",
                                scene_id,
                                browser_error,
                            )
                            # Record fallback in metrics
                            if _METRICS_AVAILABLE and capture_metrics is not None:
                                # Note: The failure itself was already recorded in _capture_browser_video
                                # Here we just note that this triggered a fallback (can be useful for tracking)
                                capture_metrics.fallback_used += 1
                            result = await _generate_ai_visual(
                                normalized_scene, scene_metadata
                            )
                            result["fallback_triggered"] = True
                            result["browser_error"] = browser_error

                elif top_half_type in _STRICT_BROWSER_CAPTURE_TYPES:
                    # public_page_capture / authenticated_capture_later:
                    # Browser capture required by default; AI fallback is opt-in only.
                    if not source_ref:
                        raise ApplicationError(
                            f"Scene {scene_id} requires source_ref for browser capture (type={top_half_type})",
                            non_retryable=True,
                        )
                    try:
                        async with browser_capture_gate:
                            result = await _capture_browser_video(
                                normalized_scene, scene_metadata, source_ref
                            )
                    except Exception as capture_err:
                        if not browser_capture_ai_fallback_enabled:
                            raise
                        browser_error = str(capture_err)[:300]
                        fallback_triggered = True
                        logger.warning(
                            "strict browser capture failed, falling back to AI visual | scene=%s | type=%s | error=%s",
                            scene_id,
                            top_half_type,
                            browser_error,
                        )
                        if _METRICS_AVAILABLE and capture_metrics is not None:
                            capture_metrics.fallback_used += 1
                        result = await _generate_ai_visual(normalized_scene, scene_metadata)
                        result["fallback_triggered"] = True
                        result["browser_error"] = browser_error
                        result["fallback_from_type"] = top_half_type

                else:
                    # Unknown type - log error and fail
                    logger.error(
                        "Unhandled normalized top_half_source_type=%s for scene %s - cannot generate asset",
                        top_half_type,
                        scene_id,
                    )
                    raise ApplicationError(
                        f"Scene {scene_id} has unsupported normalized top_half_source_type={top_half_type}",
                        non_retryable=True,
                    )

                # Build final scene result
                final_url = result.get("url") or result.get("storage_url")

                logger.info(
                    "Scene asset resolved | scene=%s | type=%s | method=%s | url=%s | is_video=%s | fallback_triggered=%s",
                    scene_id,
                    top_half_type,
                    result.get("generation_method"),
                    final_url[:80] if final_url else "NONE",
                    result.get("is_video", False),
                    fallback_triggered,
                )

                return {
                    **normalized_scene,
                    "image_url": final_url,
                    "source_image_url": final_url,
                    "storage_image_url": result.get("storage_url"),
                    "image_storage_key": result.get("storage_key"),
                    "media_asset_id": result.get("media_asset_id"),
                    "status": "completed",
                    "is_video": result.get("is_video", False),
                    "generation_method": result.get("generation_method"),
                    "fallback_triggered": fallback_triggered,
                    "browser_error": browser_error,
                    "capture_metrics": result.get("capture_metrics"),
                }

            except ApplicationError:
                raise
            except Exception as e:
                logger.error(
                    "Scene generation FAILED | scene=%s | type=%s | error_type=%s | error=%s",
                    scene_id,
                    top_half_type,
                    type(e).__name__,
                    str(e)[:300],
                )
                # Only strict browser types should raise as browser failures
                if top_half_type in _STRICT_BROWSER_CAPTURE_TYPES:
                    raise ApplicationError(
                        f"Playwright top-half recording failed for scene {scene_id}: {e}",
                        non_retryable=not getattr(e, "retryable", False),
                    )
                raise ApplicationError(
                    f"Top-half generation failed for scene {scene_id}: {e}",
                    non_retryable=not getattr(e, "retryable", False),
                )

    logger.info(
        "Generating %s top-half scene assets with concurrency=%s...",
        len(scenes),
        max_parallel,
    )
    tasks = [gen_one(scene) for scene in scenes]
    enriched = await asyncio.gather(*tasks)
    logger.info("Top-half scene generation completed | total=%s", len(enriched))
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
