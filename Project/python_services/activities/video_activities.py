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
import re
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
BOTTOM_SOURCE_WIDTH = 1080
BOTTOM_SOURCE_HEIGHT = 1080
TOP_SCENE_SKIP_SECONDS = 15.0  # Skip first 15 seconds to ensure page is fully loaded
SUBTITLE_FONT_NAME = "Tahoma"
SUBTITLE_FONT_SIZE = 64
SUBTITLE_CENTER_X = FULL_FRAME_WIDTH // 2
SUBTITLE_CENTER_Y = FULL_FRAME_HEIGHT // 2
SUBTITLE_MIN_WORDS = 3
SUBTITLE_MAX_WORDS = 5
SUBTITLE_TARGET_WORDS = 4
SUBTITLE_HIGHLIGHT_COLOR = "&H00FFFF&"
SUBTITLE_PRIMARY_COLOR = "&HFFFFFF&"
VIETNAMESE_STOPWORDS = {
    "va",
    "la",
    "cua",
    "cho",
    "trong",
    "nhung",
    "mot",
    "cac",
    "voi",
    "ban",
    "nay",
    "kia",
    "that",
    "rat",
    "tren",
    "duoi",
    "ngay",
    "day",
    "the",
    "thi",
    "se",
    "toi",
    "minh",
    "tripc",
}


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
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                payload = response.content or b""

            # Guard against transient tiny responses during object overwrite/propagation.
            if len(payload) < 256:
                raise ValueError(
                    f"downloaded payload too small ({len(payload)} bytes) for {label}"
                )

            with open(dest, "wb") as file_obj:
                file_obj.write(payload)
            logger.info("Downloaded %s", label)
            return
        except Exception as exc:
            last_error = exc
            if attempt >= 3:
                break
            logger.warning(
                "Retrying download for %s (attempt %s/3): %s",
                label,
                attempt,
                exc,
            )
            await asyncio.sleep(0.6 * attempt)

    if last_error is not None:
        raise last_error


async def _download_optional(url: str, dest: str, label: str) -> Optional[str]:
    """Download an optional asset. Fail closed to fallback instead of failing the lane."""
    try:
        await _download_required(url, dest, label)
        return dest
    except Exception as exc:
        logger.warning("Optional asset %s unavailable, falling back: %s", label, exc)
        return None


def _run_ffmpeg(cmd: List[str], label: str, cwd: Optional[str] = None) -> None:
    result = subprocess.run(cmd, capture_output=True, cwd=cwd, text=True)
    if result.returncode != 0:
        stderr_text = (result.stderr or "").strip()
        stdout_text = (result.stdout or "").strip()
        combined = "\n".join(part for part in [stderr_text, stdout_text] if part).strip()
        error_text = (combined or "<no ffmpeg output>")[-3000:]
        raise AssemblyError(
            f"ffmpeg failed ({label}) [code={result.returncode}] cmd={' '.join(cmd[:12])}...: {error_text}"
        )
    logger.info("ffmpeg OK: %s", label)


def _safe_topic_fragment(topic: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in topic.strip()
    )
    return cleaned.strip("_") or "topic"


def _probe_media_duration(path: str) -> Optional[float]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("ffprobe failed for %s: %s", path, result.stderr[-300:])
        return None
    try:
        duration = float((result.stdout or "").strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def _clean_subtitle_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _chunk_subtitle_lines(text: str) -> List[str]:
    words = _clean_subtitle_text(text).split()
    if not words:
        return []

    chunks: List[List[str]] = []
    index = 0
    while index < len(words):
        remaining = len(words) - index
        if remaining <= SUBTITLE_MAX_WORDS:
            if remaining < SUBTITLE_MIN_WORDS and chunks:
                chunks[-1].extend(words[index:])
            else:
                chunks.append(words[index:])
            break

        chunk_size = SUBTITLE_TARGET_WORDS
        punctuation_break = None
        for offset in range(SUBTITLE_MIN_WORDS - 1, SUBTITLE_MAX_WORDS):
            word_index = index + offset
            if word_index < len(words) and re.search(r"[.!?,;:]$", words[word_index]):
                punctuation_break = offset + 1
                break
        if punctuation_break is not None:
            chunk_size = punctuation_break
        elif remaining - chunk_size < SUBTITLE_MIN_WORDS:
            chunk_size = max(SUBTITLE_MIN_WORDS, remaining - SUBTITLE_MIN_WORDS)

        chunk_size = max(SUBTITLE_MIN_WORDS, min(SUBTITLE_MAX_WORDS, chunk_size))
        chunks.append(words[index : index + chunk_size])
        index += chunk_size

    return [" ".join(chunk).strip() for chunk in chunks if chunk]


def _normalize_keyword_token(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def _pick_highlight_token(words: List[str]) -> Optional[str]:
    candidates = []
    for word in words:
        normalized = _normalize_keyword_token(word)
        if len(normalized) < 4 or normalized in VIETNAMESE_STOPWORDS:
            continue
        if normalized.isdigit():
            continue
        candidates.append((len(normalized), word))
    if not candidates:
        return None
    return max(candidates)[1]


def _escape_ass_text(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def _style_subtitle_line(text: str) -> str:
    words = str(text or "").split()
    highlight_word = _pick_highlight_token(words)
    styled_words: List[str] = []
    highlighted = False
    for word in words:
        escaped_word = _escape_ass_text(word)
        if not highlighted and highlight_word and word == highlight_word:
            styled_words.append(
                rf"{{\c{SUBTITLE_HIGHLIGHT_COLOR}}}{escaped_word}{{\c{SUBTITLE_PRIMARY_COLOR}}}"
            )
            highlighted = True
        else:
            styled_words.append(escaped_word)
    return (
        rf"{{\an5\pos({SUBTITLE_CENTER_X},{SUBTITLE_CENTER_Y})\fscx96\fscy96\t(0,120,\fscx100\fscy100)}}"
        + " ".join(styled_words).strip()
    )


def _format_ass_timestamp(seconds: float) -> str:
    total_seconds = max(0.0, float(seconds))
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    secs = total_seconds - (hours * 3600) - (minutes * 60)
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _build_subtitle_events(
    subtitle_segments: List[Dict[str, Any]],
    subtitle_script: str,
    audio_duration: Optional[float],
) -> List[Dict[str, Any]]:
    valid_segments = [
        {
            "start": float(segment.get("start", 0.0) or 0.0),
            "end": float(segment.get("end", 0.0) or 0.0),
            "text": _clean_subtitle_text(segment.get("text", "")),
        }
        for segment in subtitle_segments
        if _clean_subtitle_text(segment.get("text", ""))
    ]

    if not valid_segments and _clean_subtitle_text(subtitle_script):
        fallback_end = audio_duration or 1.0
        valid_segments = [
            {
                "start": 0.0,
                "end": fallback_end,
                "text": _clean_subtitle_text(subtitle_script),
            }
        ]

    if not valid_segments:
        return []

    source_duration = max(
        [segment["end"] for segment in valid_segments if segment["end"] > segment["start"]],
        default=0.0,
    )
    timing_scale = (
        (audio_duration / source_duration)
        if audio_duration and source_duration > 0
        else 1.0
    )

    events: List[Dict[str, Any]] = []
    for segment in valid_segments:
        start = max(0.0, segment["start"] * timing_scale)
        end = max(start + 0.2, segment["end"] * timing_scale)
        lines = _chunk_subtitle_lines(segment["text"])
        if not lines:
            continue

        total_words = sum(max(1, len(line.split())) for line in lines)
        cursor = start
        segment_duration = max(end - start, 0.6)

        for line_index, line in enumerate(lines):
            word_count = max(1, len(line.split()))
            weighted_duration = segment_duration * (word_count / total_words)
            next_cursor = (
                end
                if line_index == len(lines) - 1
                else min(end, cursor + max(0.45, weighted_duration))
            )
            if next_cursor - cursor < 0.25:
                next_cursor = min(end, cursor + 0.25)
            events.append(
                {
                    "start": cursor,
                    "end": next_cursor,
                    "text": _style_subtitle_line(line),
                }
            )
            cursor = next_cursor

    for index in range(len(events) - 1):
        next_start = events[index + 1]["start"]
        if events[index]["end"] >= next_start:
            events[index]["end"] = max(
                events[index]["start"] + 0.12,
                next_start - 0.03,
            )

    if audio_duration:
        for event in events:
            event["start"] = min(event["start"], audio_duration)
            event["end"] = min(max(event["end"], event["start"] + 0.12), audio_duration)

    return [event for event in events if event["end"] > event["start"]]


def _write_ass_subtitles(path: str, events: List[Dict[str, Any]]) -> None:
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1080",
            "PlayResY: 1920",
            "ScaledBorderAndShadow: yes",
            "WrapStyle: 2",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
            f"Style: Default,{SUBTITLE_FONT_NAME},{SUBTITLE_FONT_SIZE},&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,5,90,90,0,1",
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        ]
    )
    lines = [header]
    for event in events:
        lines.append(
            "Dialogue: 0,"
            f"{_format_ass_timestamp(event['start'])},"
            f"{_format_ass_timestamp(event['end'])},"
            f"Default,,0,0,0,,{event['text']}"
        )
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(lines) + "\n")


def _ffmpeg_ass_filter_path(path: str) -> str:
    normalized = str(Path(path).resolve()).replace("\\", "/")
    return normalized.replace(":", r"\:")


def _fit_to_frame_filter(width: int, height: int, background: str = "black") -> str:
    """Scale into a fixed frame without distorting the source aspect ratio."""
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:{background},setsar=1"
    )


def _half_frame_filter(background: str = "black") -> str:
    return _fit_to_frame_filter(HALF_FRAME_WIDTH, HALF_FRAME_HEIGHT, background)


def _bottom_half_filter(background: str = "black") -> str:
    return (
        f"scale={BOTTOM_SOURCE_WIDTH}:{BOTTOM_SOURCE_HEIGHT}:"
        "force_original_aspect_ratio=increase,"
        f"crop={BOTTOM_SOURCE_WIDTH}:{BOTTOM_SOURCE_HEIGHT},"
        "setsar=1,"
        f"crop={HALF_FRAME_WIDTH}:{HALF_FRAME_HEIGHT}:"
        f"(iw-{HALF_FRAME_WIDTH})/2:(ih-{HALF_FRAME_HEIGHT})/2"
    )


def _bot_half_crop_filter() -> str:
    """Backward-compatible alias retained for tests and legacy imports."""
    return _bottom_half_filter()


def _split_screen_filter() -> str:
    return (
        f"[0:v]{_half_frame_filter()}[top];"
        f"[1:v]{_bottom_half_filter()}[bot];"
        "[top][bot]vstack=inputs=2[v]"
    )


@activity.defn
async def build_split_screen_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Canonical assembly path for final video output.

    Required:
    - image_urls (top-half videos only)
    - audio_url
    - talking_head_url (bottom-half video)
    """
    assembly_input = SplitScreenVideoInput(**config)

    if not assembly_input.image_urls:
        raise AssemblyMissingAssetError(
            "image_urls is empty; cannot assemble without scenes."
        )
    if not assembly_input.audio_url:
        raise AssemblyMissingAssetError("audio_url is missing; narration is required.")
    if not assembly_input.talking_head_url:
        raise AssemblyMissingAssetError(
            "talking_head_url is required for split-screen assembly."
        )

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

            if not is_video_asset:
                raise AssemblyMissingAssetError(
                    f"Top-half asset {index + 1} is not a video URL; Playwright recording is required"
                )

            ext = _get_extension_for_url(url) if is_video_from_url else ".mp4"

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
            # Increased size guard to 2KB to catch partial or empty browser captures
            if not os.path.exists(path) or os.path.getsize(path) < 2000:
                raise AssemblyMissingAssetError(
                    f"Required asset missing or too small (min 2000 bytes, got {os.path.getsize(path) if os.path.exists(path) else '0'}): {path}"
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

            if not is_vid:
                raise AssemblyMissingAssetError(
                    f"Top-half asset {idx + 1} is not a video file after download"
                )

            source_duration = _probe_media_duration(p)
            trim_start = TOP_SCENE_SKIP_SECONDS
            
            if source_duration is not None:
                # Calculate the minimum content needed after trimming
                min_content_needed = scene_duration + 0.5  # scene + small buffer
                available_after_skip = source_duration - TOP_SCENE_SKIP_SECONDS
                
                if available_after_skip >= min_content_needed:
                    # Ideal case: enough content after the skip
                    trim_start = TOP_SCENE_SKIP_SECONDS
                elif source_duration >= min_content_needed:
                    # Source is long enough but not after skip - reduce skip to preserve content
                    # Start from (source_duration - min_content_needed) to ensure we have enough
                    trim_start = max(0.0, source_duration - min_content_needed)
                else:
                    # Source is shorter than needed - start from beginning
                    trim_start = 0.0
                    logger.warning(
                        "Source video too short for full scene | scene=%s | source=%.2fs | needed=%.2fs | starting from 0",
                        idx,
                        source_duration,
                        min_content_needed,
                    )
            else:
                # source_duration is None - ffprobe failed
                # Use a conservative approach: start from 0 to avoid empty output
                trim_start = 0.0
                logger.warning(
                    "Could not probe video duration | scene=%s | file=%s | starting from 0",
                    idx,
                    p[-50:],
                )

            logger.info(
                "Assembly scene %s trimming | requested_skip=%.2fs | effective_skip=%.2fs | source_duration=%s | scene_duration=%.2fs",
                idx,
                TOP_SCENE_SKIP_SECONDS,
                trim_start,
                f"{source_duration:.2f}s" if source_duration is not None else "unknown",
                scene_duration,
            )

            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    p,
                    # Place -ss after input for accurate frame seek (avoids keyframe snap-back).
                    "-ss",
                    f"{trim_start:.3f}",
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
            
            # Validate the output file has content
            if not os.path.exists(std_p) or os.path.getsize(std_p) < 1000:
                raise AssemblyError(
                    f"Scene {idx} produced an empty or invalid video file after trimming "
                    f"(source_duration={source_duration}, trim_start={trim_start}, scene_duration={scene_duration})"
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

        final_path = str(tmp_path / "final_output.mp4")

        if (
            not talking_head_path
            or not os.path.exists(talking_head_path)
            or os.path.getsize(talking_head_path) < 100
        ):
            raise AssemblyMissingAssetError(
                "Talking-head bottom-half video is missing; cannot complete split-screen assembly"
            )

        logger.info(
            "Using split-screen assembly with talking head | scene_count=%s",
            len(image_paths),
        )

        talking_head_normalized = str(tmp_path / "talking_head_normalized.mp4")
        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-nostats",
                "-i",
                talking_head_path,
                "-an",
                "-vf",
                "fps=25,format=yuv420p,setsar=1",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-movflags",
                "+faststart",
                talking_head_normalized,
            ],
            "normalize_talking_head",
        )

        _run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-nostats",
                "-i",
                slideshow_path,
                "-i",
                talking_head_normalized,
                "-i",
                audio_path,
                "-filter_complex",
                _split_screen_filter(),
                "-map",
                "[v]",
                "-map",
                "2:a",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-r",
                "25",
                "-c:a",
                "aac",
                "-shortest",
                "-movflags",
                "+faststart",
                final_path,
            ],
            "split_screen_assembly",
        )

        if not os.path.exists(final_path) or os.path.getsize(final_path) < 10_000:
            raise AssemblyError("Final video file is missing or suspiciously small.")

        subtitle_events = _build_subtitle_events(
            subtitle_segments=assembly_input.subtitle_segments,
            subtitle_script=assembly_input.subtitle_script,
            audio_duration=_probe_media_duration(audio_path),
        )
        if subtitle_events:
            subtitles_path = str(tmp_path / "captions.ass")
            subtitled_output_path = str(tmp_path / "final_output_subtitled.mp4")
            _write_ass_subtitles(subtitles_path, subtitle_events)
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    final_path,
                    "-vf",
                    f"ass={_ffmpeg_ass_filter_path(subtitles_path)}",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "copy",
                    subtitled_output_path,
                ],
                "burn_subtitles",
            )
            final_path = subtitled_output_path

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
            "assembly_mode": "split_screen",
            "used_talking_head": True,
            "top_half_resolution": f"{HALF_FRAME_WIDTH}x{HALF_FRAME_HEIGHT}",
            "bottom_half_resolution": f"{HALF_FRAME_WIDTH}x{HALF_FRAME_HEIGHT}",
            "bottom_half_source_resolution": f"{BOTTOM_SOURCE_WIDTH}x{BOTTOM_SOURCE_HEIGHT}",
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
