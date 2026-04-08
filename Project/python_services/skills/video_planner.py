"""Telegram-first video planning skill for /start onboarding."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.contracts import (
    CredentialHandoffContract,
    RecordedDemoEvidenceContract,
    VideoReviewPlanContract,
    WebPageReviewContract,
)
from services.video_planner_handoff_service import VideoPlannerHandoffService
from services.website_review_service import WebsiteReviewService

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

_DEFINITION = get_skill_definition("video-planner")


def _normalize_url(raw_url: str) -> str:
    return WebsiteReviewService.normalize_url(raw_url)
class VideoPlannerSkill(BaseSkill):
    name = "video-planner"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "Internal planner")
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = _DEFINITION.get("session_shape", BaseSkill.session_shape)

    @classmethod
    def _persona_label(cls, session: SkillSession) -> str:
        persona_id = str(session.collected.get("persona_id") or "").strip()
        available = session.artifacts.get("available_personas") or []
        for item in available:
            if str(item.get("persona_id") or "").strip() == persona_id:
                return str(item.get("display_name") or persona_id).strip() or persona_id
        return persona_id or "-"

    @classmethod
    def _build_credential_handoff(
        cls,
        execution_mode: str,
    ) -> CredentialHandoffContract:
        if execution_mode == "authenticated_pc_recording":
            return CredentialHandoffContract(
                status="required",
                handoff_method="workspace_link",
                credential_label="workspace login handoff",
                notes=[
                    "Raw credentials must not be collected in Telegram chat.",
                    "Execution stays blocked until secure workspace handoff is completed.",
                ],
            )
        return CredentialHandoffContract(status="not_required", handoff_method="none")

    @classmethod
    def _plan_summary(cls, plan: VideoReviewPlanContract, session: SkillSession) -> str:
        page_review = plan.page_review
        credential = plan.credential_handoff
        return "\n".join(
            [
                "Video Review Plan",
                "",
                f"Objective: {plan.objective}",
                f"Target URL: {plan.target_url}",
                f"Language: {plan.language}",
                f"Persona: {cls._persona_label(session)}",
                f"Execution Mode: {plan.execution_mode}",
                f"Access Level: {plan.access_level}",
                "",
                f"Page Review: {(page_review.product_summary if page_review else 'Pending')}",
                f"Credential Handoff: {credential.status}",
                "",
                "Confirm this plan to lock it in, or revise one of the inputs below.",
            ]
        )

    @classmethod
    def _manual_video_goal(cls, objective: str) -> str:
        normalized = str(objective or "").lower()
        if any(token in normalized for token in ["tutorial", "walkthrough", "guide"]):
            return "walkthrough"
        if any(token in normalized for token in ["signup", "buy", "convert", "cta"]):
            return "conversion"
        return "feature_demo"

    @classmethod
    async def continue_manual_mobile_pipeline(
        cls,
        planner_session: SkillSession,
        *,
        backend_url: str,
        http_client: Any,
        file_id: str,
        asset_url: str,
        asset_id: str | None,
        filename: str,
        quality_report: Dict[str, Any],
    ) -> SkillResult:
        from skills.video_ai import VideoAISkill

        plan_payload = planner_session.artifacts.get("video_review_plan") or {}
        plan = VideoReviewPlanContract.model_validate(plan_payload)
        video_session = VideoAISkill.initial_session()
        video_session.artifacts["telegram_chat_id"] = planner_session.artifacts.get(
            "telegram_chat_id"
        )
        video_session.artifacts["persona_snapshot"] = planner_session.artifacts.get(
            "persona_snapshot"
        )
        video_session.collected.update(
            {
                "creative_input_mode": "recorded_demo_video",
                "persona_id": plan.persona_id,
                "video_goal": cls._manual_video_goal(plan.objective),
                "audience": "mobile viewers evaluating the product",
                "cta": "Learn more on the website",
                "reference_url": plan.target_url,
                "access_level": (
                    "has_logged_in_access"
                    if plan.execution_mode == "manual_mobile_recording"
                    else plan.access_level
                ),
                "demo_video_telegram_file_id": file_id,
                "demo_video_asset_url": asset_url,
                "platform": "tiktok",
                "feature_emphasis": plan.objective,
            }
        )
        video_session.artifacts["demo_video_asset_id"] = asset_id
        video_session.artifacts["demo_video_filename"] = filename
        video_session.artifacts["demo_video_quality_report"] = quality_report
        video_session.artifacts["video_review_plan"] = plan.model_dump(mode="json")

        evidence = await VideoAISkill._run_demo_analysis_and_grounding(
            video_session,
            backend_url,
            http_client,
        )
        video_session.artifacts["demo_evidence"] = evidence.model_dump(mode="json")
        video_session.artifacts["demo_preview_confirmed"] = True
        video_session.artifacts["manual_mobile_mode"] = True

        result = await VideoAISkill.execute(video_session, backend_url, http_client)
        if not result.success or result.session is None:
            return result

        current = result.session
        if result.next_step == "confirm_concept":
            current.artifacts["concept_approved"] = True
            result = await VideoAISkill.execute(current, backend_url, http_client)
            if not result.success or result.session is None:
                return result
            current = result.session

        if result.next_step == "confirm_beats":
            current.artifacts["beat_sheet_approved"] = True
            result = await VideoAISkill.execute(current, backend_url, http_client)

        return result

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)

        decision = str(current.collected.get("plan_decision") or "").strip()
        if current.step_key == "confirm_plan" and decision:
            current.collected["plan_decision"] = None
            if decision == "confirm":
                plan_payload = current.artifacts.get("video_review_plan") or {}
                plan = VideoReviewPlanContract.model_validate(plan_payload)
                plan.status = "confirmed"
                current.artifacts["video_review_plan"] = plan.model_dump(mode="json")
                persona_snapshot = current.artifacts.get("persona_snapshot") or {
                    "persona_id": plan.persona_id,
                    "display_name": cls._persona_label(current),
                    "language": plan.language,
                }
                handoff = await VideoPlannerHandoffService.start_confirmed_plan(
                    plan=plan,
                    persona_snapshot=persona_snapshot,
                    backend_url=backend_url,
                    http_client=http_client,
                    telegram_chat_id=str(
                        current.artifacts.get("telegram_chat_id") or ""
                    ).strip()
                    or None,
                )
                current.artifacts["execution_handoff"] = handoff
                workflow_id = handoff.get("workflow_id")
                if workflow_id:
                    current.control.workflow_id = workflow_id
                    current.control.status = SkillStatus.waiting_approval
                    current.step_key = "done"
                elif handoff.get("status") == "awaiting_manual_upload":
                    current.control.status = SkillStatus.collecting
                    current.step_key = "upload_manual_video"
                elif handoff.get("status") == "handoff_blocked":
                    current.control.status = SkillStatus.collecting
                    current.step_key = "confirm_plan"
                else:
                    current.control.status = SkillStatus.done
                    current.step_key = "done"
                return SkillResult(
                    success=True,
                    next_step=current.step_key,
                    output={
                        "message": handoff.get("message")
                        or "Video review plan confirmed.",
                        "workflow_id": workflow_id,
                        "status": handoff.get("status"),
                        "execution_mode": handoff.get("execution_mode"),
                        "credential_handoff": handoff.get("credential_handoff"),
                        "handoff_url": handoff.get("handoff_url"),
                        "video_review_plan": plan.model_dump(mode="json"),
                    },
                    session=current,
                )
            if decision == "revise_objective":
                current.collected["objective"] = None
                current.artifacts["video_review_plan"] = None
                return cls._collecting_result(
                    current,
                    next_step="collect_objective",
                    output={"message": "Send the updated objective for this video plan."},
                )
            if decision == "revise_url":
                current.collected["target_url"] = None
                current.artifacts["page_review"] = None
                current.artifacts["video_review_plan"] = None
                return cls._collecting_result(
                    current,
                    next_step="collect_target_url",
                    output={"message": "Send the updated target URL."},
                )
            if decision == "revise_persona":
                current.collected["persona_id"] = None
                current.artifacts["video_review_plan"] = None
                return cls._collecting_result(
                    current,
                    next_step="pick_persona",
                    output={"message": "Choose a different persona for this plan."},
                )
            if decision == "revise_mode":
                current.collected["execution_mode"] = None
                current.artifacts["video_review_plan"] = None
                return cls._collecting_result(
                    current,
                    next_step="choose_execution_mode",
                    output={"message": "Choose a different execution mode for this plan."},
                )
            return cls._error_result(current, f"Unsupported plan decision: {decision}")

        if not cls._has_value(current.collected.get("objective")):
            return cls._collecting_result(current, next_step="collect_objective")

        target_url = _normalize_url(str(current.collected.get("target_url") or ""))
        if not target_url:
            return cls._collecting_result(current, next_step="collect_target_url")
        current.collected["target_url"] = target_url

        if not current.artifacts.get("page_review"):
            page_review = await WebsiteReviewService.review_url(
                target_url,
                objective=str(current.collected.get("objective") or "").strip(),
                user_id=f"telegram:{current.artifacts.get('telegram_chat_id', 'unknown')}",
            )
            current.artifacts["page_review"] = page_review.model_dump(mode="json")
            return cls._collecting_result(
                current,
                next_step="choose_language",
                output={
                    "message": (
                        f"Website review ready for {page_review.normalized_url}\n\n"
                        f"Summary: {page_review.product_summary}\n"
                        f"Access Level: {page_review.access_level}\n"
                        f"Login Required: {'yes' if page_review.login_required else 'no'}"
                    )
                },
            )

        if not cls._has_value(current.collected.get("language")):
            return cls._collecting_result(current, next_step="choose_language")

        if not cls._has_value(current.collected.get("persona_id")):
            return cls._collecting_result(current, next_step="pick_persona")

        if not cls._has_value(current.collected.get("execution_mode")):
            return cls._collecting_result(current, next_step="choose_execution_mode")

        if current.step_key == "upload_manual_video":
            current.collected["manual_upload_note"] = None
            return cls._collecting_result(
                current,
                next_step="upload_manual_video",
                output={
                    "message": (
                        "Upload the mobile-recorded video now. "
                        "Keep the footage vertical so the final output stays on the current 9:16 canvas."
                    )
                },
            )

        plan_payload = current.artifacts.get("video_review_plan")
        if not plan_payload:
            page_review = WebPageReviewContract.model_validate(
                current.artifacts.get("page_review") or {}
            )
            execution_mode = str(current.collected.get("execution_mode") or "").strip()
            credential_handoff = cls._build_credential_handoff(execution_mode)
            access_level = (
                "has_logged_in_access"
                if execution_mode == "authenticated_pc_recording"
                else page_review.access_level
            )
            plan = VideoReviewPlanContract(
                planning_mode="webpage_review",
                objective=str(current.collected.get("objective") or "").strip(),
                target_url=target_url,
                language=str(current.collected.get("language") or "").strip(),
                persona_id=str(current.collected.get("persona_id") or "").strip(),
                execution_mode=execution_mode,
                access_level=access_level,
                page_review=page_review,
                credential_handoff=credential_handoff,
                assumptions=[
                    "The confirmed plan will later feed the production workflow after explicit approval.",
                ],
                risks=list(page_review.risks),
            )
            current.artifacts["video_review_plan"] = plan.model_dump(mode="json")
            return cls._collecting_result(
                current,
                next_step="confirm_plan",
                output={
                    "message": cls._plan_summary(plan, current),
                    "video_review_plan": plan.model_dump(mode="json"),
                },
            )

        plan = VideoReviewPlanContract.model_validate(plan_payload)
        return cls._collecting_result(
            current,
            next_step="confirm_plan",
            output={
                "message": cls._plan_summary(plan, current),
                "video_review_plan": plan.model_dump(mode="json"),
            },
        )
