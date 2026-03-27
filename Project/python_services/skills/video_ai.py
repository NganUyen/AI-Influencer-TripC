"""AI influencer video pre-production skill wrapper."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from pydantic import ValidationError

from services.contracts import (
    ApprovedProductionPackageContract,
    BeatSheetContract,
    ConceptBriefContract,
)
from services.creative_director_service import CreativeDirectorService

from .base import BaseSkill, SkillResult, SkillSession, SkillStatus
from .definitions import get_skill_definition

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
}
_RESETTABLE_FIELDS = [
    "idea_brief",
    "feature_focus",
    "video_goal",
    "audience",
    "cta",
    "reference_url",
    "access_level",
]


class VideoAISkill(BaseSkill):
    name = "video-ai"
    required_params = list(_DEFINITION.get("required_params", []))
    optional_params = list(_DEFINITION.get("optional_params", []))
    api_target = _DEFINITION.get("api_call", {}).get("target", "Internal CreativeDirectorService")
    backend_status = _DEFINITION.get("status", "partial")
    steps = list(_DEFINITION.get("steps", []))
    session_shape = deepcopy(_DEFINITION.get("session_shape", BaseSkill.session_shape))

    @classmethod
    def initial_session(cls) -> SkillSession:
        session = super().initial_session()
        session.collected["platform"] = session.collected.get("platform") or "tiktok"
        session.artifacts.setdefault("persona_snapshot", None)
        session.artifacts.setdefault("persona_readiness", None)
        session.artifacts.setdefault("concept_brief", None)
        session.artifacts.setdefault("beat_sheet", None)
        session.artifacts.setdefault("approved_production_package", None)
        session.artifacts.setdefault("concept_approved", False)
        session.artifacts.setdefault("beat_sheet_approved", False)
        return session

    @classmethod
    def _missing_step(cls, session: SkillSession) -> Optional[str]:
        missing = cls._missing_required_params(session)
        if not missing:
            return None
        return _FIELD_TO_STEP.get(missing[0], "collect_idea_brief")

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
            return snapshot

        readiness = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{persona_id}/readiness",
        )
        session.artifacts["persona_readiness"] = readiness
        if not readiness.get("ready"):
            raise ValueError(
                readiness.get("blocking_reason") or "Selected persona is not ready."
            )

        persona = await cls._request_json(
            http_client,
            "GET",
            backend_url,
            f"/api/personas/{persona_id}",
        )
        if not persona.get("persona_id"):
            raise ValueError("Selected persona could not be loaded.")

        tone_resolved = str(persona.get("tone_default") or "natural").strip() or "natural"
        resolved_snapshot = {
            "persona_id": persona.get("persona_id"),
            "display_name": persona.get("display_name") or persona.get("persona_id"),
            "language": persona.get("language") or "English",
            "tts_voice": persona.get("tts_voice"),
            "tone_default": persona.get("tone_default"),
            "tone_resolved": tone_resolved,
            "heygen_avatar_id": persona.get("heygen_avatar_id"),
            "status": persona.get("status"),
        }
        session.artifacts["persona_snapshot"] = resolved_snapshot
        return resolved_snapshot

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
    def _package_ready_result(
        cls,
        session: SkillSession,
        package: ApprovedProductionPackageContract,
    ) -> SkillResult:
        session.control.status = SkillStatus.done
        session.step_key = "package_ready"
        return SkillResult(
            success=True,
            next_step="package_ready",
            output={
                "message": (
                    "Pre-production package is ready. No production workflow has started yet."
                ),
                "approved_production_package": package.model_dump(mode="json"),
            },
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
        for field in _RESETTABLE_FIELDS:
            session.collected[field] = None
        session.artifacts["concept_brief"] = None
        session.artifacts["beat_sheet"] = None
        session.artifacts["approved_production_package"] = None
        session.artifacts["concept_approved"] = False
        session.artifacts["beat_sheet_approved"] = False
        session.control.status = SkillStatus.collecting
        session.step_key = "collect_idea_brief"
        return SkillResult(
            success=True,
            next_step="collect_idea_brief",
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
        return cls._error_result(current, f"Unsupported action for {current.step_key}: {action}")

    @classmethod
    async def execute(
        cls,
        session: Optional[SkillSession | Dict[str, Any]],
        backend_url: str,
        http_client: Any,
    ) -> SkillResult:
        current = cls._normalize_session(session)
        current.collected["platform"] = current.collected.get("platform") or "tiktok"

        next_step = cls._missing_step(current)
        if next_step:
            return cls._collecting_result(current, next_step=next_step)

        try:
            persona_snapshot = await cls._resolve_persona_snapshot(current, backend_url, http_client)
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
                beat_sheet = await CreativeDirectorService.build_beat_sheet(concept, persona_snapshot)
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
                package = ApprovedProductionPackageContract.model_validate(package_payload)
            except ValidationError:
                current.artifacts["approved_production_package"] = None
            else:
                return cls._package_ready_result(current, package)

        package = CreativeDirectorService.build_approved_package(
            concept,
            beat_sheet,
            persona_snapshot,
        )
        current.artifacts["approved_production_package"] = package.model_dump(mode="json")
        return cls._package_ready_result(current, package)
