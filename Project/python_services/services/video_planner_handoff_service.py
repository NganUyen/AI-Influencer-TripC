"""Convert confirmed Telegram review plans into execution handoff actions."""

from __future__ import annotations

from typing import Any, Dict

import httpx

from services.contracts import VideoReviewPlanContract
from services.telegram_link_service import TelegramLinkService
from services.video_capture_handoff_service import VideoCaptureHandoffService


class VideoPlannerHandoffService:
    @classmethod
    async def _start_review_plan_workflow(
        cls,
        *,
        plan: VideoReviewPlanContract,
        backend_url: str,
        http_client: Any,
        telegram_chat_id: str | None,
    ) -> Dict[str, Any]:
        response = await http_client.post(
            f"{backend_url.rstrip('/')}/api/workflows/start-video",
            json={
                "persona_id": plan.persona_id,
                "topic": plan.objective,
                "tone": "natural",
                "platform": "tiktok",
                "telegram_chat_id": telegram_chat_id,
                "talking_head_optional": True,
                "review_plan": plan.model_dump(mode="json"),
                "execution_mode": plan.execution_mode,
                "audio_policy": plan.audio_policy.model_dump(mode="json"),
            },
            headers={"x-internal-api-token": cls._internal_api_token()},
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Workflow start response must be a JSON object")
        data.setdefault("execution_mode", plan.execution_mode)
        data.setdefault("video_review_plan", plan.model_dump(mode="json"))
        return data

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
        if plan.status != "confirmed":
            raise ValueError("Video review plan must be confirmed before execution handoff")

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
                    "credential_handoff": plan.credential_handoff.model_dump(mode="json"),
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
                    "Upload the recorded mobile video next and the system will process it on the current vertical output canvas."
                ),
                "video_review_plan": plan.model_dump(mode="json"),
            }

        if execution_mode != "autonomous_screen_recording":
            raise ValueError(f"Unsupported execution mode: {execution_mode}")

        return await cls._start_review_plan_workflow(
            plan=plan,
            backend_url=backend_url,
            http_client=http_client,
            telegram_chat_id=telegram_chat_id,
        )

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

        data = await cls._start_review_plan_workflow(
            plan=plan,
            backend_url=backend_url,
            http_client=http_client,
            telegram_chat_id=handoff_payload.get("telegram_chat_id"),
        )
        data["credential_handoff"] = plan.credential_handoff.model_dump(mode="json")
        return data

    @staticmethod
    def _internal_api_token() -> str:
        try:
            from config.settings import settings

            return (getattr(settings, "INTERNAL_API_TOKEN", None) or "").strip()
        except Exception:
            return ""
