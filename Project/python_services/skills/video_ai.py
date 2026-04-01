"""AI influencer video pre-production skill wrapper."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from services.contracts import (
    ApprovedProductionPackageContract,
    BeatSheetContract,
    ConceptBriefContract,
    RecordedDemoEvidenceContract,
)
from services.creative_director_service import CreativeDirectorService
from services.demo_feature_grounding_service import (
    DemoFeatureGroundingService,
    build_preview_summary,
)
from services.demo_video_analyzer_service import DemoVideoAnalyzerService
from services.recorded_demo_failure_policy import (
    build_preview_warnings,
    should_block_before_concept,
)

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

logger = logging.getLogger(__name__)

_DEFINITION = get_skill_definition("video-ai")

_FIELD_TO_STEP = {
    "persona_id": "pick_persona",
    "idea_brief": "collect_idea_brief",
    "feature_focus": "collect_feature_focus",
    "video_goal": "choose_video_goal",
    "audience": "collect_audience",
    "cta": "collect_cta",
    "reference_url": "collect_reference_url",
    "access_level": "choose_access_level",
    "demo_video_telegram_file_id": "upload_demo_video",
}
_RESETTABLE_FIELDS = [
    "idea_brief",
    "feature_focus",
    "feature_emphasis",
    "video_goal",
    "audience",
    "cta",
    "reference_url",
    "access_level",
    "demo_video_telegram_file_id",
    "demo_video_asset_url",
]


class VideoAISkill(BaseSkill):
    name = "video-ai"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get(
        "target", "Internal CreativeDirectorService"
    )
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def initial_session(cls) -> SkillSession:
        session = super().initial_session()
        session.collected["platform"] = session.collected.get("platform") or "tiktok"
        session.collected["creative_input_mode"] = (
            session.collected.get("creative_input_mode") or "idea_brief"
        )
        session.artifacts.setdefault("persona_snapshot", None)
        session.artifacts.setdefault("persona_readiness", None)
        session.artifacts.setdefault("workflow_id", None)
        session.artifacts.setdefault("talking_head_optional", False)
        session.artifacts.setdefault("production_note", None)
        session.artifacts.setdefault("concept_brief", None)
        session.artifacts.setdefault("beat_sheet", None)
        session.artifacts.setdefault("approved_production_package", None)
        session.artifacts.setdefault("concept_approved", False)
        session.artifacts.setdefault("beat_sheet_approved", False)
        # Phase 5: Demo video preview confirmation artifacts
        session.artifacts.setdefault("demo_evidence", None)
        session.artifacts.setdefault("demo_preview_summary", None)
        session.artifacts.setdefault("demo_preview_confirmed", False)
        session.artifacts.setdefault("demo_preview_timeout_at", None)
        return session

    @classmethod
    def _can_continue_without_talking_head(cls, readiness: Dict[str, Any]) -> bool:
        checks = readiness.get("checks") or {}
        return (
            bool(checks.get("status_ready"))
            and bool(checks.get("has_tts_voice"))
            and bool(checks.get("has_avatar_asset"))
            and not bool(checks.get("has_heygen_avatar_id"))
        )

    @classmethod
    def _production_note(cls, *, talking_head_optional: bool) -> Optional[str]:
        if not talking_head_optional:
            return None
        return (
            "This persona does not have a HeyGen talking-head avatar yet, "
            "so the video will use scene visuals with voiceover instead."
        )

    @classmethod
    def _missing_step(cls, session: SkillSession) -> Optional[str]:
        """Determine next required step based on creative_input_mode and missing params."""
        creative_input_mode = session.collected.get("creative_input_mode", "idea_brief")

        # Mode selection is first if not set
        if not creative_input_mode:
            return "select_mode"

        # Check persona_id first (required for both modes)
        if not session.collected.get("persona_id"):
            return "pick_persona"

        # For recorded_demo_video mode
        if creative_input_mode == "recorded_demo_video":
            if not session.collected.get("demo_video_telegram_file_id"):
                return "upload_demo_video"
            # Skip idea_brief and feature_focus, they're not required
            # Continue with other required fields
            if not session.collected.get("video_goal"):
                return "choose_video_goal"
            if not session.collected.get("audience"):
                return "collect_audience"
            if not session.collected.get("cta"):
                return "collect_cta"
            if not session.collected.get("reference_url"):
                return "collect_reference_url"
            if not session.collected.get("access_level"):
                return "choose_access_level"
            # Phase 5: Check if demo preview has been confirmed
            if not session.artifacts.get("demo_preview_confirmed"):
                return "demo_preview_confirm"
            return None

        # For idea_brief mode (original flow)
        # idea_brief and feature_focus are required in this mode
        if not session.collected.get("idea_brief"):
            return "collect_idea_brief"
        if not session.collected.get("feature_focus"):
            return "collect_feature_focus"
        # Then check remaining required params
        missing = cls._missing_required_params(session)
        if not missing:
            return None
        return _FIELD_TO_STEP.get(missing[0], "choose_video_goal")

    @classmethod
    async def _resolve_persona_snapshot(
        cls,
        session: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> Dict[str, Any]:
        persona_id = session.collected.get("persona_id")
        snapshot = session.artifacts.get("persona_snapshot") or {}
        if snapshot.get("persona_id") == persona_id and snapshot.get("tone_resolved"):
            session.artifacts["talking_head_optional"] = not bool(
                snapshot.get("heygen_avatar_id")
            )
            session.artifacts["production_note"] = cls._production_note(
                talking_head_optional=session.artifacts["talking_head_optional"]
            )
            return snapshot

        # Build owner_key from telegram_chat_id for proper scoping
        telegram_chat_id = session.artifacts.get("telegram_chat_id")
        owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None
        owner_param = f"?owner_key={owner_key}" if owner_key else ""

        readiness = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{persona_id}/readiness{owner_param}",
        )
        session.artifacts["persona_readiness"] = readiness
        talking_head_optional = cls._can_continue_without_talking_head(readiness)
        session.artifacts["talking_head_optional"] = talking_head_optional
        session.artifacts["production_note"] = cls._production_note(
            talking_head_optional=talking_head_optional
        )
        if not readiness.get("ready") and not talking_head_optional:
            raise ValueError(
                readiness.get("blocking_reason") or "Selected persona is not ready."
            )

        persona = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{persona_id}{owner_param}",
        )
        if not persona.get("persona_id"):
            raise ValueError("Selected persona could not be loaded.")
        if persona.get("status") != "ready":
            raise ValueError(
                readiness.get("blocking_reason") or "Selected persona is not ready."
            )
        if not persona.get("tts_voice"):
            raise ValueError(
                readiness.get("blocking_reason")
                or "Selected persona is missing tts_voice."
            )

        talking_head_optional = talking_head_optional and not bool(
            persona.get("heygen_avatar_id")
        )
        session.artifacts["talking_head_optional"] = talking_head_optional
        session.artifacts["production_note"] = cls._production_note(
            talking_head_optional=talking_head_optional
        )
        tone_resolved = (
            str(persona.get("tone_default") or "natural").strip() or "natural"
        )
        resolved_snapshot = {
            "persona_id": persona.get("persona_id"),
            "display_name": persona.get("display_name") or persona.get("persona_id"),
            "language": persona.get("language") or "English",
            "tts_voice": persona.get("tts_voice"),
            "tone_default": persona.get("tone_default"),
            "tone_resolved": tone_resolved,
            "heygen_avatar_id": persona.get("heygen_avatar_id"),
            "talking_head_optional": talking_head_optional,
            "status": persona.get("status"),
        }
        session.artifacts["persona_snapshot"] = resolved_snapshot
        return resolved_snapshot

    @classmethod
    async def _run_demo_analysis_and_grounding(
        cls,
        session: SkillSession,
        backend_url: str,
        http_client: Any,
    ) -> RecordedDemoEvidenceContract:
        """
        Run Phase 4 analysis and Phase 5 grounding for recorded_demo_video mode.

        This method:
        1. Calls DemoVideoAnalyzerService to analyze the uploaded video
        2. Calls DemoFeatureGroundingService to ground features against official website
        3. Returns the enriched RecordedDemoEvidenceContract

        Raises:
            ValueError: If video asset URL is missing or analysis fails
        """
        demo_video_url = session.collected.get("demo_video_asset_url")
        if not demo_video_url:
            raise ValueError("Demo video asset URL is missing. Please re-upload.")

        reference_url = session.collected.get("reference_url", "")
        video_goal = session.collected.get("video_goal", "feature_demo")
        audience = session.collected.get("audience", "")
        cta = session.collected.get("cta", "")
        telegram_chat_id = session.artifacts.get("telegram_chat_id")
        user_id = f"telegram:{telegram_chat_id}" if telegram_chat_id else "system"

        # Phase 4: Run video analysis
        logger.info("Running Phase 4 demo video analysis for %s", demo_video_url)
        analyzer = DemoVideoAnalyzerService()
        evidence = await analyzer.analyze_demo_video(
            video_url=demo_video_url,
            reference_url=reference_url,
            video_goal=video_goal,
            audience=audience,
            cta=cta,
        )

        # Store quality report from Phase 3 if available
        quality_report = session.artifacts.get("demo_video_quality_report")
        if quality_report:
            evidence.confidence_signals["quality_report"] = quality_report

        # Phase 5: Run feature grounding against official website
        if reference_url:
            logger.info(
                "Running Phase 5 feature grounding against %s",
                reference_url,
            )
            grounding_service = DemoFeatureGroundingService()
            evidence = await grounding_service.ground_features(
                evidence=evidence,
                reference_url=reference_url,
                project_name=None,  # Will be inferred from website
                video_goal=video_goal,
                audience=audience,
                cta=cta,
                user_id=user_id,
            )
        else:
            logger.info("No reference_url provided, skipping feature grounding")
            evidence.grounding_completed = False

        logger.info(
            "Demo analysis complete: %d features, %d grounded",
            len(evidence.extracted_features),
            sum(1 for f in evidence.grounded_features if f.grounded),
        )

        return evidence

    @classmethod
    def _preview_result(
        cls,
        session: SkillSession,
        *,
        step_key: str,
        output: Dict[str, Any],
    ) -> SkillResult:
        session.control.status = SkillStatus.preview_ready
        session.step_key = step_key
        return SkillResult(
            success=True,
            next_step=step_key,
            output=output,
            session=session,
        )

    @classmethod
    def _active_workflow_id(cls, session: SkillSession) -> Optional[str]:
        workflow_id = session.control.workflow_id or session.artifacts.get(
            "workflow_id"
        )
        normalized = str(workflow_id or "").strip()
        return normalized or None

    @classmethod
    def _workflow_started_result(
        cls,
        session: SkillSession,
        *,
        workflow_id: str,
        message: Optional[str] = None,
    ) -> SkillResult:
        talking_head_optional = bool(session.artifacts.get("talking_head_optional"))
        production_note = session.artifacts.get(
            "production_note"
        ) or cls._production_note(talking_head_optional=talking_head_optional)
        session.artifacts["production_note"] = production_note
        session.artifacts["workflow_id"] = workflow_id
        session.control.status = SkillStatus.waiting_approval
        session.control.workflow_id = workflow_id
        session.control.approval_required = False
        session.control.error_message = None
        session.step_key = "package_ready"
        return SkillResult(
            success=True,
            next_step="poll_status",
            output={
                "message": message
                or (
                    "Production workflow is already running.\n\n"
                    "I’m keeping this session attached so you can cancel it if needed."
                ),
                "approved_production_package": session.artifacts.get(
                    "approved_production_package"
                ),
                "workflow_id": workflow_id,
                "status": "started",
                "talking_head_optional": talking_head_optional,
                "production_mode": (
                    "voiceover_only" if talking_head_optional else "talking_head"
                ),
                "production_note": production_note,
            },
            session=session,
        )

    @classmethod
    async def _package_ready_result(
        cls,
        session: SkillSession,
        package: ApprovedProductionPackageContract,
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        """Package is ready. Trigger the production workflow."""
        session.step_key = "package_ready"
        existing_workflow_id = cls._active_workflow_id(session)
        if existing_workflow_id:
            return cls._workflow_started_result(
                session,
                workflow_id=existing_workflow_id,
            )

        # Prepare payload for production workflow
        persona_id = session.collected.get("persona_id")
        telegram_chat_id = session.artifacts.get("telegram_chat_id")
        platform = session.collected.get("platform", "tiktok")
        topic = session.collected.get("idea_brief", "")
        talking_head_optional = bool(session.artifacts.get("talking_head_optional"))
        production_note = cls._production_note(
            talking_head_optional=talking_head_optional
        )
        session.artifacts["production_note"] = production_note

        production_payload = {
            "persona_id": persona_id,
            "topic": topic,
            "tone": "natural",
            "platform": platform,
            "telegram_chat_id": telegram_chat_id,
            "user_id": None,
            "owner_key": f"telegram:{telegram_chat_id}" if telegram_chat_id else None,
            "talking_head_optional": talking_head_optional,
            "approved_package": package.model_dump(mode="json"),
        }

        # Call the production workflow API
        try:
            response = await http_client.post(
                cls._build_url(backend_url, "/api/workflows/start-video"),
                json=production_payload,
                headers=cls._auth_headers(),
            )
            response.raise_for_status()
            workflow_data = response.json()
            workflow_id = workflow_data.get("workflow_id", "unknown")
            session.artifacts["approved_production_package"] = package.model_dump(
                mode="json"
            )
            return cls._workflow_started_result(
                session,
                workflow_id=workflow_id,
                message=(
                    f"Production workflow started! Workflow ID: {workflow_id}\n\n"
                    "I'm now generating the full video. This may take a few minutes..."
                ),
            )
        except Exception as exc:
            session.control.status = SkillStatus.failed
            session.control.workflow_id = None
            session.control.error_message = str(exc)
            session.artifacts["workflow_id"] = None
            return SkillResult(
                success=False,
                next_step="package_ready",
                output={
                    "message": "Pre-production package is ready, but I couldn't start the production workflow.",
                    "approved_production_package": package.model_dump(mode="json"),
                    "talking_head_optional": talking_head_optional,
                    "production_mode": (
                        "voiceover_only" if talking_head_optional else "talking_head"
                    ),
                    "production_note": production_note,
                },
                error=str(exc),
                session=session,
            )

    @classmethod
    def _retryable_error_result(
        cls,
        session: SkillSession,
        *,
        step_key: str,
        error: str,
        output: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        session.control.status = SkillStatus.failed
        session.control.error_message = error
        session.step_key = step_key
        merged_output = {"retryable": True}
        if output:
            merged_output.update(output)
        return SkillResult(
            success=False,
            next_step=step_key,
            output=merged_output,
            error=error,
            session=session,
        )

    @classmethod
    def _restart_collection(cls, session: SkillSession, *, message: str) -> SkillResult:
        """Reset collected fields and restart from appropriate step based on mode."""
        for field in _RESETTABLE_FIELDS:
            session.collected[field] = None
        session.artifacts["talking_head_optional"] = False
        session.artifacts["production_note"] = None
        session.artifacts["concept_brief"] = None
        session.artifacts["beat_sheet"] = None
        session.artifacts["approved_production_package"] = None
        session.artifacts["workflow_id"] = None
        session.artifacts["concept_approved"] = False
        session.artifacts["beat_sheet_approved"] = False
        # Phase 5: Reset demo preview artifacts
        session.artifacts["demo_evidence"] = None
        session.artifacts["demo_preview_summary"] = None
        session.artifacts["demo_preview_confirmed"] = False
        session.artifacts["demo_preview_timeout_at"] = None
        session.control.workflow_id = None
        session.control.approval_required = False
        session.control.error_message = None
        session.control.status = SkillStatus.collecting

        # Determine restart step based on mode
        creative_input_mode = session.collected.get("creative_input_mode", "idea_brief")
        if creative_input_mode == "recorded_demo_video":
            session.step_key = "upload_demo_video"
            next_step = "upload_demo_video"
        else:
            session.step_key = "collect_idea_brief"
            next_step = "collect_idea_brief"

        return SkillResult(
            success=True,
            next_step=next_step,
            output={"message": message},
            session=session,
        )

    @classmethod
    async def handle_preproduction_action(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        action: str,
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        active_workflow_id = cls._active_workflow_id(current)
        if active_workflow_id:
            return cls._workflow_started_result(
                current,
                workflow_id=active_workflow_id,
            )

        if current.step_key == "package_ready" and action in {"approve", "retry_start"}:
            package_payload = current.artifacts.get("approved_production_package")
            if not package_payload:
                return cls._error_result(
                    current,
                    "Approved production package is missing. Please rebuild the beat plan first.",
                )
            try:
                package = ApprovedProductionPackageContract.model_validate(
                    package_payload
                )
            except ValidationError:
                current.artifacts["approved_production_package"] = None
                return cls._error_result(
                    current,
                    "Approved production package is invalid. Please regenerate the beat plan and try again.",
                )
            return await cls._package_ready_result(
                current,
                package,
                backend_url,
                http_client,
            )

        if current.step_key == "confirm_concept":
            if action == "approve":
                current.artifacts["concept_approved"] = True
                current.artifacts["beat_sheet"] = None
                current.artifacts["approved_production_package"] = None
                current.artifacts["beat_sheet_approved"] = False
                return await cls.execute(current, backend_url, http_client)
            if action == "regenerate":
                current.artifacts["concept_brief"] = None
                current.artifacts["concept_approved"] = False
                current.artifacts["beat_sheet"] = None
                current.artifacts["beat_sheet_approved"] = False
                current.artifacts["approved_production_package"] = None
                return await cls.execute(current, backend_url, http_client)
            if action == "edit":
                return cls._restart_collection(
                    current,
                    message="Okay. Send an updated video idea and I will rebuild the concept from scratch.",
                )
        if current.step_key == "confirm_beats":
            if action == "approve":
                current.artifacts["beat_sheet_approved"] = True
                return await cls.execute(current, backend_url, http_client)
            if action == "regenerate":
                current.artifacts["beat_sheet"] = None
                current.artifacts["beat_sheet_approved"] = False
                current.artifacts["approved_production_package"] = None
                return await cls.execute(current, backend_url, http_client)
            if action == "edit":
                return cls._restart_collection(
                    current,
                    message="Okay. Let's revise the concept inputs first, then I will rebuild the beat plan.",
                )
        return cls._error_result(
            current, f"Unsupported action for {current.step_key}: {action}"
        )

    @classmethod
    async def handle_demo_preview_action(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        action: str,
        backend_url: str,
        http_client: Any,
        *,
        correction_text: Optional[str] = None,
        reemphasis_text: Optional[str] = None,
    ) -> SkillResult:
        """
        Handle demo preview confirmation actions (Phase 5).

        Actions:
        - confirm: User confirms the analysis, proceed to ConceptBrief generation
        - correct: User wants to correct feature misunderstandings
        - reemphasize: User wants to focus on specific features
        - reupload: User wants to re-upload a different demo video
        - timeout: System-triggered timeout (abort, not auto-confirm)
        """
        current = cls._normalize_session(session)

        # Only handle if we're at the demo_preview_confirm step
        if current.step_key != "demo_preview_confirm":
            return cls._error_result(
                current,
                f"Demo preview action not applicable at step: {current.step_key}",
            )

        if action == "confirm":
            # User confirms the analysis - proceed to ConceptBrief generation
            current.artifacts["demo_preview_confirmed"] = True
            current.artifacts["demo_preview_timeout_at"] = None
            logger.info("Demo preview confirmed by user, proceeding to ConceptBrief")
            return await cls.execute(current, backend_url, http_client)

        if action == "correct":
            if correction_text:
                # Apply correction to evidence
                evidence_payload = current.artifacts.get("demo_evidence")
                if evidence_payload:
                    try:
                        evidence = RecordedDemoEvidenceContract.model_validate(
                            evidence_payload
                        )
                        # Store correction for later use in ConceptBrief generation
                        evidence.confidence_signals["user_correction"] = correction_text
                        current.artifacts["demo_evidence"] = evidence.model_dump(
                            mode="json"
                        )
                    except ValidationError:
                        pass
                # Mark as confirmed after correction
                current.artifacts["demo_preview_confirmed"] = True
                current.artifacts["demo_preview_timeout_at"] = None
                logger.info(
                    "Demo preview confirmed with correction: %s", correction_text
                )
                return await cls.execute(current, backend_url, http_client)
            else:
                # Need to collect correction text
                current.step_key = "demo_correct_features"
                return cls._collecting_result(
                    current, next_step="demo_correct_features"
                )

        if action == "reemphasize":
            if reemphasis_text:
                # Apply re-emphasis to feature_emphasis field
                current.collected["feature_emphasis"] = reemphasis_text
                evidence_payload = current.artifacts.get("demo_evidence")
                if evidence_payload:
                    try:
                        evidence = RecordedDemoEvidenceContract.model_validate(
                            evidence_payload
                        )
                        evidence.confidence_signals["user_reemphasis"] = reemphasis_text
                        current.artifacts["demo_evidence"] = evidence.model_dump(
                            mode="json"
                        )
                    except ValidationError:
                        pass
                # Mark as confirmed after re-emphasis
                current.artifacts["demo_preview_confirmed"] = True
                current.artifacts["demo_preview_timeout_at"] = None
                logger.info(
                    "Demo preview confirmed with re-emphasis: %s", reemphasis_text
                )
                return await cls.execute(current, backend_url, http_client)
            else:
                # Need to collect re-emphasis text
                current.step_key = "demo_reemphasize_features"
                return cls._collecting_result(
                    current, next_step="demo_reemphasize_features"
                )

        if action == "reupload":
            # Reset demo video artifacts and restart from upload step
            current.collected["demo_video_telegram_file_id"] = None
            current.collected["demo_video_asset_url"] = None
            current.artifacts["demo_evidence"] = None
            current.artifacts["demo_preview_summary"] = None
            current.artifacts["demo_preview_confirmed"] = False
            current.artifacts["demo_preview_timeout_at"] = None
            current.artifacts["demo_video_quality_report"] = None
            current.step_key = "upload_demo_video"
            return cls._collecting_result(
                current,
                next_step="upload_demo_video",
                output={"message": "Please upload a new demo video."},
            )

        if action == "timeout":
            # Timeout abort - do NOT auto-confirm per spec
            current.control.status = SkillStatus.failed
            current.control.error_message = (
                "Demo preview confirmation timed out (15 minutes). "
                "Please start again or re-upload the video."
            )
            current.step_key = "demo_preview_confirm"
            logger.warning("Demo preview timed out, aborting (not auto-confirming)")
            return SkillResult(
                success=False,
                next_step="demo_preview_confirm",
                output={
                    "message": (
                        "Preview confirmation timed out after 15 minutes.\n\n"
                        "The session has been paused. You can:\n"
                        "• Re-upload the video to start fresh\n"
                        "• Contact support if you need assistance"
                    ),
                    "timeout": True,
                    "retryable": True,
                },
                error="Preview confirmation timed out",
                session=current,
            )

        return cls._error_result(current, f"Unknown demo preview action: {action}")

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        current.collected["platform"] = current.collected.get("platform") or "tiktok"
        current.collected["creative_input_mode"] = (
            current.collected.get("creative_input_mode") or "idea_brief"
        )

        active_workflow_id = cls._active_workflow_id(current)
        if active_workflow_id:
            return cls._workflow_started_result(
                current,
                workflow_id=active_workflow_id,
            )

        # P0.4: Handle feature correction/reemphasis free-text submissions
        # When user types correction text after clicking "correct" button
        if current.step_key == "demo_correct_features" and current.collected.get(
            "feature_correction"
        ):
            correction_text = current.collected.get("feature_correction", "").strip()
            if correction_text:
                # Apply correction to evidence
                evidence_payload = current.artifacts.get("demo_evidence")
                if evidence_payload:
                    try:
                        evidence = RecordedDemoEvidenceContract.model_validate(
                            evidence_payload
                        )
                        evidence.confidence_signals["user_correction"] = correction_text
                        current.artifacts["demo_evidence"] = evidence.model_dump(
                            mode="json"
                        )
                    except ValidationError:
                        pass
                # Mark as confirmed and proceed
                current.artifacts["demo_preview_confirmed"] = True
                current.artifacts["demo_preview_timeout_at"] = None
                logger.info(
                    "Demo preview confirmed with correction (free-text): %s",
                    correction_text,
                )
                # Clear the step_key to allow normal flow
                current.step_key = None

        # When user types reemphasis text after clicking "reemphasize" button
        if current.step_key == "demo_reemphasize_features" and current.collected.get(
            "feature_reemphasis"
        ):
            reemphasis_text = current.collected.get("feature_reemphasis", "").strip()
            if reemphasis_text:
                # Apply re-emphasis
                current.collected["feature_emphasis"] = reemphasis_text
                evidence_payload = current.artifacts.get("demo_evidence")
                if evidence_payload:
                    try:
                        evidence = RecordedDemoEvidenceContract.model_validate(
                            evidence_payload
                        )
                        evidence.confidence_signals["user_reemphasis"] = reemphasis_text
                        current.artifacts["demo_evidence"] = evidence.model_dump(
                            mode="json"
                        )
                    except ValidationError:
                        pass
                # Mark as confirmed and proceed
                current.artifacts["demo_preview_confirmed"] = True
                current.artifacts["demo_preview_timeout_at"] = None
                logger.info(
                    "Demo preview confirmed with re-emphasis (free-text): %s",
                    reemphasis_text,
                )
                # Clear the step_key to allow normal flow
                current.step_key = None

        next_step = cls._missing_step(current)

        # Phase 5: For recorded_demo_video mode, run analysis and grounding before preview
        if (
            next_step == "demo_preview_confirm"
            and current.collected.get("creative_input_mode") == "recorded_demo_video"
            and not current.artifacts.get("demo_evidence")
        ):
            # Run Phase 4 analysis + Phase 5 grounding
            try:
                evidence = await cls._run_demo_analysis_and_grounding(
                    current, backend_url, http_client
                )
                current.artifacts["demo_evidence"] = evidence.model_dump(mode="json")

                # Build preview summary for Telegram rendering
                preview_summary = build_preview_summary(
                    evidence,
                    video_goal=current.collected.get("video_goal"),
                )

                # Phase 8: Add warnings from failure policy
                warnings = build_preview_warnings(evidence)
                if warnings:
                    preview_summary["warnings"] = warnings

                current.artifacts["demo_preview_summary"] = preview_summary

                # Set timeout timestamp (15 minutes from now)
                import time

                current.artifacts["demo_preview_timeout_at"] = int(time.time()) + 900
            except Exception as exc:
                logger.warning("Demo analysis/grounding failed: %s", exc)
                return cls._retryable_error_result(
                    current,
                    step_key="demo_preview_confirm",
                    error=f"Could not analyze demo video. Please try again or re-upload. ({exc})",
                    output={"retryable": True},
                )

        if next_step:
            # For demo_preview_confirm, include the preview summary in output
            if next_step == "demo_preview_confirm":
                preview_summary = current.artifacts.get("demo_preview_summary") or {}
                current.step_key = "demo_preview_confirm"
                current.control.status = SkillStatus.preview_ready
                return SkillResult(
                    success=True,
                    next_step="demo_preview_confirm",
                    output={
                        "message": "Demo video analysis complete. Please review.",
                        "demo_preview_summary": preview_summary,
                        "demo_evidence": current.artifacts.get("demo_evidence"),
                    },
                    session=current,
                )
            return cls._collecting_result(current, next_step=next_step)

        try:
            persona_snapshot = await cls._resolve_persona_snapshot(
                current, backend_url, http_client
            )
        except ValueError as exc:
            return cls._error_result(current, str(exc))

        concept_payload = current.artifacts.get("concept_brief")
        concept: Optional[ConceptBriefContract] = None
        if concept_payload:
            try:
                concept = ConceptBriefContract.model_validate(concept_payload)
            except ValidationError:
                current.artifacts["concept_brief"] = None
                current.artifacts["concept_approved"] = False
                current.artifacts["beat_sheet"] = None
                current.artifacts["beat_sheet_approved"] = False
                current.artifacts["approved_production_package"] = None
                concept_payload = None

        if not concept_payload:
            try:
                # Build concept based on input mode
                creative_input_mode = current.collected.get(
                    "creative_input_mode", "idea_brief"
                )

                if creative_input_mode == "recorded_demo_video":
                    evidence_payload = current.artifacts.get("demo_evidence")
                    if not evidence_payload:
                        raise ValueError(
                            "Recorded demo evidence is missing. Please re-run the preview step."
                        )
                    evidence = RecordedDemoEvidenceContract.model_validate(
                        evidence_payload
                    )

                    # Phase 8: Use failure policy for combined usability check
                    # Blocks only when low confidence + weak evidence combined
                    block_message = should_block_before_concept(evidence)
                    if block_message:
                        raise ValueError(block_message)

                    concept = (
                        await CreativeDirectorService.build_concept_from_demo_evidence(
                            evidence,
                            current.collected,
                            persona_snapshot,
                        )
                    )
                else:
                    # Original idea_brief flow
                    concept = await CreativeDirectorService.build_concept_brief(
                        current.collected,
                        persona_snapshot,
                    )
            except Exception as exc:
                return cls._retryable_error_result(
                    current,
                    step_key="confirm_concept",
                    error=f"Could not build the concept brief yet. Please try regenerate again. ({exc})",
                )
            current.artifacts["concept_brief"] = concept.model_dump(mode="json")
            current.artifacts["concept_approved"] = False
            current.artifacts["beat_sheet"] = None
            current.artifacts["beat_sheet_approved"] = False
            current.artifacts["approved_production_package"] = None
            return cls._preview_result(
                current,
                step_key="confirm_concept",
                output={
                    "message": "Concept brief ready for review.",
                    "concept_brief": current.artifacts["concept_brief"],
                    "persona_snapshot": persona_snapshot,
                },
            )

        if not current.artifacts.get("concept_approved"):
            return cls._preview_result(
                current,
                step_key="confirm_concept",
                output={
                    "message": "Concept brief ready for review.",
                    "concept_brief": concept.model_dump(mode="json"),
                    "persona_snapshot": persona_snapshot,
                },
            )

        beat_payload = current.artifacts.get("beat_sheet")
        beat_sheet: Optional[BeatSheetContract] = None
        if beat_payload:
            try:
                beat_sheet = BeatSheetContract.model_validate(beat_payload)
            except ValidationError:
                current.artifacts["beat_sheet"] = None
                current.artifacts["beat_sheet_approved"] = False
                current.artifacts["approved_production_package"] = None
                beat_payload = None

        if not beat_payload:
            try:
                if (
                    current.collected.get("creative_input_mode")
                    == "recorded_demo_video"
                ):
                    evidence_payload = current.artifacts.get("demo_evidence")
                    if not evidence_payload:
                        raise ValueError(
                            "Recorded demo evidence is missing. Please re-run the preview step."
                        )
                    evidence = RecordedDemoEvidenceContract.model_validate(
                        evidence_payload
                    )

                    # Phase 8: Use failure policy for combined usability check
                    block_message = should_block_before_concept(evidence)
                    if block_message:
                        raise ValueError(block_message)

                    beat_sheet = (
                        await CreativeDirectorService.build_beats_from_demo_evidence(
                            concept,
                            evidence,
                        )
                    )
                else:
                    beat_sheet = await CreativeDirectorService.build_beat_sheet(
                        concept, persona_snapshot
                    )
            except Exception as exc:
                return cls._retryable_error_result(
                    current,
                    step_key="confirm_beats",
                    error=f"Could not build the beat plan yet. Please try regenerate again. ({exc})",
                    output={"concept_brief": concept.model_dump(mode="json")},
                )
            current.artifacts["beat_sheet"] = beat_sheet.model_dump(mode="json")
            current.artifacts["beat_sheet_approved"] = False
            current.artifacts["approved_production_package"] = None
            return cls._preview_result(
                current,
                step_key="confirm_beats",
                output={
                    "message": "Beat plan ready for review.",
                    "beat_sheet": current.artifacts["beat_sheet"],
                    "concept_brief": concept.model_dump(mode="json"),
                },
            )

        if not current.artifacts.get("beat_sheet_approved"):
            return cls._preview_result(
                current,
                step_key="confirm_beats",
                output={
                    "message": "Beat plan ready for review.",
                    "beat_sheet": beat_sheet.model_dump(mode="json"),
                    "concept_brief": concept.model_dump(mode="json"),
                },
            )

        package_payload = current.artifacts.get("approved_production_package")
        if package_payload:
            try:
                package = ApprovedProductionPackageContract.model_validate(
                    package_payload
                )
            except ValidationError:
                current.artifacts["approved_production_package"] = None
            else:
                return await cls._package_ready_result(
                    current, package, backend_url, http_client
                )

        package = CreativeDirectorService.build_approved_package(
            concept,
            beat_sheet,
            persona_snapshot,
        )
        current.artifacts["approved_production_package"] = package.model_dump(
            mode="json"
        )
        return await cls._package_ready_result(
            current, package, backend_url, http_client
        )
