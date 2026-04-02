"""
Capture pipeline orchestration:
capture -> compositor -> storage save/update.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from .capture_models import CaptureJobInput, CaptureJobResult
from .compositor import composite_overlay
from .exceptions import CapturePipelineError
from .storage import save_capture_result_activity


async def run_capture_pipeline(
    *,
    job: CaptureJobInput,
    capture_scene_image: Callable[..., str],
    output_dir: str,
    db_client: Any,
    supabase_client: Any,
    stitched_video_path: Optional[str] = None,
    stitch_video: Optional[Callable[..., str]] = None,
    upload_to_storage: bool = True,
    bucket_name: str = "videos",
    head_check: Optional[Any] = None,
) -> CaptureJobResult:
    """
    Run full capture flow for all scenes and persist final result.
    capture_scene_image is injected to keep pipeline unit-test friendly.
    """
    try:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        scene_outputs: list[str] = []

        for scene in job.scenes:
            raw_image_path = capture_scene_image(scene=scene, campaign_id=job.campaign_id)
            scene_out = output_root / f"scene_{scene.scene_index:03d}.png"
            composite_overlay(
                input_path=raw_image_path,
                output_path=str(scene_out),
                spec=scene,
                campaign_id=job.campaign_id,
            )
            scene_outputs.append(str(scene_out))

        final_video_path = stitched_video_path
        if not final_video_path:
            if stitch_video is None:
                raise CapturePipelineError(
                    "Missing stitched_video_path and no stitch_video callable provided"
                )
            final_video_path = stitch_video(
                scene_outputs=scene_outputs,
                scenes=job.scenes,
                campaign_id=job.campaign_id,
                persona_id=job.persona_id,
            )
            if not final_video_path:
                raise CapturePipelineError("Stitch step returned empty output path")

        return await save_capture_result_activity(
            campaign_id=job.campaign_id,
            scenes=job.scenes,
            output_video_path=final_video_path,
            db_client=db_client,
            supabase_client=supabase_client,
            bucket_name=bucket_name,
            upload_to_storage=upload_to_storage,
            head_check=head_check,
        )
    except Exception as exc:
        raise CapturePipelineError(f"Capture pipeline failed for {job.campaign_id}: {exc}") from exc
