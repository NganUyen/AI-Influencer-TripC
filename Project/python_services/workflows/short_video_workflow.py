"""
Short video workflow for persona-driven vertical video generation.
"""

from __future__ import annotations
import asyncio
import re
from urllib.parse import urlparse
from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, TimeoutError

with workflow.unsafe.imports_passed_through():
    from activities.approval_activities import (
        generate_and_send_script_for_approval,
        wait_for_script_approval,
        send_preview_to_telegram,
        wait_for_publish_decision,
        generate_script_from_approved_package_activity,
        generate_script_from_review_plan_activity,
        send_telegram_progress_update,
        send_telegram_error_notification,
    )
    from activities.media_activities import (
        generate_audio,
        generate_scene_images,
        create_talking_head_video,
    )
    from activities.distribution_activities import publish_to_platforms
    from activities.video_activities import build_split_screen_video
    from activities.workflow_status_activities import sync_workflow_terminal_status
    from services.contracts import VideoWorkflowStartPayloadContract
    from services.errors import (
        PersonaNotReadyError,
        PersonaConfigurationError,
        SceneAssetMismatchError,
    )


MEDIA_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    non_retryable_error_types=[
        "PersonaNotReadyError",
        "PersonaConfigurationError",
    ],
)

_DB_SYNC_RETRY = RetryPolicy(maximum_attempts=2)
_ASSEMBLY_RETRY_POLICY = RetryPolicy(
    maximum_attempts=2,
    non_retryable_error_types=[
        "AssemblyError",
        "AssemblyMissingAssetError",
        "SceneAssetMismatchError",
    ],
)


_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi"}
_KNOWN_VIDEO_GENERATION_METHODS = {
    "browser_capture",
    "uploaded_demo_segment",
    "ai_visual_video",
}


def _scene_has_video_asset(scene: Dict[str, Any]) -> bool:
    """Best-effort video detection for mixed worker versions and partial metadata."""
    raw_flag = scene.get("is_video")
    if isinstance(raw_flag, bool):
        return raw_flag
    if isinstance(raw_flag, str):
        normalized = raw_flag.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False

    generation_method = str(scene.get("generation_method") or "").strip().lower()
    if generation_method in _KNOWN_VIDEO_GENERATION_METHODS:
        return True

    asset_url = str(scene.get("image_url") or "").strip()
    if not asset_url:
        return False

    parsed = urlparse(asset_url)
    path = (parsed.path or "").lower()
    return any(path.endswith(ext) for ext in _VIDEO_EXTENSIONS)


def _has_nonempty_asset_url(scene: Dict[str, Any]) -> bool:
    asset_url = scene.get("image_url")
    return isinstance(asset_url, str) and bool(asset_url.strip())


_FFMPEG_SUBSTAGE_PATTERN = re.compile(r"ffmpeg failed \(([^)]+)\)")


def _trim_debug_text(text: str, limit: int = 3000) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _application_error_type(exc: ApplicationError, raw_text: str) -> str:
    explicit_type = str(getattr(exc, "type", "") or "").strip()
    if explicit_type and explicit_type != "ApplicationError":
        return explicit_type
    inline_match = re.match(r"^([A-Za-z][A-Za-z0-9_]+):", raw_text)
    if inline_match and inline_match.group(1) != "ApplicationError":
        return inline_match.group(1)
    return type(exc).__name__


def _sanitize_workflow_error_for_user(error_text: str, error_type: str) -> str:
    text_lower = error_text.lower()
    error_type_lower = error_type.lower()

    if "talking-head generation failed" in text_lower or "heygen" in text_lower:
        return (
            "Talking-head generation failed. Please verify avatar/provider availability "
            "and retry."
        )
    if "playwright top-half recording failed" in text_lower:
        return (
            "Top-half browser recording failed. Please verify website accessibility "
            "and try again."
        )
    if "top-half assets must be playwright" in text_lower:
        return (
            "Top-half assets were not valid video recordings. Please retry render "
            "after re-validating the plan."
        )
    if "asset generation failed for" in text_lower and "scene" in text_lower:
        return "Top-half asset generation failed for one or more scenes. Please retry."

    if "assemblymissingasseterror" in error_type_lower:
        return "A required media file was unavailable during video assembly."
    if "assemblyerror" in error_type_lower:
        return "Video processing encountered an issue. Please try again."
    if "storageuploaderror" in error_type_lower:
        return "Final video upload issue. Please try again."
    if "sceneassetmismatcherror" in error_type_lower:
        return "Scene assets were incomplete. Please try again."

    if "ffmpeg" in text_lower or "ffprobe" in text_lower:
        return "Video processing encountered an issue. Please try again."
    if "codec" in text_lower or "encoding" in text_lower:
        return "Video encoding issue. Please try with a different video format."

    if any(
        p in text_lower
        for p in ["/tmp/", "\\tmp\\", "storage", "bucket", "blob", "s3://"]
    ):
        return "Temporary storage issue. Please try again in a few minutes."
    if "file not found" in text_lower or "no such file" in text_lower:
        return "A required file was unavailable. Please try again."

    if "timeout" in text_lower:
        return "Request timed out. Please try again."
    if "connection" in text_lower or "network" in text_lower:
        return "Network issue encountered. Please try again."
    if "rate limit" in text_lower or "429" in text_lower:
        return "Service is busy. Please try again in a few minutes."

    if (
        "auth" in text_lower
        or "token" in text_lower
        or "credential" in text_lower
    ):
        return "Authentication issue. Please contact support."

    if "applicationerror" in error_type_lower:
        clean = re.sub(r"^(ActivityError/|ApplicationError:?\s*)", "", error_text)
        if any(c in clean for c in ["\\", "/", "0x", "stack", "trace"]):
            return "An unexpected error occurred. Please try again."
        return clean[:200] if len(clean) <= 200 else clean[:197] + "..."

    if re.search(r"(File \".+\", line \d+|Traceback|at 0x[0-9a-f]+)", error_text):
        return "An internal error occurred. Our team has been notified."

    if len(error_text) <= 150 and not any(
        c in error_text for c in ["\\", "://", "/home/", "/var/", "C:\\"]
    ):
        return error_text

    return "An unexpected error occurred. Please try again or contact support."


def _infer_failure_substage(raw_error_message: str) -> str | None:
    match = _FFMPEG_SUBSTAGE_PATTERN.search(str(raw_error_message or ""))
    if match:
        return match.group(1).strip()
    return None


def _summarize_workflow_exception(exc: Exception) -> Dict[str, Any]:
    raw_text = str(exc).strip() or repr(exc)
    error_type = type(exc).__name__
    activity_type = None
    cause_type = None
    retryable = getattr(exc, "retryable", None)

    if isinstance(exc, ActivityError):
        activity_type = getattr(exc, "activity_type", None)
        cause = getattr(exc, "cause", None)
        raw_text = str(cause or exc).strip() or "Activity task failed"
        if isinstance(cause, ApplicationError):
            cause_type = _application_error_type(cause, raw_text)
            retryable = not bool(getattr(cause, "non_retryable", False))
        elif cause is not None:
            cause_type = type(cause).__name__
            retryable = getattr(cause, "retryable", retryable)
        error_type = f"ActivityError/{cause_type or 'UnknownCause'}"
    elif isinstance(exc, ApplicationError):
        error_type = _application_error_type(exc, raw_text)
        retryable = not bool(getattr(exc, "non_retryable", False))

    error_summary = _sanitize_workflow_error_for_user(raw_text, error_type)
    if error_summary == "An unexpected error occurred. Please try again." and activity_type:
        activity_fallbacks = {
            "create_talking_head_video": (
                "Talking-head generation failed while processing avatar video. "
                "Please retry."
            ),
            "generate_scene_images": (
                "Top-half scene generation failed while preparing recorded visuals. "
                "Please retry."
            ),
            "build_split_screen_video": (
                "Video assembly failed while combining top-half and bottom-half. "
                "Please retry."
            ),
        }
        error_summary = activity_fallbacks.get(activity_type, error_summary)

    return {
        "error_type": error_type,
        "error_summary": error_summary,
        "raw_error_message": _trim_debug_text(raw_text, limit=4000),
        "failure_substage": _infer_failure_substage(raw_text),
        "activity_type": activity_type,
        "activity_cause_type": cause_type,
        "retryable": retryable,
    }


def _build_failure_output_data(
    *, failed_step: str, error_details: Dict[str, Any]
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "failure_step": failed_step,
        "error_type": error_details["error_type"],
        "raw_error_message": error_details["raw_error_message"],
    }
    if error_details.get("failure_substage"):
        payload["failure_substage"] = error_details["failure_substage"]
    if error_details.get("activity_type"):
        payload["activity_type"] = error_details["activity_type"]
    if error_details.get("activity_cause_type"):
        payload["activity_cause_type"] = error_details["activity_cause_type"]
    if error_details.get("retryable") is not None:
        payload["error_retryable"] = bool(error_details["retryable"])
    return payload


@workflow.defn
class ShortVideoWorkflow:
    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.workflow_status = "queued"
        self.current_step = "queued"
        self.decision = None

        # Version gates for deterministic replay across deployed workflow changes.
        progress_notify_enabled = workflow.patched("short-video-progress-notify-v1")
        error_notify_enabled = workflow.patched("short-video-error-notify-v1")

        workflow_id = workflow.info().workflow_id
        payload_dict = payload if isinstance(payload, dict) else {}
        fallback_persona_id = payload_dict.get("persona_id", "")
        fallback_topic = payload_dict.get("topic", "")
        telegram_chat_id = payload_dict.get("telegram_chat_id")
        auto_publish_enabled = bool(payload_dict.get("auto_publish_enabled"))
        caption_draft = str(payload_dict.get("caption_draft") or "").strip()
        content_title = str(payload_dict.get("content_title") or "").strip()

        def log_step_change(new_step: str, details: str = "") -> None:
            """Log workflow step transitions for debugging and monitoring."""
            workflow.logger.info(
                "Workflow step change | workflow_id=%s | persona_id=%s | topic=%s | step=%s | details=%s",
                workflow_id,
                fallback_persona_id,
                fallback_topic,
                new_step,
                details or "none",
            )

        async def notify_progress(stage_label: str, details: str = "") -> None:
            if not progress_notify_enabled:
                return
            if not telegram_chat_id:
                return
            try:
                await workflow.execute_activity(
                    send_telegram_progress_update,
                    args=[
                        {
                            "telegram_chat_id": telegram_chat_id,
                            "workflow_id": workflow_id,
                            "stage_label": stage_label,
                            "details": details,
                        }
                    ],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
            except Exception as exc:
                workflow.logger.warning(
                    "Progress notification failed | workflow_id=%s | stage=%s | error=%s",
                    workflow_id,
                    stage_label,
                    exc,
                )

        async def _sync_db_status(
            wf_id: str,
            status: str,
            step: str,
            *,
            error_message: str | None = None,
            output_data: Dict[str, Any] | None = None,
        ) -> None:
            """Fire-and-forget sync of terminal status to public.workflows."""
            try:
                await workflow.execute_activity(
                    sync_workflow_terminal_status,
                    args=[
                        {
                            "workflow_id": wf_id,
                            "status": status,
                            "current_step": step,
                            "error_message": error_message,
                            "output_data": output_data,
                        }
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=_DB_SYNC_RETRY,
                )
            except Exception as sync_exc:
                workflow.logger.warning(
                    "DB status sync failed (non-fatal) | workflow_id=%s | status=%s | error=%s",
                    wf_id,
                    status,
                    sync_exc,
                )

        async def _handle_workflow_failure(exc: Exception) -> None:
            failed_step = str(getattr(self, "current_step", "unknown") or "unknown")
            self.workflow_status = "failed"
            error_details = _summarize_workflow_exception(exc)
            failure_output = _build_failure_output_data(
                failed_step=failed_step,
                error_details=error_details,
            )

            workflow.logger.error(
                "Workflow failed | workflow_id=%s | topic=%s | step=%s | substage=%s | error_type=%s | error=%s | raw_error=%s",
                workflow_id,
                fallback_topic,
                failed_step,
                error_details.get("failure_substage") or "none",
                error_details["error_type"],
                error_details["error_summary"],
                error_details["raw_error_message"],
            )

            await _sync_db_status(
                workflow_id,
                "failed",
                failed_step,
                error_message=error_details["error_summary"],
                output_data=failure_output,
            )

            if telegram_chat_id and error_notify_enabled:
                try:
                    await workflow.execute_activity(
                        send_telegram_error_notification,
                        args=[
                            {
                                "telegram_chat_id": telegram_chat_id,
                                "workflow_id": workflow_id,
                                "topic": fallback_topic,
                                "error_type": error_details["error_type"],
                                "error_summary": error_details["error_summary"],
                                "failure_step": failed_step,
                                "failure_substage": error_details.get("failure_substage"),
                                "activity_type": error_details.get("activity_type"),
                            }
                        ],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(maximum_attempts=2),
                    )
                except Exception as notify_exc:
                    workflow.logger.warning(
                        "Failed to send error notification to Telegram: %s",
                        notify_exc,
                    )

        try:
            start_payload = VideoWorkflowStartPayloadContract.model_validate(payload)
            persona_id = start_payload.persona_id
            topic = start_payload.topic
            tone = start_payload.tone
            platform = start_payload.platform
            telegram_chat_id = start_payload.telegram_chat_id
            owner_key = start_payload.owner_key
            persona_snapshot = start_payload.persona_snapshot
            language = persona_snapshot.language or "English"
            tts_voice = persona_snapshot.tts_voice
            heygen_avatar_id = persona_snapshot.heygen_avatar_id
            user_id = start_payload.user_id
            talking_head_optional = bool(start_payload.talking_head_optional)
            audio_policy = (
                start_payload.audio_policy.model_dump(mode="json")
                if start_payload.audio_policy
                else {
                    "voiceover_required": True,
                    "bgm_fallback_enabled": True,
                    "bgm_library_profile": "product_explainer",
                    "bgm_duck_under_voiceover": True,
                    "max_bgm_duration_seconds": 60,
                    "movement_overlay_enabled": False,
                    "movement_library_profile": "natural",
                    "movement_overlay_volume": 0.18,
                }
            )
            review_plan = (
                start_payload.review_plan.model_dump(mode="json")
                if start_payload.review_plan
                else None
            )
            execution_mode = (start_payload.execution_mode or "").strip()

            # Check if this workflow was kicked off with an approved production package
            approved_package = (
                start_payload.approved_package.model_dump(mode="json")
                if start_payload.approved_package
                else None
            )

            if review_plan and execution_mode in {
                "autonomous_screen_recording",
                "authenticated_pc_recording",
            }:
                self.workflow_status = "generating_script_from_review_plan"
                self.current_step = "generating_script"
                log_step_change("generating_script", "from confirmed review plan")
                await notify_progress(
                    "Generating recording script from approved plan",
                    "Converting the confirmed website review plan into autonomous recording scenes.",
                )
                script_result = await workflow.execute_activity(
                    generate_script_from_review_plan_activity,
                    args=[
                        {
                            "app_name": "TripC",
                            "review_plan": review_plan,
                            "persona_config": {
                                "language_name": language,
                                "voice": tts_voice,
                                "tts_voice": tts_voice,
                                "_openclaw_owner_key": owner_key,
                                "_openclaw_user_id": user_id,
                            },
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                await notify_progress(
                    "Recording script ready",
                    "Autonomous screen recording steps are ready. Starting asset generation next.",
                )
            elif approved_package:
                self.workflow_status = "generating_script_from_package"
                self.current_step = "generating_script"
                log_step_change("generating_script", "from approved package")
                await notify_progress(
                    "Generating script from approved plan",
                    "Converting the approved concept and beat plan into the production script.",
                )

                script_result = await workflow.execute_activity(
                    generate_script_from_approved_package_activity,
                    args=[
                        {
                            "app_name": "TripC",
                            "topic": topic,
                            "approved_package": approved_package,
                            "persona_config": {
                                "language_name": language,
                                "voice": tts_voice,
                                "tts_voice": tts_voice,
                                "_openclaw_owner_key": owner_key,
                                "_openclaw_user_id": user_id,
                            },
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                await notify_progress(
                    "Script ready",
                    "Approved package was converted successfully. Starting top-half and bottom-half generation next.",
                )
            else:
                self.workflow_status = "waiting_script_approval"
                self.current_step = "waiting_script_approval"
                script_result = await workflow.execute_activity(
                    generate_and_send_script_for_approval,
                    args=[
                        {
                            "app_name": "TripC",
                            "topic": topic,
                            "persona_config": {
                                "language_name": language,
                                "voice": tts_voice,
                                "tts_voice": tts_voice,
                                "_openclaw_owner_key": owner_key,
                                "_openclaw_user_id": user_id,
                            },
                            "telegram_chat_id": telegram_chat_id,
                            "workflow_id": workflow_id,
                            "user_id": user_id,
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )

                approval = await workflow.execute_activity(
                    wait_for_script_approval,
                    args=[script_result["request_id"], telegram_chat_id],
                    start_to_close_timeout=timedelta(minutes=31),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
                if not approval.get("approved"):
                    self.workflow_status = "discarded"
                    self.current_step = "script_rejected"
                    log_step_change("script_rejected", "user rejected script")
                    await _sync_db_status(workflow_id, "discarded", "script_rejected")
                    return {
                        "type": "video",
                        "status": "discarded",
                        "workflow_id": workflow_id,
                        "persona_id": persona_id,
                        "topic": topic,
                        "video_url": None,
                        "storage_key": None,
                        "metadata": {"reason": "script_rejected"},
                    }

            self.workflow_status = "generating_assets"
            self.current_step = "generating_top_half_and_audio"
            log_step_change("generating_top_half_and_audio", "parallel generation started")
            await notify_progress(
                "Starting top-half and bottom-half generation",
                "Top-half visuals and bottom-half audio are now running in parallel.",
            )

            script_json = script_result["script_json"]
            scenes: List[Dict[str, Any]] = script_json.get("scenes", [])

            scene_payloads = [
                {
                    "id": scene.get("id"),
                    "caption": scene.get("caption", ""),
                    "image_prompt": scene.get("prompt", ""),
                    "prompt": scene.get("prompt", ""),
                    "browser_action": scene.get("browser_action"),
                    "visual_success_criteria": scene.get("visual_success_criteria"),
                    "config": {},
                    "top_half_source_type": scene.get("top_half_source_type"),
                    "top_half_target": scene.get("top_half_target"),
                    "top_half_capture_hint": scene.get("top_half_capture_hint"),
                    "top_half_follow_links": scene.get("top_half_follow_links"),
                    "top_half_max_capture_seconds": scene.get(
                        "top_half_max_capture_seconds"
                    ),
                    "source_ref": scene.get("source_ref"),
                }
                for scene in scenes
            ]

            # Stage A: Start audio and scenes in parallel
            # Temporal 1.5.1 returns ActivityHandle; start both first, then await
            audio_handle = None
            if bool(audio_policy.get("voiceover_required", True)):
                audio_handle = workflow.execute_activity(
                    generate_audio,
                    args=[
                        {
                            "script": script_json.get("script", ""),
                            "metadata": {
                                "day": 1,
                                "platform": platform,
                                "persona_id": persona_id,
                                "owner_key": owner_key,
                                "user_id": user_id,
                            },
                            "persona_id": persona_id,
                            "owner_key": owner_key,
                            "user_id": user_id,
                            "config": {"voice": tts_voice},
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=MEDIA_RETRY_POLICY,
                )
            scenes_handle = workflow.execute_activity(
                generate_scene_images,
                args=[
                    [
                        {
                            **scene,
                            "metadata": {
                                **(scene.get("metadata") or {}),
                                "persona_id": persona_id,
                                "owner_key": owner_key,
                                "user_id": user_id,
                                "day": 1,
                                "platform": platform,
                                "workflow_id": workflow_id,
                                "workflow_run_id": workflow.info().run_id,
                            },
                        }
                        for scene in scene_payloads
                    ]
                ],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=MEDIA_RETRY_POLICY,
            )

            # Await audio first so talking head can start immediately
            audio_result = None
            if audio_handle is not None:
                try:
                    audio_result = await audio_handle
                except Exception as exc:
                    if bool(audio_policy.get("bgm_fallback_enabled", True)):
                        workflow.logger.warning(
                            "Primary audio generation failed; falling back to local BGM | workflow_id=%s | error=%s",
                            workflow_id,
                            exc,
                        )
                        audio_result = None
                    else:
                        raise
            talking_head_handle = None

            # Stage B: Start talking head as soon as audio is ready
            if not heygen_avatar_id and talking_head_optional:
                workflow.logger.info(
                    "Talking head skipped | persona=%s | reason=no heygen avatar and talking head optional",
                    persona_id,
                )
                talking_head_result = {"url": None, "status": "skipped"}
            elif not heygen_avatar_id:
                raise PersonaConfigurationError(
                    (
                        "heygen_avatar_id is required for split-screen output. "
                        f"Cannot generate bottom-half talking head for persona {persona_id}."
                    )
                )
            elif audio_result is not None:
                self.current_step = "generating_talking_head"
                await notify_progress(
                    "Bottom-half audio ready",
                    "Starting talking-head generation while top-half assets continue processing.",
                )
                talking_head_handle = workflow.execute_activity(
                    create_talking_head_video,
                    args=[
                        {
                            "avatar_id": heygen_avatar_id,
                            "audio_url": audio_result["url"],
                            "script_text": script_json.get("script", ""),
                            "platform": platform,
                            "day": 1,
                            "topic": topic,
                            "persona_id": persona_id,
                            "owner_key": owner_key,
                            "user_id": user_id,
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=20),
                    retry_policy=MEDIA_RETRY_POLICY,
                )
            else:
                talking_head_result = {"url": None, "status": "skipped_no_audio"}

            # Now await scenes (may already be done while talking head was starting)
            self.current_step = "generating_top_half"
            scenes_result = await scenes_handle

            # Await talking head if it was started
            if talking_head_handle is not None:
                try:
                    talking_head_result = await talking_head_handle
                except Exception as exc:
                    workflow.logger.error(
                        "Talking head generation FAILED | persona=%s | error_type=%s | error=%s",
                        persona_id,
                        type(exc).__name__,
                        str(exc)[:300],
                    )
                    # Re-raise to fail the workflow - talking head is required for split-screen
                    raise

            self.workflow_status = "assembling"
            self.current_step = "assembling"
            log_step_change("assembling", "combining top and bottom half")
            await notify_progress(
                "Top-half assets ready",
                "Combining top half and bottom half with ffmpeg now.",
            )

            # Extract per-scene durations from timestamps
            scene_durations = []
            for scene in scenes:
                start = scene.get("timestamp_start", 0.0)
                end = scene.get("timestamp_end", 0.0)
                duration = end - start if end > start else 4.0
                scene_durations.append(duration)

            # Detect failed scenes before assembly
            image_urls_raw = [scene.get("image_url") for scene in scenes_result]
            failed_scene_indices = [
                i
                for i, url in enumerate(image_urls_raw)
                if not (isinstance(url, str) and url.strip())
            ]

            if failed_scene_indices:
                workflow.logger.error(
                    "Scene asset generation failed for indices %s — aborting assembly",
                    failed_scene_indices,
                )
                raise SceneAssetMismatchError(
                    f"Asset generation failed for {len(failed_scene_indices)} scene(s): indices {failed_scene_indices}"
                )

            # Build aligned arrays: only include scenes with valid assets
            valid_scenes_with_index = [
                (i, scene)
                for i, scene in enumerate(scenes_result)
                if _has_nonempty_asset_url(scene)
            ]
            image_urls = [
                scene.get("image_url") for _, scene in valid_scenes_with_index
            ]
            # [SAFETY-4] Extract video flags with metadata + URL fallback detection.
            is_video_flags = [
                _scene_has_video_asset(scene) for _, scene in valid_scenes_with_index
            ]
            if not all(is_video_flags):
                invalid_video_indices = [
                    i
                    for (i, _scene), is_video in zip(
                        valid_scenes_with_index, is_video_flags
                    )
                    if not is_video
                ]
                invalid_video_diagnostics = [
                    {
                        "scene_index": i,
                        "url": str(scene.get("image_url") or "")[:120],
                        "is_video": scene.get("is_video"),
                        "generation_method": scene.get("generation_method"),
                    }
                    for i, scene in valid_scenes_with_index
                    if i in invalid_video_indices
                ]
                workflow.logger.error(
                    "Top-half validation failed: non-video asset detected | flags=%s | invalid_indices=%s | diagnostics=%s",
                    is_video_flags,
                    invalid_video_indices,
                    invalid_video_diagnostics,
                )
                raise SceneAssetMismatchError(
                    "Top-half assets must be Playwright browser recordings (video only). "
                    f"Invalid scene indices: {invalid_video_indices}"
                )
            aligned_durations = [
                scene_durations[i] if i < len(scene_durations) else 4.0
                for i, _ in valid_scenes_with_index
            ]
            aligned_subtitle_segments = [
                {
                    "start": float(scenes[i].get("timestamp_start", 0.0) or 0.0),
                    "end": float(
                        scenes[i].get(
                            "timestamp_end",
                            scenes[i].get("timestamp_start", 0.0) or 0.0,
                        )
                        or 0.0
                    ),
                    "text": str(scenes[i].get("narration_text") or "").strip(),
                }
                for i, _ in valid_scenes_with_index
            ]

            # Final safety check: arrays must be same length
            if len(image_urls) != len(aligned_durations):
                workflow.logger.error(
                    "MISMATCH duration/image count: durations=%s images=%s",
                    len(aligned_durations),
                    len(image_urls),
                )
                raise SceneAssetMismatchError(
                    f"Scene count mismatch: {len(image_urls)} images vs {len(aligned_durations)} durations — aborting assembly"
                )

            workflow.logger.info(
                "Pre-assembly check passed | scenes=%s | total_duration=%.1fs",
                len(image_urls),
                sum(aligned_durations),
            )

            final_video = await workflow.execute_activity(
                build_split_screen_video,
                args=[
                    {
                        "image_urls": image_urls,
                        "audio_url": audio_result.get("url") if audio_result else None,
                        "talking_head_url": talking_head_result.get("url") or None,
                        "subtitle_script": script_json.get("script", ""),
                        "subtitle_segments": aligned_subtitle_segments,
                        "scene_durations": aligned_durations,
                        "is_video_flags": is_video_flags,  # [SAFETY-4]
                        "persona_id": persona_id,
                        "owner_key": owner_key,
                        "user_id": user_id,
                        "workflow_id": workflow_id,
                        "topic": topic,
                        "duration_per_image": 4.0,
                        "audio_policy": audio_policy,
                    }
                ],
                start_to_close_timeout=timedelta(minutes=20),
                retry_policy=_ASSEMBLY_RETRY_POLICY,
            )

            if telegram_chat_id:
                self.workflow_status = "waiting_final_decision"
                self.current_step = "waiting_final_decision"
                preview = await workflow.execute_activity(
                    send_preview_to_telegram,
                    args=[
                        {
                            "telegram_chat_id": telegram_chat_id,
                            "video_url": final_video["video_url"],
                            "workflow_id": workflow_id,
                            "user_id": user_id,
                            "topic": topic,
                            "persona_id": persona_id,
                            "tone": tone,
                            "platform": platform,
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

                try:
                    decision = await workflow.execute_activity(
                        wait_for_publish_decision,
                        args=[preview["request_id"], telegram_chat_id],
                        start_to_close_timeout=timedelta(minutes=31),
                        retry_policy=RetryPolicy(maximum_attempts=1),
                    )
                except ActivityError as exc:
                    cause = getattr(exc, "cause", None)
                    is_timeout = isinstance(cause, TimeoutError) or (
                        "timed out" in str(exc).lower()
                    )
                    if not is_timeout:
                        raise

                    self.decision = "timeout"
                    self.workflow_status = "expired"
                    self.current_step = "decision_timeout"
                    log_step_change(
                        "decision_timeout",
                        "no publish decision within 31 minutes",
                    )
                    workflow.logger.warning(
                        "Publish decision timed out | workflow_id=%s | request_id=%s",
                        workflow_id,
                        preview.get("request_id"),
                    )
                    await _sync_db_status(workflow_id, "expired", "decision_timeout")
                    return {
                        **final_video,
                        "status": "expired",
                        "workflow_id": workflow_id,
                        "persona_id": persona_id,
                        "topic": topic,
                        "metadata": {
                            **(final_video.get("metadata") or {}),
                            "final_decision": "timeout",
                            "reason": "publish_decision_timeout",
                        },
                    }

                self.decision = decision.get("action")
                if self.decision == "discard":
                    self.workflow_status = "discarded"
                    self.current_step = "discarded"
                    log_step_change("discarded", "user discarded video")
                    await _sync_db_status(workflow_id, "discarded", "discarded")
                    return {
                        "type": "video",
                        "status": "discarded",
                        "workflow_id": workflow_id,
                        "persona_id": persona_id,
                        "topic": topic,
                        "video_url": None,
                        "storage_key": None,
                        "metadata": {"reason": "operator_discarded"},
                    }
            else:
                self.decision = "save"
                log_step_change(
                    "completed_without_telegram",
                    "no telegram link present, auto-saving final product",
                )

            publish_result = None
            if auto_publish_enabled and final_video.get("video_url"):
                publish_result = await workflow.execute_activity(
                    publish_to_platforms,
                    args=[
                        {
                            "id": workflow_id,
                            "logical_post_id": workflow_id,
                            "workflow_id": workflow_id,
                            "user_id": user_id,
                            "platform": platform,
                            "content": caption_draft or topic,
                            "title": content_title or topic,
                            "theme": topic,
                            "media": [{"storage_url": final_video["video_url"]}],
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )

            self.workflow_status = "completed"
            self.current_step = "completed"
            log_step_change("completed", "workflow successful")
            await _sync_db_status(workflow_id, "completed", "completed")
            return {
                **final_video,
                "status": "completed",
                "workflow_id": workflow_id,
                "persona_id": persona_id,
                "topic": topic,
                "metadata": {
                    **(final_video.get("metadata") or {}),
                    "final_decision": "save",
                    "publish_result": publish_result,
                },
            }
        except (PersonaNotReadyError, PersonaConfigurationError) as exc:
            await _handle_workflow_failure(exc)
            raise
        except asyncio.CancelledError:
            # [SAFETY-1] Handle cancellation explicitly - don't treat as failure
            self.workflow_status = "cancelled"
            self.current_step = "cancelled"
            workflow.logger.info(
                "Workflow cancelled | workflow_id=%s | topic=%s",
                workflow_id,
                fallback_topic,
            )
            await _sync_db_status(workflow_id, "cancelled", "cancelled")
            return {
                "type": "video",
                "status": "cancelled",
                "workflow_id": workflow_id,
                "persona_id": fallback_persona_id,
                "topic": fallback_topic,
                "video_url": None,
                "storage_key": None,
                "metadata": {"reason": "Cancelled by user"},
            }
        except Exception as exc:
            await _handle_workflow_failure(exc)
            raise

    @workflow.query
    def get_workflow_status(self) -> Dict[str, Any]:
        return {
            "status": getattr(self, "workflow_status", "queued"),
            "current_step": getattr(self, "current_step", "queued"),
            "decision": getattr(self, "decision", None),
            "workflow_id": workflow.info().workflow_id,
        }
