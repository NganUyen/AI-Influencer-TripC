"""
Video Assembly Activities (TripC v2 Standard)
===============================================
Deterministic, local ffmpeg assembly.
- Chỉ nhận remote URLs và metadata, không gọi bất kỳ AI provider nào.
- Download về temp dir → build → upload R2 → trả về FinalVideoContract.
- Retry chỉ khi tất cả input assets đã có, không retry nếu asset thiếu.
"""

from temporalio import activity
from typing import Dict, Any, List
import logging
import asyncio
import subprocess
import tempfile
import httpx
import os
from pathlib import Path

from services.errors import AssemblyError, AssemblyMissingAssetError, StorageUploadError
from services.contracts import FinalVideoContract
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


# ─── Helper ───────────────────────────────────────────────────────────────────

async def _download(url: str, dest: str, label: str):
    """Download file từ URL về local path."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
    logger.info(f"Downloaded {label}: {len(open(dest,'rb').read())//1024} KB")


def _run_ffmpeg(cmd: List[str], label: str):
    """Chạy ffmpeg và raise AssemblyError nếu thất bại."""
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-1000:]
        raise AssemblyError(f"ffmpeg failed ({label}): {err}")
    logger.info(f"ffmpeg OK: {label}")


# ─── Activity: build_split_screen_video ──────────────────────────────────────

@activity.defn
async def build_split_screen_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ghép video split screen 9:16 từ các assets đã được generate.

    Input config:
        image_urls: List[str]           — URL ảnh slideshow (từ fal.ai)
        audio_url: str                  — URL narration MP3 (từ Google TTS)
        talking_head_url: str | None    — URL HeyGen video (optional)
        scene_captions: List[str]       — Caption cho mỗi scene
        persona_id: str
        topic: str
        duration_per_image: float       — seconds per slide (default 4.0)

    Output (FinalVideoContract):
        video_url, preview_url, storage_key, duration, resolution
    """
    image_urls: List[str] = config.get("image_urls", [])
    audio_url: str = config.get("audio_url", "")
    talking_head_url: str = config.get("talking_head_url", "")
    captions: List[str] = config.get("scene_captions", [])
    persona_id: str = config.get("persona_id", "unknown")
    topic: str = config.get("topic", "topic")
    dur_per_img: float = config.get("duration_per_image", 4.0)

    # Validate input
    if not image_urls:
        raise AssemblyMissingAssetError("image_urls is empty — cannot assemble without scenes.")
    if not audio_url:
        raise AssemblyMissingAssetError("audio_url is missing — narration required.")

    logger.info(f"Starting assembly: {len(image_urls)} images, talking_head={'yes' if talking_head_url else 'no'}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 1. Download all media in parallel
        tasks = []
        img_paths = []
        for i, url in enumerate(image_urls):
            dest = str(tmp / f"img_{i:02d}.jpg")
            img_paths.append(dest)
            tasks.append(_download(url, dest, f"Image {i+1}"))

        audio_path = str(tmp / "narration.mp3")
        tasks.append(_download(audio_url, audio_path, "Audio"))

        th_path = None
        if talking_head_url:
            th_path = str(tmp / "talking_head.mp4")
            tasks.append(_download(talking_head_url, th_path, "Talking Head"))

        await asyncio.gather(*tasks)

        # Verify all files exist
        for p in [*img_paths, audio_path]:
            if not os.path.exists(p) or os.path.getsize(p) < 100:
                raise AssemblyMissingAssetError(f"File missing or too small: {p}")

        # 2. Build slideshow concat file
        concat_file = str(tmp / "concat.txt")
        with open(concat_file, "w") as f:
            for img in img_paths:
                f.write(f"file '{img}'\nduration {dur_per_img}\n")
            f.write(f"file '{img_paths[-1]}'\n")  # last frame hold

        slideshow_path = str(tmp / "slideshow.mp4")
        _run_ffmpeg([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vf", "scale=1080:960:force_original_aspect_ratio=decrease,pad=1080:960:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            slideshow_path
        ], "slideshow")

        # 3. Add captions overlay (optional, if captions provided)
        if captions:
            drawtext_filters = []
            per_cap = dur_per_img
            for i, cap in enumerate(captions[:len(img_paths)]):
                ts = i * per_cap
                te = ts + per_cap
                safe_cap = cap.replace("'", "\\'").replace(":", "\\:")[:60]
                drawtext_filters.append(
                    f"drawtext=text='{safe_cap}':fontsize=30:fontcolor=white:x=(w-text_w)/2:y=h-80:box=1:boxcolor=black@0.6:boxborderw=8:enable='between(t,{ts},{te})'"
                )
            captioned_path = str(tmp / "slideshow_captioned.mp4")
            _run_ffmpeg([
                "ffmpeg", "-y", "-i", slideshow_path,
                "-vf", ",".join(drawtext_filters),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                captioned_path
            ], "captions")
            slideshow_path = captioned_path

        # 4. Final assembly: split screen OR just slideshow + audio
        final_path = str(tmp / "final_output.mp4")

        if th_path and os.path.exists(th_path):
            # Split screen 1080x1920
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-i", slideshow_path, "-i", th_path, "-i", audio_path,
                "-filter_complex",
                (
                    "[0:v]scale=1080:960,setsar=1[top];"
                    "[1:v]scale=1080:960,setsar=1[bot];"
                    "[top][bot]vstack=inputs=2[v];"
                    "[v]drawbox=w=iw:h=4:y=(ih/2)-2:color=orange:t=fill[vbar]"
                ),
                "-map", "[vbar]", "-map", "2:a",
                "-c:v", "libx264", "-c:a", "aac", "-shortest",
                final_path
            ], "split_screen_assembly")
        else:
            # Slideshow + audio only (1080x960 → pad to 1080x1920)
            _run_ffmpeg([
                "ffmpeg", "-y",
                "-i", slideshow_path, "-i", audio_path,
                "-vf", "pad=1080:1920:0:(1920-ih)/2:black",
                "-c:v", "libx264", "-c:a", "aac", "-shortest",
                final_path
            ], "slideshow_audio_assembly")

        # 5. Validate output
        if not os.path.exists(final_path) or os.path.getsize(final_path) < 10_000:
            raise AssemblyError("Final video file is missing or suspiciously small.")

        size_kb = os.path.getsize(final_path) // 1024
        logger.info(f"Final video: {size_kb} KB")

        # 6. Upload to R2
        storage = StorageService()
        storage_key = f"videos/{persona_id}/{topic.replace(' ', '_')}_final.mp4"

        try:
            with open(final_path, "rb") as f:
                video_bytes = f.read()
            video_url = await storage.upload_bytes(
                data=video_bytes,
                filename=storage_key,
                content_type="video/mp4",
            )
        except Exception as e:
            raise StorageUploadError(f"Failed to upload final video: {e}")

        logger.info(f"Final video uploaded: {video_url}")

        return FinalVideoContract(
            video_url=video_url,
            preview_url=video_url,
            storage_key=storage_key,
            persona_id=persona_id,
            topic=topic,
        ).model_dump()
