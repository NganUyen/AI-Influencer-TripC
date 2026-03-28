"""
Short video workflow for persona-driven vertical video generation.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.approval_activities import (
        generate_and_send_script_for_approval,
        wait_for_script_approval,
        send_preview_to_telegram,
        wait_for_publish_decision,
        generate_script_from_approved_package_activity,
    )
    from activities.media_activities import (
        generate_audio,
        generate_scene_images,
        create_talking_head_video,
    )
    from activities.video_activities import build_split_screen_video
    from services.errors import PersonaNotReadyError, PersonaConfigurationError
    from services.persona_registry_service import PersonaRegistryService
    from config.settings import settings


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

        try:
            persona_id = payload["persona_id"]
            topic = payload["topic"]
            tone = payload.get("tone", "natural")
            platform = payload.get("platform", "tiktok")
            telegram_chat_id = payload.get("telegram_chat_id") or settings.TELEGRAM_CHAT_ID
            owner_key = payload.get("owner_key")
            talking_head_optional = bool(payload.get("talking_head_optional"))
            if not owner_key and telegram_chat_id:
                owner_key = f"telegram:{telegram_chat_id}"

            # FIX 3: resolve persona fields only — no duplicate status/heygen check
            persona = await PersonaRegistryService.get_persona(
                persona_id,
                user_id=payload.get("user_id"),
                owner_key=owner_key,
            )
            if not persona:
                raise PersonaConfigurationError(f"Persona '{persona_id}' was not found.")
            language = persona.get("language") or "English"
            tts_voice = persona.get("tts_voice")
            heygen_avatar_id = persona.get("heygen_avatar_id")

            # Check if this workflow was kicked off with an approved production package
            approved_package = payload.get("approved_package")

            if approved_package:
                self.workflow_status = "generating_script_from_package"
                self.current_step = "generating_script"
                
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
                            }
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=3),
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
                    # FIX 2: strict FinalVideoContract on script-rejected exit
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
            self.current_step = "generating_assets"

            script_json = script_result["script_json"]
            scenes: List[Dict[str, Any]] = script_json.get("scenes", [])
            
            # NOTE: top_half_source_type flows through script_json scenes via SceneContract
            
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

            # FIX 1: Stage A — audio and scenes truly in parallel
            audio_result, scenes_result = await workflow.gather(
                workflow.execute_activity(
                    generate_audio,
                    args=[
                        {
                            "script": script_json.get("script", ""),
                            "metadata": {
                                "day": 1,
                                "platform": platform,
                                "persona_id": persona_id,
                                "owner_key": owner_key,
                                "user_id": payload.get("user_id"),
                            },
                            "persona_id": persona_id,
                            "owner_key": owner_key,
                            "user_id": payload.get("user_id"),
                            "config": {"voice": tts_voice},
                        }
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=MEDIA_RETRY_POLICY,
                ),
                workflow.execute_activity(
                    generate_scene_images,
                    args=[
                        [
                            {
                                **scene,
                                "metadata": {
                                    **(scene.get("metadata") or {}),
                                    "persona_id": persona_id,
                                    "owner_key": owner_key,
                                    "user_id": payload.get("user_id"),
                                    "day": 1,
                                    "platform": platform,
                                },
                            }
                            for scene in scene_payloads
                        ]
                    ],
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=MEDIA_RETRY_POLICY,
                ),
            )

            # FIX 1: Stage B — talking head starts as soon as audio is ready
            if not heygen_avatar_id:
                workflow.logger.info(
                    "Skipping talking-head generation for persona %s because heygen_avatar_id is missing.",
                    persona_id,
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
                try:
                    talking_head_result = await workflow.execute_activity(
                        create_talking_head_video,
                        args=[
                            {
                                "avatar_id": heygen_avatar_id,
                                "audio_url": audio_result["url"],
                                "day": 1,
                                "topic": topic,
                                "persona_id": persona_id,
                                "owner_key": owner_key,
                                "user_id": payload.get("user_id"),
                            }
                        ],
                        start_to_close_timeout=timedelta(minutes=20),
                        retry_policy=MEDIA_RETRY_POLICY,
                    )
                except Exception as exc:  # Fallback to slideshow+audio lane
                    workflow.logger.warning("Talking head generation failed: %s", exc)
                    talking_head_result = {"url": "", "status": "failed"}

            self.workflow_status = "assembling"
            self.current_step = "assembling"
            final_video = await workflow.execute_activity(
                build_split_screen_video,
                args=[
                    {
                        "image_urls": [
                            scene.get("image_url")
                            for scene in scenes_result
                            if scene.get("image_url")
                        ],
                        "audio_url": audio_result["url"],
                        "talking_head_url": talking_head_result.get("url") or None,
                        "scene_captions": [
                            scene.get("caption", "") for scene in scenes_result
                        ],
                        "persona_id": persona_id,
                        "owner_key": owner_key,
                        "user_id": payload.get("user_id"),
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
                # FIX 2: strict FinalVideoContract on operator-discard exit
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
        except Exception as exc:
            self.workflow_status = "failed"
            self.current_step = "failed"
            # FIX 2: strict FinalVideoContract on exception exit
            return {
                "type": "video",
                "status": "failed",
                "workflow_id": workflow_id,
                "persona_id": payload.get("persona_id", ""),
                "topic": payload.get("topic", ""),
                "video_url": None,
                "storage_key": None,
                "metadata": {"reason": str(exc)},
            }

    @workflow.query
    def get_workflow_status(self) -> Dict[str, Any]:
        return {
            "status": getattr(self, "workflow_status", "queued"),
            "current_step": getattr(self, "current_step", "queued"),
            "decision": getattr(self, "decision", None),
            "workflow_id": workflow.info().workflow_id,
        }
