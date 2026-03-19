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
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from services.fal_service import FalAIService
from services.google_tts_service import GoogleTTSService
from services.heygen_service import HeyGenService
from services.storage_service import StorageService
from services.content_scenes_service import (
    generate_content_scenes as get_scenes,
    generate_app_tutorial_scenes as get_app_scenes
)

logger = logging.getLogger(__name__)


@activity.defn
async def generate_image(prompt_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate image using fal.ai
    Supports models like Flux.1 Pro, SDXL, etc.
    """
    logger.info(f"Generating image for day {prompt_config.get('day')}")

    fal_service = FalAIService()

    try:
        result = await fal_service.generate_image(
            prompt=prompt_config.get("prompt"),
            model=prompt_config.get("config", {}).get("model", "fal-ai/flux-pro"),
            aspect_ratio=prompt_config.get("config", {}).get("aspect_ratio", "16:9"),
            safety_tolerance=prompt_config.get("config", {}).get("safety_tolerance", 2),
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to generate image HTTP error: {str(e)}")
        # Do not retry on 4xx clients errors to prevent burning limits/billing
        non_retryable = 400 <= e.response.status_code < 500
        raise ApplicationError(f"Image generation HTTP error: {str(e)}", non_retryable=non_retryable)
    except Exception as e:
        logger.error(f"Failed to generate image: {str(e)}")
        raise ApplicationError(f"Image generation failed: {str(e)}", non_retryable=False)

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
    Generate audio using Google TTS API
    Returns URL of generated audio
    """
    logger.info(f"Generating audio for platform: {prompt_config.get('metadata', {}).get('platform', 'unknown')}")

    tts_service = GoogleTTSService()
    
    # Map the requested voice style to a Wavenet voice if provided
    # Alternatively use the default voice 'vi-VN-Wavenet-D' ("Minh")
    voice_mapped = "vi-VN-Wavenet-D" 
    # Extract config if present
    custom_voice = prompt_config.get("config", {}).get("voice")
    if custom_voice:
        voice_mapped = custom_voice

    text_to_speak = prompt_config.get("script")
    if not text_to_speak:
         raise ApplicationError("Missing audio script in prompt", non_retryable=True)

    try:
        audio_bytes = await tts_service.generate_audio(
            text=text_to_speak,
            voice=voice_mapped,
        )
        
        storage_service = StorageService()
        file_extension = "mp3"
        day = prompt_config.get('metadata', {}).get('day', 1)
        platform = prompt_config.get('metadata', {}).get('platform', 'default')
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
             "metadata": prompt_config.get("metadata", {}),
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


# ─────────────────────────────────────────────────────────────────────────────
# Nhánh 2: Slideshow Video (ffmpeg)
# ─────────────────────────────────────────────────────────────────────────────

@activity.defn
async def create_slideshow(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tạo video slideshow từ danh sách ảnh + audio dùng ffmpeg.

    config:
        image_urls: List[str]  — URLs ảnh fal.ai (4-5 ảnh cảnh 9:16)
        audio_url: str          — URL audio TTS (MP3)
        duration_per_image: int — Mỗi ảnh bao nhiêu giây (default 4)
        output_filename: str    — Tên file output (default 'slideshow.mp4')
        day: int                — Ngày trong chiến lược

    Returns:
        dict với storage_url, duration, và metadata
    """
    image_urls: List[str] = config.get("image_urls", [])
    audio_url: str = config.get("audio_url", "")
    duration_per_image: int = config.get("duration_per_image", 4)
    day: int = config.get("day", 1)
    output_filename: str = config.get("output_filename", f"slideshow_day{day}.mp4")

    if not image_urls:
        raise ApplicationError("create_slideshow: thiếu 'image_urls'", non_retryable=True)
    if not audio_url:
        raise ApplicationError("create_slideshow: thiếu 'audio_url'", non_retryable=True)

    logger.info(f"Tạo slideshow | {len(image_urls)} ảnh | {duration_per_image}s/ảnh")

    storage = StorageService()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Task 4.2: Download ảnh về local temp
        image_paths = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for idx, url in enumerate(image_urls):
                logger.info(f"  Downloading ảnh {idx+1}/{len(image_urls)}")
                resp = await client.get(url)
                resp.raise_for_status()
                img_path = tmp_path / f"img_{idx:02d}.png"
                img_path.write_bytes(resp.content)
                image_paths.append(str(img_path))

            # Download audio
            logger.info("  Downloading audio...")
            resp = await client.get(audio_url)
            resp.raise_for_status()
            audio_path = tmp_path / "audio.mp3"
            audio_path.write_bytes(resp.content)

        # Task 4.3: dùng ffmpeg tạo slideshow với Ken Burns effect
        output_path = tmp_path / output_filename
        input_args = []
        filter_parts = []

        for idx in range(len(image_paths)):
            # Mỗi ảnh: thêm -loop 1 -t <duration> -i <file>
            input_args += ["-loop", "1", "-t", str(duration_per_image), "-i", image_paths[idx]]

            # Ken Burns: zoom in nhẹ + pan lên, 125 frames = 5s@25fps = 4s@31fps
            frames = duration_per_image * 25  # 25fps
            zoom_expr = f"'min(zoom+0.0005,1.05)'"
            pan_x = "0"
            pan_y = f"'ih/zoom-(ih/zoom)*{idx % 2}'"  # Xen kẽ pan up/down
            filter_parts.append(
                f"[{idx}:v]zoompan=z={zoom_expr}:x={pan_x}:d={frames}:s=1080x1920,setsar=1[v{idx}]"
            )

        # Concat tất cả video streams
        concat_inputs = "".join(f"[v{i}]" for i in range(len(image_paths)))
        filter_parts.append(
            f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[vout]"
        )
        filter_complex = ";".join(filter_parts)

        # Audio input index
        audio_input_idx = len(image_paths)
        input_args += ["-i", str(audio_path)]

        cmd = [
            "ffmpeg", "-y",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", f"{audio_input_idx}:a",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",           # Kết thúc khi audio hết
            "-pix_fmt", "yuv420p", # Tương thích iOS/Android
            str(output_path),
        ]

        logger.info("  Chạy ffmpeg...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            logger.error(f"ffmpeg stderr: {result.stderr[-500:]}")
            raise ApplicationError(f"ffmpeg thất bại: {result.stderr[-200:]}", non_retryable=False)

        # Task 4.4: Upload mp4 lên R2
        logger.info("  Upload video lên R2...")
        video_bytes = output_path.read_bytes()
        public_url = await storage.upload(
            file_data=BytesIO(video_bytes),
            filename=f"videos/slideshow/day{day}/{output_filename}",
            content_type="video/mp4",
        )

    total_duration = duration_per_image * len(image_urls)
    logger.info(f"Slideshow hoàn thành | URL: {public_url}")

    return {
        "type": "slideshow_video",
        "storage_url": public_url,
        "duration": total_duration,
        "image_count": len(image_urls),
        "day": day,
        "metadata": config,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nhánh 1: Talking Head (HeyGen)
# ─────────────────────────────────────────────────────────────────────────────

@activity.defn
async def create_talking_head_video(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tạo video AI influencer 'Minh' nói script qua HeyGen.

    config:
        avatar_id: str      — ID avatar HeyGen (tạo 1 lần từ persona image)
        audio_url: str      — URL audio TTS tiếng Việt
        background: str     — "blur" | "Da Nang" | URL ảnh nền
        day: int            — Ngày trong chiến lược
        topic: str          — Chủ đề episode (để đặt tên file)

    Returns:
        dict với storage_url, video_id, và metadata
    """
    avatar_id: str = config.get("avatar_id", "")
    audio_url: str = config.get("audio_url", "")
    background: str = config.get("background", "blur")
    day: int = config.get("day", 1)
    topic: str = config.get("topic", "episode")

    if not avatar_id or not audio_url:
        raise ApplicationError(
            "create_talking_head_video: thiếu 'avatar_id' hoặc 'audio_url'",
            non_retryable=True,
        )

    heygen = HeyGenService()
    storage = StorageService()

    logger.info(f"Tạo talking head | avatar: {avatar_id} | day: {day}")

    # Gửi request tạo video
    video_job = await heygen.create_video(
        avatar_id=avatar_id,
        audio_url=audio_url,
        background=background,
        aspect_ratio="9:16",
    )

    video_id = video_job.get("video_id")
    if not video_id:
        raise ApplicationError("HeyGen không trả về video_id", non_retryable=False)

    # Polling đợi video hoàn thành (Task 5.3)
    logger.info(f"  Polling HeyGen video {video_id}...")
    heygen_video_url = await heygen.poll_video_status(video_id, timeout_seconds=600)

    # Download và upload lên R2 (Task 5.4)
    logger.info("  Downloading video từ HeyGen...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(heygen_video_url)
        resp.raise_for_status()
        video_bytes = resp.content

    filename = f"videos/talking_head/day{day}/{topic.replace(' ', '_')[:30]}.mp4"
    logger.info("  Upload video lên R2...")
    public_url = await storage.upload(
        file_data=BytesIO(video_bytes),
        filename=filename,
        content_type="video/mp4",
    )

    logger.info(f"Talking head hoàn thành | URL: {public_url}")

    return {
        "type": "talking_head_video",
        "storage_url": public_url,
        "heygen_video_id": video_id,
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
    """
    Sinh ảnh cho tất cả scenes song song qua fal.ai.
    Mỗi scene nhận thêm trường 'image_url'.

    scenes: output từ content_scenes_service.generate_content_scenes()
    """
    fal = FalAIService()

    async def gen_one(scene: dict) -> dict:
        result = await fal.generate_image(
            prompt=scene["image_prompt"],
            model=scene.get("config", {}).get("model", "fal-ai/flux/schnell"),
            aspect_ratio="9:16",
            safety_tolerance=2,
        )
        return {**scene, "image_url": result.get("url")}

    logger.info(f"Sinh {len(scenes)} ảnh scene song song...")
    tasks = [gen_one(s) for s in scenes]
    enriched = await asyncio.gather(*tasks)
    logger.info("Sinh ảnh scenes xong")
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
    """
    Tạo video Split Screen 9:16 bằng cách stack:
      - TOP  1080x960: slideshow ảnh cảnh + caption text overlay + Ken Burns
      - BOT  1080x960: HeyGen talking head video (no bg)
    với TTS audio đồng bộ toàn bộ video.

    config:
        scenes          : List[Dict] — từ generate_scene_images() (image_url + caption + duration)
        heygen_video_url: str — URL video HeyGen (BOT half)
        audio_url       : str — URL audio TTS (MP3)
        topic           : str — chủ đề (đặt tên file)
        day             : int
        duration_per_image: int (default 4)
    """
    scenes: List[dict] = config.get("scenes", [])
    heygen_video_url: str = config.get("heygen_video_url", "")
    audio_url: str = config.get("audio_url", "")
    topic: str = config.get("topic", "episode")
    day: int = config.get("day", 1)
    dur: int = config.get("duration_per_image", 4)

    if not scenes:
        raise ApplicationError("create_split_screen_video: thiếu 'scenes'", non_retryable=True)
    if not heygen_video_url:
        raise ApplicationError("create_split_screen_video: thiếu 'heygen_video_url'", non_retryable=True)
    if not audio_url:
        raise ApplicationError("create_split_screen_video: thiếu 'audio_url'", non_retryable=True)

    logger.info(f"Tạo Split Screen | {len(scenes)} scenes | day {day}")
    storage = StorageService()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # ── 1. Download tất cả assets ─────────────────────────────────────
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Download slide images
            img_paths = []
            for i, scene in enumerate(scenes):
                url = scene.get("image_url")
                if not url:
                    continue
                resp = await client.get(url)
                resp.raise_for_status()
                p = tmp / f"scene_{i:02d}.jpg"
                p.write_bytes(resp.content)
                img_paths.append((p, scene))
                logger.info(f"  ✓ Scene {i+1} image ({len(resp.content)//1024}KB)")

            # Download HeyGen video
            resp = await client.get(heygen_video_url)
            resp.raise_for_status()
            heygen_path = tmp / "heygen.mp4"
            heygen_path.write_bytes(resp.content)
            logger.info(f"  ✓ HeyGen video ({len(resp.content)//1024}KB)")

            # Download audio
            resp = await client.get(audio_url)
            resp.raise_for_status()
            audio_path = tmp / "tts_audio.mp3"
            audio_path.write_bytes(resp.content)
            logger.info(f"  ✓ Audio TTS ({len(resp.content)//1024}KB)")

        # ── 2. Build TOP slideshow với caption overlay (Ken Burns) ─────────
        top_path = tmp / "top_slideshow.mp4"
        input_args = []
        filter_parts = []

        for idx, (img_p, scene) in enumerate(img_paths):
            scene_dur = scene.get("duration", dur)
            frames = scene_dur * 25
            input_args += ["-loop", "1", "-t", str(scene_dur), "-i", str(img_p)]

            # Ken Burns: zoom + crop exactly 1080x960
            zoom_expr = "'min(zoom+0.0004,1.06)'"
            kb = (
                f"[{idx}:v]"
                f"scale=1080:1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,"
                f"crop=1080:960:0:0,"  # Chỉ lấy nửa trên (top half)
                f"zoompan=z={zoom_expr}:d={frames}:s=1080x960,setsar=1"
            )

            # Caption text overlay (drawtext)
            caption = scene.get("caption", "")
            if caption:
                safe_caption = caption.replace("'", "\\'").replace(":", "\\:")
                # Font fallback: Arial hoặc DejaVu
                kb += (
                    f",drawtext=text='{safe_caption}'"
                    f":fontsize=42:fontcolor=white:borderw=3:bordercolor=black"
                    f":x=(w-text_w)/2:y=h-90"  # Bottom of the top half
                )

            kb += f"[v{idx}]"
            filter_parts.append(kb)

        # Concat slides thành top video
        n = len(img_paths)
        concat_in = "".join(f"[v{i}]" for i in range(n))
        filter_parts.append(f"{concat_in}concat=n={n}:v=1:a=0[top]")
        filter_complex_top = ";".join(filter_parts)

        audio_input_idx = n
        input_args += ["-an"]  # Không cần audio ở bước này

        cmd_top = [
            "ffmpeg", "-y",
            *input_args,
            "-filter_complex", filter_complex_top,
            "-map", "[top]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            str(top_path),
        ]

        logger.info("  Render top slideshow...")
        r = subprocess.run(cmd_top, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            logger.error(f"ffmpeg TOP lỗi:\n{r.stderr[-400:]}")
            raise ApplicationError(f"ffmpeg top thất bại: {r.stderr[-100:]}", non_retryable=False)

        # ── 3. ffmpeg: Stack TOP + BOTTOM + Audio + Progress Bar ───────────
        output_path = tmp / f"split_screen_day{day}.mp4"

        # Tính toán tổng thời lượng để làm progress bar
        total_dur = sum(s.get("duration", dur) for s in scenes)
        
        # BOT: crop HeyGen video xuống 1080x960
        # Progress Bar: Một hình chữ nhật mỏng (vàng/cam) chạy ở giữa ranh giới
        # dùng filter 'drawbox' di động theo thời gian 't'
        progress_bar_filter = (
            f"drawbox=y=ih/2-2:x=0:w=iw*t/{total_dur}:h=4:color=orange@0.8:t=fill"
        )

        cmd_final = [
            "ffmpeg", "-y",
            "-i", str(top_path),        # [0] top slideshow  1080x960
            "-i", str(heygen_path),     # [1] HeyGen talking head
            "-i", str(audio_path),      # [2] TTS audio
            "-filter_complex",
            (
                "[0:v]scale=1080:960,setsar=1[top_scaled];"
                "[1:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:960:0:480,setsar=1[bot_scaled];"   # Centre-crop bottom half
                "[top_scaled][bot_scaled]vstack=inputs=2[v_stacked];"
                f"[v_stacked]{progress_bar_filter}[v]"
            ),
            "-map", "[v]",
            "-map", "2:a",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]

        logger.info("  Render split screen final...")
        r = subprocess.run(cmd_final, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            logger.error(f"ffmpeg FINAL lỗi:\n{r.stderr[-400:]}")
            raise ApplicationError(f"ffmpeg split screen thất bại: {r.stderr[-100:]}", non_retryable=False)

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"  Split screen xong! {size_mb:.1f} MB")

        # ── 4. Upload R2 ───────────────────────────────────────────────────
        safe_topic = topic.replace(" ", "_")[:30]
        filename = f"videos/split_screen/day{day}/{safe_topic}.mp4"
        public_url = await storage.upload(
            file_data=BytesIO(output_path.read_bytes()),
            filename=filename,
            content_type="video/mp4",
        )

    logger.info(f"Split Screen upload xong | URL: {public_url}")

    return {
        "type": "split_screen_video",
        "storage_url": public_url,
        "scene_count": len(scenes),
        "day": day,
        "topic": topic,
        "size_mb": round(size_mb, 2),
        "metadata": config,
    }
