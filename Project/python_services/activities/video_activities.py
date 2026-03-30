"""
Video assembly activities.

Canonical deterministic lane for final video composition.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import asyncio
import logging
import os
import subprocess
import tempfile

import httpx
from temporalio import activity

from services.contracts import FinalVideoContract, SplitScreenVideoInput
from services.errors import AssemblyError, AssemblyMissingAssetError, StorageUploadError
from services.storage_service import StorageService
from services.media_storage_service import MediaStorageService

logger = logging.getLogger(__name__)

HALF_FRAME_WIDTH = 1080
HALF_FRAME_HEIGHT = 960
FULL_FRAME_WIDTH = 1080
FULL_FRAME_HEIGHT = 1920


def _is_video_url(url: str) -> bool:
    """
    [MEDIUM-2 FIX] Detect if URL points to a video file.
    Uses urlparse to strip query params before checking extension.
    Handles presigned S3 URLs and CDN URLs with query strings.
    """
    path = urlparse(url).path.lower()
    return path.endswith((".webm", ".mp4", ".mov"))


def _get_extension_for_url(url: str) -> str:
    """Get file extension for a URL, handling presigned URLs."""
    path = urlparse(url).path.lower()
    if path.endswith(".webm"):
        return ".webm"
    elif path.endswith(".mp4"):
        return ".mp4"
    elif path.endswith(".mov"):
        return ".mov"
    return ".jpg"


async def _download_required(url: str, dest: str, label: str) -> None:
    """Download a required asset and fail fast on any download issue."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        with open(dest, "wb") as file_obj:
            file_obj.write(response.content)
    logger.info("Downloaded %s", label)


async def _download_optional(url: str, dest: str, label: str) -> Optional[str]:
    """Download an optional asset. Fail closed to fallback instead of failing the lane."""
    try:
        await _download_required(url, dest, label)
        return dest
    except Exception as exc:
        logger.warning("Optional asset %s unavailable, falling back: %s", label, exc)
        return None


def _run_ffmpeg(cmd: List[str], label: str) -> None:
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        error_text = result.stderr.decode("utf-8", errors="replace")[-1000:]
        raise AssemblyError(f"ffmpeg failed ({label}): {error_text}")
    logger.info("ffmpeg OK: %s", label)


def _safe_topic_fragment(topic: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in topic.strip()
    )
    return cleaned.strip("_") or "topic"


def _escape_drawtext_text(text: str) -> str:
    value = str(text or "")
    replacements = {
        "\\": "\\\\",
        "'": "\\'",
        ":": "\\:",
        ",": "\\,",
        ";": "\\;",
        "[": "\\[",
        "]": "\\]",
        "%": "\\%",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _fit_to_frame_filter(width: int, height: int, background: str = "black") -> str:
    """Scale into a fixed frame without distorting the source aspect ratio."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:{background},setsar=1"
    )


def _half_frame_filter(background: str = "black") -> str:
    return _fit_to_frame_filter(HALF_FRAME_WIDTH, HALF_FRAME_HEIGHT, background)


def _bot_half_crop_filter() -> str:
    """Fill the bottom half by center-cropping the talking-head source."""
    return (
        "scale=1080:1080:force_original_aspect_ratio=increase,"
        "crop=1080:960:(iw-1080)/2:(ih-960)/2,setsar=1"
    )


def _split_screen_filter() -> str:
    return (
        "[0:v]setsar=1[top];"
        f"[1:v]{_bot_half_crop_filter()}[bot];"
        "[top][bot]vstack=inputs=2[v];"
        "[v]drawbox=w=iw:h=4:y=(ih/2)-2:color=orange:t=fill[vbar]"
    )


@activity.defn
async def build_split_screen_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical assembly path for final video output.

    Required:
    - image_urls
    - audio_url

    Optional:
    - talking_head_url
    - scene_captions
    """
    assembly_input = SplitScreenVideoInput(**config)

    if not assembly_input.image_urls:
        raise AssemblyMissingAssetError(
            "image_urls is empty; cannot assemble without scenes."
        )
    if not assembly_input.audio_url:
        raise AssemblyMissingAssetError("audio_url is missing; narration is required.")

    logger.info(
        "Starting assembly: %s images, talking_head=%s",
        len(assembly_input.image_urls),
        "yes" if assembly_input.talking_head_url else "no",
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        download_tasks: List[asyncio.Future] = []
        image_paths: List[str] = []
        # [SAFETY-4] Use is_video_flags from workflow if available, fallback to URL detection
        is_video_flags = assembly_input.is_video_flags or []
        for index, url in enumerate(assembly_input.image_urls):
            # [SAFETY-4] Prefer explicit flag, fallback to URL-based detection
            is_video_from_flag = (
                is_video_flags[index] if index < len(is_video_flags) else None
            )
            is_video_from_url = _is_video_url(url)
            is_video_asset = (
                is_video_from_flag
                if is_video_from_flag is not None
                else is_video_from_url
            )

            # Use appropriate extension based on asset type
            if is_video_asset:
                ext = _get_extension_for_url(url) if is_video_from_url else ".mp4"
            else:
                ext = _get_extension_for_url(url)

            # [CP5] Log asset type detection with source
            logger.debug(
                "Asset type detected | scene=%s | is_video=%s (flag=%s, url=%s) | url_path=%s",
                index,
                is_video_asset,
                is_video_from_flag,
                is_video_from_url,
                urlparse(url).path[-50:] if url else "NONE",
            )

            image_path = str(tmp_path / f"img_{index:02d}{ext}")
            image_paths.append(image_path)
            download_tasks.append(
                _download_required(url, image_path, f"asset_{index + 1}")
            )

        audio_path = str(tmp_path / "narration.mp3")
        download_tasks.append(
            _download_required(assembly_input.audio_url, audio_path, "audio")
        )

        talking_head_path: Optional[str] = None
        if assembly_input.talking_head_url:
            talking_head_dest = str(tmp_path / "talking_head.mp4")
            download_tasks.append(
                _download_optional(
                    assembly_input.talking_head_url, talking_head_dest, "talking_head"
                )
            )

        download_results = await asyncio.gather(*download_tasks)
        if assembly_input.talking_head_url:
            talking_head_path = download_results[-1]

        for path in [*image_paths, audio_path]:
            if not os.path.exists(path) or os.path.getsize(path) < 100:
                raise AssemblyMissingAssetError(
                    f"Required asset missing or too small: {path}"
                )

        # New Robust Concat Logic for Mixed Media Types
        concat_file = str(tmp_path / "concat.txt")
        standard_paths = []

        # Use per-scene durations if available, otherwise fall back to duration_per_image
        scene_durations = assembly_input.scene_durations or []

        # Warn if scene_durations array doesn't match image count
        if scene_durations and len(scene_durations) != len(image_paths):
            logger.warning(
                "Scene durations array length mismatch | durations=%s | images=%s | using fallback for missing",
                len(scene_durations),
                len(image_paths),
            )

        for idx, p in enumerate(image_paths):
            std_p = str(tmp_path / f"std_{idx:02d}.mp4")
            standard_paths.append(std_p)
            is_vid = p.endswith((".webm", ".mp4", ".mov"))

            # Get duration for this scene
            scene_duration = (
                scene_durations[idx]
                if idx < len(scene_durations)
                else assembly_input.duration_per_image
            )

            # [CP6] Log assembly per-scene details
            logger.info(
                "Assembly scene %s | asset_type=%s | duration=%.2fs | has_talking_head=%s",
                idx,
                "video" if is_vid else "image",
                scene_duration,
                bool(talking_head_path),
            )

            if is_vid:
                # Crop and scale video, limit to duration
                _run_ffmpeg(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        p,
                        "-vf",
                        _half_frame_filter(),
                        "-t",
                        str(scene_duration),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-r",
                        "25",
                        "-an",
                        std_p,
                    ],
                    f"std_vid_{idx}",
                )
            else:
                # Convert image to video chunk
                _run_ffmpeg(
                    [
                        "ffmpeg",
                        "-y",
                        "-loop",
                        "1",
                        "-i",
                        p,
                        "-vf",
                        _half_frame_filter(),
                        "-c:v",
                        "libx264",
                        "-t",
                        str(scene_duration),
                        "-pix_fmt",
                        "yuv420p",
                        "-r",
                        "25",
                        std_p,
                    ],
                    f"std_img_{idx}",
                )

        with open(concat_file, "w", encoding="utf-8") as file_obj:
            for sp in standard_paths:
                file_obj.write(f"file '{sp}'\n")

        slideshow_path = str(tmp_path / "slideshow.mp4")
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                concat_file,
                "-c",
                "copy",
                slideshow_path,
            ],
            "slideshow_concat",
        )

        if assembly_input.scene_captions:
            drawtext_filters = []
            current_ts = 0.0
            for index, caption in enumerate(
                assembly_input.scene_captions[: len(image_paths)]
            ):
                scene_duration = (
                    scene_durations[index]
                    if index < len(scene_durations)
                    else assembly_input.duration_per_image
                )
                start_ts = current_ts
                end_ts = current_ts + scene_duration
                safe_caption = _escape_drawtext_text(caption)[:60]
                drawtext_filters.append(
                    "drawtext="
                    f"text='{safe_caption}':fontsize=30:fontcolor=white:"
                    "x=(w-text_w)/2:y=h-80:box=1:boxcolor=black@0.6:boxborderw=8:"
                    f"enable='between(t,{start_ts},{end_ts})'"
                )
                current_ts = end_ts

            captioned_path = str(tmp_path / "slideshow_captioned.mp4")
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    slideshow_path,
                    "-vf",
                    ",".join(drawtext_filters),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    captioned_path,
                ],
                "captions",
            )
            slideshow_path = captioned_path

        final_path = str(tmp_path / "final_output.mp4")
        used_fallback = not talking_head_path

        if (
            talking_head_path
            and os.path.exists(talking_head_path)
            and os.path.getsize(talking_head_path) >= 100
        ):
            logger.info(
                "Using split-screen assembly with talking head | scene_count=%s",
                len(image_paths),
            )
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    slideshow_path,
                    "-i",
                    talking_head_path,
                    "-i",
                    audio_path,
                    "-filter_complex",
                    _split_screen_filter(),
                    "-map",
                    "[vbar]",
                    "-map",
                    "2:a",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-shortest",
                    final_path,
                ],
                "split_screen_assembly",
            )
        else:
            used_fallback = True
            # [CP7] Log slideshow fallback
            logger.info(
                "No talking head available — using slideshow fallback | scene_count=%s",
                len(image_paths),
            )
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    slideshow_path,
                    "-i",
                    audio_path,
                    "-vf",
                    f"pad={FULL_FRAME_WIDTH}:{FULL_FRAME_HEIGHT}:0:({FULL_FRAME_HEIGHT}-ih)/2:black",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-shortest",
                    final_path,
                ],
                "slideshow_audio_assembly",
            )

        if not os.path.exists(final_path) or os.path.getsize(final_path) < 10_000:
            raise AssemblyError("Final video file is missing or suspiciously small.")

        safe_topic = _safe_topic_fragment(assembly_input.topic)
        storage_key = f"videos/{assembly_input.persona_id}/{safe_topic}_final.mp4"
        _campaign_id = config.get("campaign_id")
        _owner_key = config.get("owner_key")
        _user_id = config.get("user_id")

        try:
            with open(final_path, "rb") as file_obj:
                video_bytes = file_obj.read()
            storage_result = None
            if _campaign_id or assembly_input.persona_id or _owner_key or _user_id:
                storage_result = await MediaStorageService().upload_bytes(
                    data=video_bytes,
                    campaign_id=str(_campaign_id) if _campaign_id else None,
                    content_type="video/mp4",
                    asset_type="VIDEO",
                    asset_kind="video",
                    generation_prompt=assembly_input.topic,
                    user_id=_user_id,
                    owner_key=_owner_key,
                    persona_id=assembly_input.persona_id,
                    metadata={"topic": assembly_input.topic, "source": "split_screen"},
                    file_name_hint=f"{safe_topic}-final",
                )

            if storage_result and storage_result.get("access_url"):
                video_url = storage_result["access_url"]
                storage_key = storage_result.get("storage_path") or storage_key
            else:
                storage = StorageService()
                video_url = await storage.upload_bytes(
                    data=video_bytes,
                    filename=storage_key,
                    content_type="video/mp4",
                )
        except Exception as exc:
            raise StorageUploadError(f"Failed to upload final video: {exc}") from exc

        metadata = {
            **assembly_input.model_dump(),
            "assembly_mode": "slideshow_audio" if used_fallback else "split_screen",
            "used_talking_head": not used_fallback,
        }

        return FinalVideoContract(
            url=video_url,
            video_url=video_url,
            preview_url=video_url,
            storage_key=storage_key,
            metadata=metadata,
            status="completed",
            resolution="1080x1920",
            persona_id=assembly_input.persona_id,
            topic=assembly_input.topic,
        ).model_dump()
