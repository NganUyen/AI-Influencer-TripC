"""Helpers for authenticated capture handoff without direct workflow starts."""

from __future__ import annotations

from typing import Any, Dict

from services.contracts import VideoReviewPlanContract
from services.skill_session_store import TelegramSkillSessionStore
from services.telegram_link_service import TelegramLinkService
from services.video_capture_handoff_service import VideoCaptureHandoffService


class VideoPlannerHandoffService:
    @classmethod
    async def start_confirmed_plan(
        cls,
        *,
        plan: VideoReviewPlanContract,
        persona_snapshot: Dict[str, Any],
        backend_url: str,
        http_client: Any,
        telegram_chat_id: str | None,
    ) -> Dict[str, Any]:
        del persona_snapshot, backend_url, http_client

        if plan.status != "confirmed":
            raise ValueError(
                "Video review plan must be confirmed before execution handoff"
            )

        execution_mode = plan.execution_mode

        if execution_mode == "authenticated_pc_recording":
            owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None
            user_id = await TelegramLinkService.resolve_user_id_for_owner_key(owner_key)
            if not user_id:
                return {
                    "status": "handoff_blocked",
                    "execution_mode": execution_mode,
                    "message": (
                        "This plan needs authenticated PC capture, but this Telegram chat is not linked to a workspace user yet. "
                        "Link Telegram to the workspace first, then confirm the plan again."
                    ),
                    "video_review_plan": plan.model_dump(mode="json"),
                    "credential_handoff": plan.credential_handoff.model_dump(
                        mode="json"
                    ),
                }

            token = VideoCaptureHandoffService.create_token(
                user_id=user_id,
                plan_id=plan.plan_id,
                objective=plan.objective,
                target_url=plan.target_url,
                persona_id=plan.persona_id,
                execution_mode=execution_mode,
                review_plan=plan.model_dump(mode="json"),
                telegram_chat_id=telegram_chat_id,
            )
            credential_handoff = plan.credential_handoff.model_copy(
                update={
                    "status": "requested",
                    "handoff_url": token["handoff_url"],
                    "expires_at": token["expires_at"],
                }
            )
            return {
                "status": "handoff_required",
                "execution_mode": execution_mode,
                "message": (
                    "This plan needs authenticated PC capture. "
                    "Open the secure workspace handoff link to continue credential setup outside Telegram."
                ),
                "video_review_plan": plan.model_dump(mode="json"),
                "credential_handoff": credential_handoff.model_dump(mode="json"),
                "handoff_url": token["handoff_url"],
            }

        if execution_mode == "manual_mobile_recording":
            return {
                "status": "awaiting_manual_upload",
                "execution_mode": execution_mode,
                "message": (
                    "This plan is set to manual mobile recording. "
                    "Continue in Create Video to upload the recorded demo video."
                ),
                "video_review_plan": plan.model_dump(mode="json"),
            }

        if execution_mode != "autonomous_screen_recording":
            raise ValueError(f"Unsupported execution mode: {execution_mode}")

        return {
            "status": "ready_for_video_ai",
            "execution_mode": execution_mode,
            "message": (
                "Plan confirmed. Continue in Create Video to finish pre-production and start execution."
            ),
            "video_review_plan": plan.model_dump(mode="json"),
        }

    @classmethod
    async def complete_authenticated_handoff(
        cls,
        *,
        handoff_payload: Dict[str, Any],
        method: str,
        notes: str,
        backend_url: str,
        http_client: Any,
    ) -> Dict[str, Any]:
        del backend_url, http_client

        plan_payload = handoff_payload.get("review_plan") or {}
        plan = VideoReviewPlanContract.model_validate(plan_payload)
        if plan.execution_mode != "authenticated_pc_recording":
            raise ValueError("Handoff payload is not for authenticated PC recording")

        handoff_notes = list(plan.credential_handoff.notes)
        handoff_notes.append(f"completion_method:{method}")
        if notes:
            handoff_notes.append(f"note:{notes.strip()[:240]}")

        plan.credential_handoff = plan.credential_handoff.model_copy(
            update={
                "status": "completed",
                "notes": handoff_notes,
            }
        )

        telegram_chat_id = str(handoff_payload.get("telegram_chat_id") or "").strip()
        if telegram_chat_id:
            session = await TelegramSkillSessionStore.get_session(telegram_chat_id)
            if session is not None and session.skill_name == "video-ai":
                session.artifacts["credential_handoff"] = (
                    plan.credential_handoff.model_dump(mode="json")
                )
                session.artifacts["video_review_plan"] = plan.model_dump(mode="json")
                await TelegramSkillSessionStore.set_session(telegram_chat_id, session)

        return {
            "status": "handoff_completed",
            "message": (
                "Authenticated PC capture handoff completed. Return to Telegram and tap Retry Start to continue."
            ),
            "execution_mode": plan.execution_mode,
            "credential_handoff": plan.credential_handoff.model_dump(mode="json"),
            "video_review_plan": plan.model_dump(mode="json"),
        }
