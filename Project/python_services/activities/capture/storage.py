"""
Capture storage workflow.
Verifies rendered videos, uploads to storage, and updates campaign DB state.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from temporalio import activity

from .capture_models import CaptureJobResult, SceneCaptureSpec, SubtitleData
from .exceptions import (
    CampaignNotFoundError,
    CaptureStorageError,
    StorageBucketError,
    StorageUploadError,
    StorageVerifyError,
)

try:
    from .capture_config import TARGET_SIZE
except ImportError:
    TARGET_SIZE = (1080, 960)


async def _verify_video_file(video_path: str) -> Dict[str, Any]:
    """Verify video file exists, has content, correct resolution, and valid duration."""
    video = Path(video_path)
    if not video.exists():
        raise StorageVerifyError(f"Video file not found: {video_path}")
    if video.stat().st_size <= 0:
        raise StorageVerifyError(f"Video file is empty: {video_path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise StorageVerifyError("ffprobe is not installed or not in PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise StorageVerifyError(f"ffprobe failed: {exc.stderr or exc.stdout}") from exc

    try:
        probe = json.loads(result.stdout or "{}")
        stream = (probe.get("streams") or [{}])[0]
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        duration = float((probe.get("format") or {}).get("duration", 0))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise StorageVerifyError("Invalid ffprobe output format") from exc

    if (width, height) != TARGET_SIZE:
        raise StorageVerifyError(
            f"Invalid resolution {width}x{height}. Expected {TARGET_SIZE[0]}x{TARGET_SIZE[1]}"
        )
    if duration <= 0:
        raise StorageVerifyError(f"Invalid video duration: {duration}")

    return {"width": width, "height": height, "duration": duration}


async def _upload_to_supabase_storage(
    *,
    supabase_client: Any,
    bucket_name: str,
    local_file_path: str,
    campaign_id: str,
    output_filename: Optional[str] = None,
    head_check: Optional[Any] = None,
) -> Dict[str, str]:
    """Upload video file to Supabase storage and verify accessibility."""
    if supabase_client is None:
        raise StorageBucketError("supabase_client is required")

    storage_api = getattr(supabase_client, "storage", None)
    if storage_api is None:
        raise StorageBucketError("Supabase client has no storage API")

    source = Path(local_file_path)
    filename = output_filename or source.name
    storage_path = f"captures/{campaign_id}/{filename}"

    bucket = storage_api.from_(bucket_name)
    if bucket is None:
        raise StorageBucketError(f"Bucket not found: {bucket_name}")

    with source.open("rb") as file_obj:
        bucket.upload(storage_path, file_obj, {"upsert": "true"})

    public_url = bucket.get_public_url(storage_path)

    if head_check is not None:
        for _ in range(3):
            if head_check(public_url):
                break
        else:
            raise StorageUploadError(
                f"Upload verification failed after 3 HEAD checks: {storage_path}"
            )

    return {"storage_path": storage_path, "storage_url": public_url}


async def _update_campaign_db(
    *,
    db_client: Any,
    campaign_id: str,
    values: Dict[str, Any],
    max_retries: int = 3,
) -> None:
    """Update campaign capture fields in DB, retrying transient errors."""
    # Supabase-style client
    if hasattr(db_client, "table"):
        last_exc: Optional[Exception] = None
        for _ in range(max_retries):
            try:
                query = db_client.table("campaigns").update(values).eq("id", campaign_id)
                response = query.execute()
                data = getattr(response, "data", None)
                if data is None:
                    return
                if isinstance(data, list) and len(data) == 0:
                    raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
                return
            except CampaignNotFoundError:
                raise
            except Exception as exc:  # surface after retries
                last_exc = exc
        raise CaptureStorageError(f"Failed to update campaign {campaign_id}: {last_exc}")

    # asyncpg pool client
    if hasattr(db_client, "acquire"):
        assignments = list(values.keys())
        set_clause = ", ".join([f"{k} = ${i+2}" for i, k in enumerate(assignments)])
        sql = (
            f"update public.campaigns set {set_clause}, capture_updated_at = now() "
            f"where id = $1::uuid"
        )
        args = [campaign_id, *[values[k] for k in assignments]]
        last_exc: Optional[Exception] = None
        for _ in range(max_retries):
            try:
                async with db_client.acquire() as conn:
                    result = await conn.execute(sql, *args)
                if result.startswith("UPDATE 0"):
                    raise CampaignNotFoundError(f"Campaign not found: {campaign_id}")
                return
            except CampaignNotFoundError:
                raise
            except Exception as exc:
                last_exc = exc
        raise CaptureStorageError(f"Failed to update campaign {campaign_id}: {last_exc}")

    raise CaptureStorageError("Unsupported db_client type for _update_campaign_db")



def _build_cumulative_subtitles(scenes: Iterable[SceneCaptureSpec]) -> List[SubtitleData]:
    current = 0.0
    subtitles: List[SubtitleData] = []
    for scene in scenes:
        start = current
        end = round(start + float(scene.duration_seconds), 3)
        subtitles.append(
            SubtitleData(
                scene_index=scene.scene_index,
                text=scene.script_text,
                start_sec=start,
                end_sec=end,
            )
        )
        current = end
    return subtitles


def _is_remote_path(path: str) -> bool:
    value = str(path or "").lower()
    return value.startswith("http://") or value.startswith("https://")


async def save_capture_result_activity(
    *,
    campaign_id: str,
    scenes: List[SceneCaptureSpec],
    output_video_path: str,
    db_client: Any,
    supabase_client: Any,
    bucket_name: str = "videos",
    upload_to_storage: bool = True,
    head_check: Optional[Any] = None,
) -> CaptureJobResult:
    """
    Persist capture result workflow:
    running -> verify -> optional upload -> completed; on any error -> failed.
    """
    try:
        await _update_campaign_db(
            db_client=db_client,
            campaign_id=campaign_id,
            values={"capture_status": "running"},
        )

        verify_status = "passed"
        if _is_remote_path(output_video_path):
            verify_status = "skipped_remote"
        else:
            await _verify_video_file(output_video_path)
        await _update_campaign_db(
            db_client=db_client,
            campaign_id=campaign_id,
            values={"capture_status": "running", "capture_verify": verify_status},
        )

        storage_url: Optional[str] = None
        storage_path: Optional[str] = None
        if upload_to_storage:
            uploaded = await _upload_to_supabase_storage(
                supabase_client=supabase_client,
                bucket_name=bucket_name,
                local_file_path=output_video_path,
                campaign_id=campaign_id,
                head_check=head_check,
            )
            storage_path = uploaded["storage_path"]
            storage_url = uploaded["storage_url"]

        subtitle_data = _build_cumulative_subtitles(scenes)
        await _update_campaign_db(
            db_client=db_client,
            campaign_id=campaign_id,
            values={
                "capture_status": "completed",
                "top_half_video_path": output_video_path,
                "top_half_storage_path": storage_path,
                "top_half_storage_url": storage_url,
                "subtitle_data": [s.model_dump() for s in subtitle_data],
            },
        )

        return CaptureJobResult(
            campaign_id=campaign_id,
            scenes=[s.model_dump() for s in scenes],
            subtitle_data=subtitle_data,
            video_path=output_video_path,
            status="success",
        )
    except Exception as exc:
        await _update_campaign_db(
            db_client=db_client,
            campaign_id=campaign_id,
            values={"capture_status": "failed", "capture_error": str(exc)},
        )
        raise CaptureStorageError(f"Capture storage failed for {campaign_id}: {exc}") from exc


@activity.defn
async def persist_capture_result_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Temporal activity wrapper to persist capture status into campaigns table.
    Uses asyncpg pool (DatabaseService) and supports already-uploaded remote video URLs.
    """
    from services.database_service import DatabaseService

    campaign_id = str(config.get("campaign_id") or "").strip()
    if not campaign_id:
        raise CaptureStorageError("persist_capture_result_activity: missing campaign_id")

    output_video_path = str(config.get("output_video_path") or "").strip()
    if not output_video_path:
        raise CaptureStorageError("persist_capture_result_activity: missing output_video_path")

    scene_rows = config.get("scenes") or []
    if not isinstance(scene_rows, list) or not scene_rows:
        raise CaptureStorageError("persist_capture_result_activity: scenes is required")

    normalized_scenes: List[SceneCaptureSpec] = []
    from .capture_models import CaptureTarget

    for idx, scene in enumerate(scene_rows):
        start = float(scene.get("timestamp_start", 0.0) or 0.0)
        end = float(scene.get("timestamp_end", start + 3.0) or start + 3.0)
        duration = end - start if end > start else 3.0
        normalized_scenes.append(
            SceneCaptureSpec(
                scene_index=int(scene.get("scene_index", idx)),
                script_text=str(
                    scene.get("narration_text") or scene.get("caption") or scene.get("script_text") or ""
                ).strip()
                or f"Scene {idx + 1}",
                capture_target=CaptureTarget(type="mobile"),
                duration_seconds=duration,
            )
        )

    pool = await DatabaseService.get_pool()
    result = await save_capture_result_activity(
        campaign_id=campaign_id,
        scenes=normalized_scenes,
        output_video_path=output_video_path,
        db_client=pool,
        supabase_client=config.get("supabase_client"),
        bucket_name=str(config.get("bucket_name") or "videos"),
        upload_to_storage=bool(config.get("upload_to_storage", False)),
        head_check=None,
    )
    return result.model_dump()
