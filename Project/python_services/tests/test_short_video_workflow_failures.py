from temporalio.exceptions import ApplicationError

from workflows.short_video_workflow import (
    _build_failure_output_data,
    _summarize_workflow_exception,
)


def test_summarize_workflow_exception_keeps_application_error_subtype():
    exc = ApplicationError(
        "ffmpeg failed (split_screen_assembly) [code=1]: missing stream",
        type="AssemblyMissingAssetError",
        non_retryable=True,
    )

    details = _summarize_workflow_exception(exc)

    assert details["error_type"] == "AssemblyMissingAssetError"
    assert details["failure_substage"] == "split_screen_assembly"
    assert details["retryable"] is False
    assert "required media file" in details["error_summary"].lower()


def test_build_failure_output_data_preserves_stage_and_debug_fields():
    payload = _build_failure_output_data(
        failed_step="assembling",
        error_details={
            "error_type": "ActivityError/AssemblyError",
            "raw_error_message": "ffmpeg failed (burn_subtitles): libass error",
            "failure_substage": "burn_subtitles",
            "activity_type": "build_split_screen_video",
            "activity_cause_type": "AssemblyError",
            "retryable": False,
        },
    )

    assert payload["failure_step"] == "assembling"
    assert payload["failure_substage"] == "burn_subtitles"
    assert payload["activity_type"] == "build_split_screen_video"
    assert payload["activity_cause_type"] == "AssemblyError"
    assert payload["error_retryable"] is False
