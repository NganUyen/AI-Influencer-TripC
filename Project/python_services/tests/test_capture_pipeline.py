import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from activities.capture.capture_models import CaptureJobInput, CaptureTarget, SceneCaptureSpec
from activities.capture.pipeline import run_capture_pipeline


@pytest.mark.asyncio
async def test_run_capture_pipeline_orchestrates_flow(tmp_path):
    """Pipeline should call capture->compositor and then persist storage result."""
    target = CaptureTarget(type="mobile")
    job = CaptureJobInput(
        campaign_id="camp-001",
        persona_id="persona-1",
        scenes=[
            SceneCaptureSpec(scene_index=0, script_text="A", capture_target=target, duration_seconds=3.0),
            SceneCaptureSpec(scene_index=1, script_text="B", capture_target=target, duration_seconds=2.0),
        ],
    )
    capture_fn = MagicMock(side_effect=["raw0.png", "raw1.png"])
    saved = AsyncMock()
    saved.return_value = MagicMock(status="success")

    with patch("activities.capture.pipeline.composite_overlay") as overlay:
        with patch("activities.capture.pipeline.save_capture_result_activity", new=saved):
            result = await run_capture_pipeline(
                job=job,
                capture_scene_image=capture_fn,
                output_dir=str(tmp_path / "frames"),
                db_client=MagicMock(),
                supabase_client=MagicMock(),
                stitched_video_path=str(tmp_path / "final.mp4"),
            )

    assert capture_fn.call_count == 2
    assert overlay.call_count == 2
    assert saved.await_count == 1
    assert result.status == "success"


@pytest.mark.asyncio
async def test_run_capture_pipeline_uses_stitch_callable_when_no_final_path(tmp_path):
    """Pipeline should use stitch callable when stitched_video_path is omitted."""
    target = CaptureTarget(type="mobile")
    job = CaptureJobInput(
        campaign_id="camp-001",
        persona_id="persona-1",
        scenes=[
            SceneCaptureSpec(scene_index=0, script_text="A", capture_target=target, duration_seconds=3.0),
        ],
    )
    capture_fn = MagicMock(return_value="raw0.png")
    stitch_fn = MagicMock(return_value=str(tmp_path / "stitched.mp4"))
    saved = AsyncMock()
    saved.return_value = MagicMock(status="success")

    with patch("activities.capture.pipeline.composite_overlay"):
        with patch("activities.capture.pipeline.save_capture_result_activity", new=saved):
            result = await run_capture_pipeline(
                job=job,
                capture_scene_image=capture_fn,
                output_dir=str(tmp_path / "frames"),
                db_client=MagicMock(),
                supabase_client=MagicMock(),
                stitched_video_path=None,
                stitch_video=stitch_fn,
            )

    assert stitch_fn.call_count == 1
    assert saved.await_count == 1
    assert result.status == "success"
