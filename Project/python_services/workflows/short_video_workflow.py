"""
Short video workflow for persona-driven vertical video generation.
"""

from __future__ import annotations
import asyncio
from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from activities.approval_activities import (
        generate_and_send_script_for_approval,
        wait_for_script_approval,
        send_preview_to_telegram,
        wait_for_publish_decision,
        generate_script_from_approved_package_activity,
        send_telegram_progress_update,
        send_telegram_error_notification,
    )
    from activities.media_activities import (
        generate_audio,
        generate_scene_images,
        create_talking_head_video,
    )
    from activities.video_activities import build_split_screen_video
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


@workflow.defn
class ShortVideoWorkflow:
    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.workflow_status = "queued"
        self.current_step = "queued"
        self.decision = None

        workflow_id = workflow.info().workflow_id
        payload_dict = payload if isinstance(payload, dict) else {}
        fallback_persona_id = payload_dict.get("persona_id", "")
        fallback_topic = payload_dict.get("topic", "")
        telegram_chat_id = payload_dict.get("telegram_chat_id")

        async def notify_progress(stage_label: str, details: str = "") -> None:
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

        def summarize_exception(exc: Exception) -> Dict[str, str]:
            """Return a more useful error type/summary for Telegram and status payloads."""
            if isinstance(exc, ActivityError):
                cause = getattr(exc, "cause", None)
                cause_text = str(cause or exc).strip() or "Activity task failed"
                cause_type = type(cause).__name__ if cause is not None else "UnknownCause"
                return {
                    "error_type": f"ActivityError/{cause_type}",
                    "error_summary": cause_text[:300],
                }

            return {
                "error_type": type(exc).__name__,
                "error_summary": (str(exc).strip() or repr(exc))[:300],
            }

        try:
            start_payload = VideoWorkflowStartPayloadContract.model_validate(payload)
            persona_id = start_payload.persona_id
            topic = start_payload.topic
            tone = start_payload.tone
            platform = start_payload.platform
            telegram_chat_id = start_payload.telegram_chat_id
            owner_key = start_payload.owner_key
            talking_head_optional = start_payload.talking_head_optional
            persona_snapshot = start_payload.persona_snapshot
            language = persona_snapshot.language or "English"
            tts_voice = persona_snapshot.tts_voice
            heygen_avatar_id = persona_snapshot.heygen_avatar_id
            user_id = start_payload.user_id

            # Check if this workflow was kicked off with an approved production package
            approved_package = (
                start_payload.approved_package.model_dump(mode="json")
                if start_payload.approved_package
                else None
            )

            if approved_package:
                self.workflow_status = "generating_script_from_package"
                self.current_step = "generating_script"
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
                            },
                            "telegram_chat_id": telegram_chat_id,
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
                    "config": {},
                    "top_half_source_type": scene.get("top_half_source_type"),
                    "top_half_target": scene.get("top_half_target"),
                    "top_half_capture_hint": scene.get("top_half_capture_hint"),
                    "source_ref": scene.get("source_ref"),
                }
                for scene in scenes
            ]

            # Stage A: Start audio and scenes in parallel
            # Temporal 1.5.1 returns ActivityHandle; start both first, then await
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
                            },
                        }
                        for scene in scene_payloads
                    ]
                ],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=MEDIA_RETRY_POLICY,
            )

            # Await audio first so talking head can start immediately
            audio_result = await audio_handle
            talking_head_handle = None

            # Stage B: Start talking head as soon as audio is ready
            if not heygen_avatar_id:
                workflow.logger.info(
                    "Skipping talking-head generation for persona %s because heygen_avatar_id is missing.",
                    persona_id,
                )
                await notify_progress(
                    "Bottom-half audio ready",
                    "This persona is in voiceover-only mode, so the workflow will continue without a talking-head avatar clip.",
                )
                talking_head_result = {
                    "url": "",
                    "status": "skipped",
                    "reason": (
                        "talking_head_optional"
                        if talking_head_optional
                        else "missing_heygen_avatar_id"
                    ),
                }
            else:
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

            # Now await scenes (may already be done while talking head was starting)
            self.current_step = "generating_top_half"
            scenes_result = await scenes_handle

            # Await talking head if it was started
            if talking_head_handle is not None:
                try:
                    talking_head_result = await talking_head_handle
                except Exception as exc:
                    workflow.logger.warning("Talking head generation failed: %s", exc)
                    talking_head_result = {"url": "", "status": "failed"}

            self.workflow_status = "assembling"
            self.current_step = "assembling"
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
                i for i, url in enumerate(image_urls_raw) if url is None
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
                if scene.get("image_url")
            ]
            image_urls = [
                scene.get("image_url") for _, scene in valid_scenes_with_index
            ]
            # [SAFETY-4] Extract is_video flags from scene metadata
            is_video_flags = [
                bool(scene.get("is_video")) for _, scene in valid_scenes_with_index
            ]
            aligned_durations = [
                scene_durations[i] if i < len(scene_durations) else 4.0
                for i, _ in valid_scenes_with_index
            ]
            aligned_captions = [
                scene.get("caption", "") for _, scene in valid_scenes_with_index
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
                        "audio_url": audio_result["url"],
                        "talking_head_url": talking_head_result.get("url") or None,
                        "scene_captions": aligned_captions,
                        "scene_durations": aligned_durations,
                        "is_video_flags": is_video_flags,  # [SAFETY-4]
                        "persona_id": persona_id,
                        "owner_key": owner_key,
                        "user_id": user_id,
                        "topic": topic,
                        "duration_per_image": 4.0,
                    }
                ],
                start_to_close_timeout=timedelta(minutes=20),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            self.workflow_status = "waiting_final_decision"
            self.current_step = "waiting_final_decision"
            preview = await workflow.execute_activity(
                send_preview_to_telegram,
                args=[
                    {
                        "telegram_chat_id": telegram_chat_id,
                        "video_url": final_video["video_url"],
                        "workflow_id": workflow_id,
                        "topic": topic,
                        "persona_id": persona_id,
                        "tone": tone,
                        "platform": platform,
                    }
                ],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            decision = await workflow.execute_activity(
                wait_for_publish_decision,
                args=[preview["request_id"], telegram_chat_id],
                start_to_close_timeout=timedelta(minutes=31),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            self.decision = decision.get("action")
            if self.decision == "discard":
                self.workflow_status = "discarded"
                self.current_step = "discarded"
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

            self.workflow_status = "completed"
            self.current_step = "completed"
            return {
                **final_video,
                "status": "completed",
                "workflow_id": workflow_id,
                "persona_id": persona_id,
                "topic": topic,
                "metadata": {
                    **(final_video.get("metadata") or {}),
                    "final_decision": "save",
                },
            }
        except (PersonaNotReadyError, PersonaConfigurationError):
            self.workflow_status = "failed"
            self.current_step = "failed"
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
            self.workflow_status = "failed"
            self.current_step = "failed"
            error_details = summarize_exception(exc)

            workflow.logger.error(
                "Workflow failed | workflow_id=%s | topic=%s | step=%s | error_type=%s | error=%s",
                workflow_id,
                fallback_topic,
                getattr(self, "current_step", "unknown"),
                error_details["error_type"],
                error_details["error_summary"],
            )
            if telegram_chat_id:
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

            return {
                "type": "video",
                "status": "failed",
                "workflow_id": workflow_id,
                "persona_id": fallback_persona_id,
                "topic": fallback_topic,
                "video_url": None,
                "storage_key": None,
                "metadata": {
                    "reason": error_details["error_summary"],
                    "error_type": error_details["error_type"],
                    "failed_step": getattr(self, "current_step", "failed"),
                },
            }

    @workflow.query
    def get_workflow_status(self) -> Dict[str, Any]:
        return {
            "status": getattr(self, "workflow_status", "queued"),
            "current_step": getattr(self, "current_step", "queued"),
            "decision": getattr(self, "decision", None),
            "workflow_id": workflow.info().workflow_id,
        }
