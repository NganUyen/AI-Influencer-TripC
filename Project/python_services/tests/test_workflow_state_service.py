import pytest

from services.workflow_state_service import WorkflowStateService


@pytest.mark.asyncio
async def test_record_terminal_status_merges_output_data_on_fallback(monkeypatch):
    workflow_id = "wf-merge-output"
    WorkflowStateService._memory_store[workflow_id] = {
        "workflow_id": workflow_id,
        "status": "running",
        "current_step": "assembling",
        "output_data": {"final_video_url": "https://cdn.example/final.mp4"},
    }

    async def fail_get_pool():
        raise RuntimeError("db offline")

    monkeypatch.setattr(
        "services.workflow_state_service.DatabaseService.get_pool",
        fail_get_pool,
    )

    result = await WorkflowStateService.record_terminal_status(
        workflow_id=workflow_id,
        status="failed",
        current_step="assembling",
        error_message="Video processing encountered an issue. Please try again.",
        output_data={
            "failure_substage": "split_screen_assembly",
            "raw_error_message": "ffmpeg failed (split_screen_assembly): broken filter",
        },
    )

    assert result is not None
    assert result["output_data"]["final_video_url"] == "https://cdn.example/final.mp4"
    assert result["output_data"]["failure_substage"] == "split_screen_assembly"
    assert "ffmpeg failed" in result["output_data"]["raw_error_message"]
