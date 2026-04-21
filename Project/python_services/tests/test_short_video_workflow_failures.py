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


def test_summarize_workflow_exception_classifies_top_half_http_response_failure():
    exc = ApplicationError(
        "Playwright top-half recording failed for scene 3: All 3 capture attempts failed for scene 3. Last error: net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://aisoeasy.co/",
        type="TopHalfRecordingError",
        non_retryable=True,
    )

    details = _summarize_workflow_exception(exc)

    assert details["error_type"] == "TopHalfRecordingError"
    assert details["retryable"] is False
    assert details["failure_details"] == {
        "stage": "top_half",
        "code": "http_response_failure",
        "message": "Top-half recording failed because the website returned an HTTP response that browser automation could not use.",
        "scene_id": "3",
        "source_url": "https://aisoeasy.co/",
        "domain": "aisoeasy.co",
        "retryable": False,
        "recommended_action": "Verify the site is reachable from automated browsers and try again.",
    }
    assert details["error_summary"] == details["failure_details"]["message"]


def test_build_failure_output_data_includes_structured_failure_details():
    payload = _build_failure_output_data(
        failed_step="generating_top_half",
        error_details={
            "error_type": "TopHalfRecordingError",
            "raw_error_message": "net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://aisoeasy.co/",
            "failure_substage": None,
            "activity_type": "generate_scene_images",
            "activity_cause_type": "TopHalfRecordingError",
            "retryable": False,
            "failure_details": {
                "stage": "top_half",
                "code": "http_response_failure",
                "message": "Top-half recording failed because the website returned an HTTP response that browser automation could not use.",
                "scene_id": "3",
                "source_url": "https://aisoeasy.co/",
                "domain": "aisoeasy.co",
                "retryable": False,
                "recommended_action": "Verify the site is reachable from automated browsers and try again.",
            },
        },
    )

    assert payload["failure_step"] == "generating_top_half"
    assert payload["failure_stage"] == "top_half"
    assert payload["failure_details"]["code"] == "http_response_failure"


def test_summarize_workflow_exception_preserves_proxy_retry_context_for_top_half_failure():
    exc = ApplicationError(
        "Playwright top-half recording failed for scene 4: All 3 capture attempts failed for scene 4. Last error: net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://www.coursera.org | capture_context=proxy_retry_failed proxy_enabled_initial=True proxy_server=http://proxy.example:8080",
        type="TopHalfRecordingError",
        non_retryable=True,
    )

    details = _summarize_workflow_exception(exc)

    assert details["failure_details"]["code"] == "http_response_failure"
    assert details["failure_details"]["proxy_retry_failed"] is True
    assert details["failure_details"]["proxy_server"] == "http://proxy.example:8080"


def test_summarize_workflow_exception_does_not_misclassify_talking_head_failure_as_top_half():
    exc = ApplicationError(
        "HeyGen quota is exhausted and D-ID fallback failed.",
        type="ApplicationError",
        non_retryable=True,
    )

    details = _summarize_workflow_exception(
        exc,
        failed_step="generating_top_half",
    )

    assert details["failure_details"] is None
    assert details["error_summary"] == "HeyGen quota is exhausted and D-ID fallback failed."
