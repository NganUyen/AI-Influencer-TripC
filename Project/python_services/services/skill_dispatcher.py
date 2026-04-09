"""Telegram skill dispatcher for menu-driven skill execution."""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Dict, Optional

import httpx

from skills import SKILL_REGISTRY
from skills.base import BaseSkill, SkillResult, SkillSession, SkillStatus

from .skill_session_store import TelegramSkillSessionStore
from .step_config import get_step_definition


class SkillDispatcher:
    """Load, update, execute, and persist skill sessions."""

    @staticmethod
    def _session_accepts_video_upload(session: SkillSession) -> bool:
        return (
            (session.skill_name == "video-ai" and session.step_key == "upload_demo_video")
            or (
                session.skill_name == "video-planner"
                and session.step_key == "upload_manual_video"
            )
        )

    @classmethod
    def _check_demo_preview_timeout(
        cls, session: SkillSession
    ) -> Optional[SkillResult]:
        """
        Check if demo preview confirmation has timed out (Phase 5).

        Returns a timeout error result if expired, None otherwise.
        """
        if (
            session.skill_name != "video-ai"
            or session.step_key != "demo_preview_confirm"
        ):
            return None

        timeout_at = session.artifacts.get("demo_preview_timeout_at")
        if not timeout_at:
            return None

        current_time = int(time.time())
        if current_time < timeout_at:
            return None

        # Timeout expired - abort (not auto-confirm per spec)
        session.control.status = SkillStatus.failed
        session.control.error_message = (
            "Demo preview confirmation timed out (15 minutes). "
            "Please start again or re-upload the video."
        )
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
            session=session,
        )

    @classmethod
    def _build_heygen_avatar_name(cls, persona_id: str) -> str:
        normalized = "".join(
            character if character.isalnum() or character in {"_", "-"} else "_"
            for character in str(persona_id or "").strip()
        )
        return normalized[:64] or "telegram_persona"

    @classmethod
    def _transport_client(cls, app: Any) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://backend")

    @classmethod
    async def _fetch_personas(
        cls,
        app: Any,
        *,
        ready_only: bool,
        owner_key: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        from services.persona_registry_service import PersonaRegistryService

        status = "ready" if ready_only else None
        return await PersonaRegistryService.list_personas(
            status=status, owner_key=owner_key
        )

    @classmethod
    async def _prepare_prompt_session(
        cls, app: Any, session: SkillSession
    ) -> SkillSession:
        step = get_step_definition(session.skill_name, session.step_key)
        input_type = step.get("input_type")
        if input_type in {"persona_picker", "persona_selector"}:
            ready_only = session.skill_name in {"video-ai", "video-planner", "carousel"}
            telegram_chat_id = session.artifacts.get("telegram_chat_id")
            owner_key = f"telegram:{telegram_chat_id}" if telegram_chat_id else None
            session.artifacts["available_personas"] = await cls._fetch_personas(
                app,
                ready_only=ready_only,
                owner_key=owner_key,
            )
        return session

    @classmethod
    async def _save_or_clear(cls, chat_id: int, result: SkillResult) -> SkillResult:
        session = result.session
        if session is None or (
            result.success
            and result.next_step == "done"
            and session.control.status.value == "done"
        ):
            await TelegramSkillSessionStore.clear_session(chat_id)
            return result
        await TelegramSkillSessionStore.set_session(chat_id, session)
        return result

    @classmethod
    async def start_skill(cls, chat_id: int, skill_name: str, app: Any) -> SkillResult:
        skill_cls = SKILL_REGISTRY.get(skill_name)
        if skill_cls is None:
            return SkillResult(success=False, error=f"Unsupported skill: {skill_name}")
        session = skill_cls.initial_session()
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))
        await cls._prepare_prompt_session(app, session)

        step = get_step_definition(skill_name, session.step_key)
        if step.get("input_type") == "automatic":
            async with cls._transport_client(app) as client:
                result = await skill_cls.execute(session, "http://backend", client)
            if result.session is not None:
                await cls._prepare_prompt_session(app, result.session)
            return await cls._save_or_clear(chat_id, result)

        result = SkillResult(success=True, next_step=session.step_key, session=session)
        return await cls._save_or_clear(chat_id, result)

    @classmethod
    async def handle_text(
        cls, chat_id: int, text: str, app: Any
    ) -> Optional[SkillResult]:
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return None
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

        # Phase 5: Check demo preview timeout before processing
        timeout_result = cls._check_demo_preview_timeout(session)
        if timeout_result:
            return await cls._save_or_clear(chat_id, timeout_result)

        step = get_step_definition(session.skill_name, session.step_key)
        input_type = step.get("input_type")
        if input_type != "free_text":
            field = step.get("field")
            normalized = text.strip()

            if input_type in {"inline_keyboard", "preview_actions", "content_actions"}:
                options = step.get("options", []) or []
                matched_value: Optional[str] = None
                for option in options:
                    option_value = str(option.get("value", "")).strip()
                    option_label = str(option.get("label", "")).strip()
                    if normalized.lower() in {
                        option_value.lower(),
                        option_label.lower(),
                    }:
                        matched_value = option_value
                        break

                if matched_value is not None and field:
                    if matched_value in {"__skip__", "__summary__"}:
                        session.collected[field] = None
                    elif field == "num_slides":
                        session.collected[field] = int(matched_value)
                    else:
                        session.collected[field] = matched_value

                    skill_cls = SKILL_REGISTRY[session.skill_name]
                    async with cls._transport_client(app) as client:
                        result = await skill_cls.execute(
                            session, "http://backend", client
                        )
                    if result.session is not None:
                        await cls._prepare_prompt_session(app, result.session)
                    return await cls._save_or_clear(chat_id, result)

            if (
                input_type in {"persona_picker", "persona_selector", "content_selector"}
                and field
                and normalized
            ):
                session.collected[field] = normalized
                skill_cls = SKILL_REGISTRY[session.skill_name]
                async with cls._transport_client(app) as client:
                    result = await skill_cls.execute(session, "http://backend", client)
                if result.session is not None:
                    await cls._prepare_prompt_session(app, result.session)
                return await cls._save_or_clear(chat_id, result)

            return SkillResult(
                success=False,
                error="This step needs button selection. Please tap one of the buttons below, or send /cancel.",
                session=session,
            )

        field = step.get("field")
        if field:
            session.collected[field] = text.strip()

        skill_cls = SKILL_REGISTRY[session.skill_name]
        async with cls._transport_client(app) as client:
            result = await skill_cls.execute(session, "http://backend", client)
        if result.session is not None:
            await cls._prepare_prompt_session(app, result.session)
        return await cls._save_or_clear(chat_id, result)

    @classmethod
    async def handle_image_upload(
        cls,
        chat_id: int,
        *,
        data: bytes,
        content_type: str,
        filename: str,
        app: Any,
    ) -> Optional[SkillResult]:
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return None
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

        if (
            session.skill_name != "persona-creator"
            or session.step_key != "collect_appearance"
        ):
            return SkillResult(
                success=False,
                error="This step does not accept file uploads yet. Please follow the current prompt or send /cancel.",
                session=session,
            )

        if not str(content_type or "").lower().startswith("image/"):
            return SkillResult(
                success=False,
                error="Please send a photo or image file for the persona appearance step.",
                session=session,
            )

        persona_id = str(session.collected.get("persona_id") or "").strip()
        if not persona_id:
            return SkillResult(
                success=False,
                error="Persona ID is missing. Restart persona creation from the studio menu.",
                session=session,
            )

        from services.media_storage_service import MediaStorageService

        owner_key = f"telegram:{chat_id}"
        storage_result = await MediaStorageService().upload_bytes(
            data=data,
            content_type=content_type,
            asset_type="IMAGE",
            asset_kind="avatar",
            asset_origin="uploaded",
            owner_key=owner_key,
            persona_id=persona_id,
            metadata={
                "source": "telegram_upload",
                "skill_name": session.skill_name,
                "persona_id": persona_id,
                "filename": filename,
            },
            file_name_hint=f"{persona_id}-telegram-avatar",
        )
        if not storage_result or not storage_result.get("media_asset_id"):
            return SkillResult(
                success=False,
                error=(
                    "I couldn't save that image to workspace storage. "
                    "Link Telegram to a customer workspace first, then try again."
                ),
                session=session,
            )

        access_url = storage_result.get("access_url") or storage_result.get("url")
        session.collected["appearance_prompt_or_photo"] = access_url or filename
        session.artifacts["uploaded_reference_image_url"] = access_url
        session.artifacts["uploaded_reference_asset_id"] = storage_result.get(
            "media_asset_id"
        )
        session.artifacts["uploaded_reference_filename"] = filename

        skill_cls = SKILL_REGISTRY[session.skill_name]
        async with cls._transport_client(app) as client:
            result = await skill_cls.execute(session, "http://backend", client)
        if result.session is not None:
            await cls._prepare_prompt_session(app, result.session)
        return await cls._save_or_clear(chat_id, result)

    @classmethod
    async def handle_video_upload(
        cls,
        chat_id: int,
        *,
        file_id: str,
        data: bytes,
        content_type: str,
        filename: str,
        app: Any,
    ) -> Optional[SkillResult]:
        """
        Handle video file upload for recorded_demo_video mode.

        Saves video to storage, runs quality gate, and stores file_id + URL in session.
        """
        import tempfile
        from pathlib import Path

        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return None
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

        if not cls._session_accepts_video_upload(session):
            return SkillResult(
                success=False,
                error="This step does not accept video uploads yet. Please follow the current prompt or send /cancel.",
                session=session,
            )

        if not str(content_type or "").lower().startswith("video/"):
            return SkillResult(
                success=False,
                error="Please send a video file for the demo video step.",
                session=session,
            )

        # Run quality gate on uploaded video
        from services.video_quality_gate_service import VideoQualityGateService

        quality_service = VideoQualityGateService()

        # Save to temp file for quality gate validation
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(data)

        try:
            quality_report = await quality_service.validate_video_file(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        # Check if quality gate passed
        if not quality_report.passed:
            error_msg = "❌ Video quality check failed:\n\n"
            for error in quality_report.errors:
                error_msg += f"• {error}\n"
            error_msg += (
                "\nPlease upload a different video that meets the requirements."
            )

            return SkillResult(
                success=False,
                error=error_msg,
                session=session,
                output={"quality_report": quality_report.model_dump()},
            )

        # Quality gate passed - save video to storage
        from services.media_storage_service import MediaStorageService

        owner_key = f"telegram:{chat_id}"
        storage_result = await MediaStorageService().upload_bytes(
            data=data,
            content_type=content_type,
            asset_type="VIDEO",
            asset_kind="demo_video",
            asset_origin="uploaded",
            owner_key=owner_key,
            metadata={
                "source": "telegram_upload",
                "skill_name": session.skill_name,
                "filename": filename,
                "duration_sec": quality_report.duration_sec,
                "resolution": quality_report.resolution_string,
                "file_size_bytes": quality_report.file_size_bytes,
            },
            file_name_hint=f"demo-video-{chat_id}",
        )

        if not storage_result or not storage_result.get("media_asset_id"):
            return SkillResult(
                success=False,
                error=(
                    "I couldn't save that video to workspace storage. "
                    "Link Telegram to a customer workspace first, then try again."
                ),
                session=session,
            )

        access_url = storage_result.get("access_url") or storage_result.get("url")

        # Build success message with warnings if any
        success_msg = f"✅ Video uploaded successfully!\n\n"
        success_msg += f"Duration: {quality_report.duration_sec:.1f}s\n"
        success_msg += f"Resolution: {quality_report.resolution_string}"

        if quality_report.has_warnings:
            success_msg += "\n\n⚠️ Warnings:\n"
            for warning in quality_report.warnings:
                success_msg += f"• {warning}\n"
            success_msg += "\nYou can continue, but consider the warnings above."

        if session.skill_name == "video-planner":
            from skills.video_planner import VideoPlannerSkill

            async with cls._transport_client(app) as client:
                result = await VideoPlannerSkill.continue_manual_mobile_pipeline(
                    session,
                    backend_url="http://backend",
                    http_client=client,
                    file_id=file_id,
                    asset_url=access_url,
                    asset_id=storage_result.get("media_asset_id"),
                    filename=filename,
                    quality_report=quality_report.model_dump(),
                )
        else:
            # Store file_id and URL in session
            session.collected["demo_video_telegram_file_id"] = file_id
            session.collected["demo_video_asset_url"] = access_url
            session.artifacts["demo_video_asset_id"] = storage_result.get("media_asset_id")
            session.artifacts["demo_video_filename"] = filename
            session.artifacts["demo_video_quality_report"] = quality_report.model_dump()

            # Execute skill to move to next step
            skill_cls = SKILL_REGISTRY[session.skill_name]
            async with cls._transport_client(app) as client:
                result = await skill_cls.execute(session, "http://backend", client)

        # Prepend success message to the result
        if result.session is not None:
            # Store quality report in artifacts for later reference
            result.session.artifacts["demo_video_upload_message"] = success_msg
            result.session.artifacts["demo_video_quality_report"] = (
                quality_report.model_dump()
            )
            await cls._prepare_prompt_session(app, result.session)

        # Return result with success message prepended to next prompt
        saved_result = await cls._save_or_clear(chat_id, result)

        # Inject upload success message into the output
        if saved_result.output is None:
            saved_result.output = {}
        saved_result.output["upload_success_prefix"] = success_msg

        return saved_result

    @classmethod
    async def handle_option(cls, chat_id: int, value: str, app: Any) -> SkillResult:
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return SkillResult(
                success=False,
                error="Skill session expired. Use /media to start again.",
            )
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

        # Phase 5: Check demo preview timeout before processing
        timeout_result = cls._check_demo_preview_timeout(session)
        if timeout_result:
            return await cls._save_or_clear(chat_id, timeout_result)

        step = get_step_definition(session.skill_name, session.step_key)
        field = step.get("field")
        if field:
            if value == "__skip__" or value == "__summary__":
                session.collected[field] = None
            elif field == "num_slides":
                session.collected[field] = int(value)
            else:
                session.collected[field] = value

        skill_cls = SKILL_REGISTRY[session.skill_name]
        async with cls._transport_client(app) as client:
            result = await skill_cls.execute(session, "http://backend", client)
        if result.session is not None:
            await cls._prepare_prompt_session(app, result.session)
        return await cls._save_or_clear(chat_id, result)

    @classmethod
    async def handle_action(cls, chat_id: int, action: str, app: Any) -> SkillResult:
        # ── Bootstrap Persona Actions (No session required) ───────────────────
        if action.startswith(
            ("edit_p_name::", "edit_p_appearance::", "inspect_persona::")
        ):
            parts = action.split("::")
            command = parts[0]
            persona_id = parts[1] if len(parts) > 1 else None

            if not persona_id:
                return SkillResult(success=False, error="Invalid persona ID.")

            return await cls._start_persona_edit(chat_id, persona_id, command, app)

        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return SkillResult(success=False, error="No active skill session.")
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

        # Phase 5: Check demo preview timeout before processing (unless canceling)
        if action != "cancel":
            timeout_result = cls._check_demo_preview_timeout(session)
            if timeout_result:
                return await cls._save_or_clear(chat_id, timeout_result)

        if action == "cancel":
            workflow_id = session.control.workflow_id or session.artifacts.get(
                "workflow_id"
            )
            if workflow_id:
                try:
                    async with cls._transport_client(app) as client:
                        response = await client.post(
                            f"/api/workflows/cancel/{workflow_id}",
                            headers=BaseSkill._auth_headers(),
                        )
                    response.raise_for_status()
                except Exception:
                    return SkillResult(
                        success=False,
                        error=(
                            "I couldn't cancel the running workflow right now. "
                            "Please try again in a moment."
                        ),
                        session=session,
                    )
            await TelegramSkillSessionStore.clear_session(chat_id)
            output = {"status": "cancelled"}
            if workflow_id:
                output["workflow_id"] = workflow_id
            return SkillResult(
                success=True, next_step="done", output=output, session=session
            )

        skill_cls = SKILL_REGISTRY[session.skill_name]

        # ── Persona-creator: Action aliases/state transitions ───────────────
        if session.skill_name == "persona-creator":
            if session.step_key == "confirm_dream" and action in {"confirm", "retry"}:
                session.collected["dream_confirmed"] = action

            if action == "ready":
                action = "save"
            elif action == "rebuild_avatar":
                action = "regenerate"
            elif action == "edit_appearance":
                session.step_key = "collect_appearance"
                session.control.status = SkillStatus.collecting
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=True,
                        next_step="collect_appearance",
                        output={
                            "message": "Send a new appearance description or upload a reference photo.",
                        },
                        session=session,
                    ),
                )
            elif action == "edit_p_name":
                session.step_key = "edit_p_name"
                session.control.status = SkillStatus.collecting
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=True,
                        next_step="edit_p_name",
                        output={
                            "message": "Send the new persona name.",
                        },
                        session=session,
                    ),
                )
            elif action == "choose_voice":
                session.step_key = "choose_voice"
                session.control.status = SkillStatus.collecting
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=True,
                        next_step="choose_voice",
                        session=session,
                    ),
                )

        if session.skill_name == "image-scene":
            if action == "use_images":
                result = skill_cls.enter_selection_mode(session)
                return await cls._save_or_clear(chat_id, result)
            if action.startswith("toggle:"):
                try:
                    selected_index = int(action.split(":", 1)[1])
                except (TypeError, ValueError):
                    return SkillResult(
                        success=False,
                        error=f"Unsupported action: {action}",
                        session=session,
                    )
                result = skill_cls.toggle_selection(session, selected_index)
                return await cls._save_or_clear(chat_id, result)
            if action == "submit_selection":
                result = skill_cls.submit_selection(session)
                return await cls._save_or_clear(chat_id, result)
            if action == "back_to_preview":
                result = skill_cls.return_to_preview(session)
                return await cls._save_or_clear(chat_id, result)

        if session.skill_name == "publish-manager":
            if action == "back_to_queue":
                result = skill_cls.back_to_queue(session)
                return await cls._save_or_clear(chat_id, result)
            if action == "refresh_queue":
                session.collected["content_id"] = None
                session.artifacts["queue_items"] = []
                session.artifacts["selected_item"] = None
                session.artifacts["publish_result"] = None
                session.step_key = "list_publish_queue"
            elif action == "inspect_provider_wiring":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.inspect_provider_wiring(
                        session, "http://backend", client
                    )
                return await cls._save_or_clear(chat_id, result)
            elif action == "check_engagement":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.refresh_selected_engagement(
                        session, "http://backend", client
                    )
                return await cls._save_or_clear(chat_id, result)
            elif action == "boost_engagement":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.boost_selected_engagement(
                        session, "http://backend", client
                    )
                return await cls._save_or_clear(chat_id, result)
            elif action == "retry_publish":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.retry_selected(
                        session, "http://backend", client
                    )
                return await cls._save_or_clear(chat_id, result)

        # Demo preview reuses some approval action names, so route it first when the
        # session is explicitly waiting on preview confirmation.
        if session.skill_name == "video-ai" and action in {
            "approve",
            "confirm",
            "pick_alternate",
            "rewrite",
            "correct",
            "reemphasize",
            "reupload",
        }:
            if session.step_key == "demo_preview_confirm":
                correction_text = session.collected.get("feature_correction")
                reemphasis_text = session.collected.get("feature_reemphasis")

                async with cls._transport_client(app) as client:
                    result = await skill_cls.handle_demo_preview_action(
                        session,
                        action,
                        "http://backend",
                        client,
                        correction_text=correction_text,
                        reemphasis_text=reemphasis_text,
                    )
                if result.session is not None:
                    await cls._prepare_prompt_session(app, result.session)
                return await cls._save_or_clear(chat_id, result)

        if session.skill_name == "video-ai" and action in {
            "approve",
            "edit",
            "regenerate",
            "retry_start",
        }:
            async with cls._transport_client(app) as client:
                result = await skill_cls.handle_preproduction_action(
                    session,
                    action,
                    "http://backend",
                    client,
                )
            if result.session is not None:
                await cls._prepare_prompt_session(app, result.session)
            return await cls._save_or_clear(chat_id, result)

        # ── Persona-creator: Save action ─────────────────────────────────────
        if action == "save" and session.skill_name == "persona-creator":
            persona_id = session.artifacts.get("persona_id") or session.collected.get(
                "persona_id"
            )
            if not persona_id:
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=False,
                        error="Persona ID is missing. Restart persona creation from the studio menu.",
                        session=session,
                    ),
                )

            from services.persona_registry_service import PersonaRegistryService
            from services.errors import HeyGenTimeoutError
            from skills.persona_creator import PersonaCreatorSkill

            owner_key = (
                f"telegram:{session.artifacts.get('telegram_chat_id')}"
                if session.artifacts.get("telegram_chat_id")
                else None
            )
            avatar_url = session.artifacts.get(
                "avatar_image_url"
            ) or session.artifacts.get("preview_image_url")
            avatar_media_asset_id = session.artifacts.get("avatar_media_asset_id")
            heygen_avatar_id = session.artifacts.get("heygen_avatar_id")
            avatar_source_type = session.artifacts.get("persona_data", {}).get(
                "avatar_source_type"
            ) or (
                "telegram_upload"
                if session.artifacts.get("uploaded_reference_asset_id")
                else "generated"
            )

            # CRITICAL FIX: Save should only finalize an already-persisted asset
            # Never re-upload from URL; if avatar_media_asset_id is missing, the preview flow failed
            if not avatar_media_asset_id:
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=False,
                        error=(
                            "Avatar preview exists but was not persisted to workspace media. "
                            "Please regenerate the avatar or try creating the persona again."
                        ),
                        session=session,
                    ),
                )

            if not avatar_url:
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=False,
                        error=(
                            "Avatar preview is missing its image URL, so I can't finish persona setup yet. "
                            "Please regenerate the avatar and try saving again."
                        ),
                        session=session,
                    ),
                )

            heygen_service = None
            created_new_heygen_avatar = False
            if not heygen_avatar_id:
                try:
                    from services.heygen_service import HeyGenService

                    heygen_service = HeyGenService()
                    heygen_avatar_id = await heygen_service.create_avatar(
                        avatar_url,
                        avatar_name=cls._build_heygen_avatar_name(str(persona_id)),
                    )
                    created_new_heygen_avatar = True
                except Exception as exc:
                    return await cls._save_or_clear(
                        chat_id,
                        SkillResult(
                            success=False,
                            error=(
                                "I couldn't register this persona with HeyGen yet, so it is not video-ready. "
                                f"Please try Save Persona again in a moment. ({exc})"
                            ),
                            session=session,
                        ),
                    )

            if heygen_service is None:
                from services.heygen_service import HeyGenService

                heygen_service = HeyGenService()

            try:
                await heygen_service.wait_for_avatar_ready(heygen_avatar_id)
            except Exception as exc:
                if isinstance(exc, HeyGenTimeoutError):
                    persona = await PersonaRegistryService.update_persona(
                        persona_id,
                        {
                            "avatar_image_url": avatar_url,
                            "avatar_media_asset_id": avatar_media_asset_id,
                            "avatar_source_type": avatar_source_type,
                            "heygen_avatar_id": heygen_avatar_id,
                        },
                        owner_key=owner_key,
                    )
                    if not persona:
                        return await cls._save_or_clear(
                            chat_id,
                            SkillResult(
                                success=False,
                                error="Persona was not found for this Telegram workspace.",
                                session=session,
                            ),
                        )

                    readiness = PersonaCreatorSkill._build_readiness_report(
                        str(persona_id),
                        persona,
                    )
                    session.artifacts["avatar_image_url"] = avatar_url
                    session.artifacts["preview_image_url"] = avatar_url
                    session.artifacts["avatar_media_asset_id"] = avatar_media_asset_id
                    session.artifacts["heygen_avatar_id"] = heygen_avatar_id
                    session.artifacts["persona_data"] = persona
                    session.artifacts["readiness"] = readiness
                    session.control.status = SkillStatus.preview_ready
                    session.step_key = "preview"

                    return await cls._save_or_clear(
                        chat_id,
                        SkillResult(
                            success=True,
                            next_step="preview",
                            output={
                                "status": "pending_heygen_avatar",
                                "message": (
                                    "HeyGen accepted the avatar, but it is still processing. "
                                    "Tap Save Persona again in a moment to finish setup."
                                ),
                                "persona_id": persona_id,
                                "preview_image_url": avatar_url,
                                "avatar_media_asset_id": avatar_media_asset_id,
                                "heygen_avatar_id": heygen_avatar_id,
                                "persona": persona,
                                "readiness": readiness,
                            },
                            session=session,
                        ),
                    )

                if created_new_heygen_avatar:
                    session.artifacts.pop("heygen_avatar_id", None)
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=False,
                        error=(
                            "I couldn't verify that HeyGen finished preparing this avatar yet. "
                            f"Please regenerate the avatar or try saving again. ({exc})"
                        ),
                        session=session,
                    ),
                )

            persona = await PersonaRegistryService.update_persona(
                persona_id,
                {
                    "status": "ready",
                    "avatar_image_url": avatar_url,
                    "avatar_media_asset_id": avatar_media_asset_id,
                    "avatar_source_type": avatar_source_type,
                    "heygen_avatar_id": heygen_avatar_id,
                },
                owner_key=owner_key,
            )
            if not persona:
                return await cls._save_or_clear(
                    chat_id,
                    SkillResult(
                        success=False,
                        error="Persona was not found for this Telegram workspace.",
                        session=session,
                    ),
                )

            await TelegramSkillSessionStore.clear_session(chat_id)
            return await cls._save_or_clear(
                chat_id,
                SkillResult(
                    success=True,
                    next_step="done",
                    output={
                        "status": "saved",
                        "message": (
                            f"✅ Persona *{persona_id}* saved, linked to storage, and marked as ready\\!"
                        ),
                        "persona_id": persona_id,
                        "avatar_media_asset_id": avatar_media_asset_id,
                        "heygen_avatar_id": heygen_avatar_id,
                    },
                ),
            )

        if action == "regenerate":
            existing_artifacts = deepcopy(session.artifacts)
            telegram_chat_id = existing_artifacts.get("telegram_chat_id")
            had_uploaded_reference = bool(
                existing_artifacts.get("uploaded_reference_image_url")
            )
            template = skill_cls.initial_session()
            session.artifacts = deepcopy(template.artifacts)
            if telegram_chat_id:
                session.artifacts["telegram_chat_id"] = str(telegram_chat_id)
            if session.skill_name == "image-scene":
                session.step_key = "generating_candidates"
            elif session.skill_name == "carousel":
                session.step_key = "pick_persona"
            elif session.skill_name == "persona-creator":
                if had_uploaded_reference:
                    session.collected["appearance_prompt_or_photo"] = None
                    session.step_key = "collect_appearance"
                    session.control.status = SkillStatus.collecting
                    return await cls._save_or_clear(
                        chat_id,
                        SkillResult(
                            success=True,
                            next_step="collect_appearance",
                            output={
                                "message": (
                                    "Send a new appearance description or upload another photo to replace the avatar."
                                )
                            },
                            session=session,
                        ),
                    )
                session.artifacts["force_regenerate_avatar"] = True

        async with cls._transport_client(app) as client:
            result = await skill_cls.execute(session, "http://backend", client)
        if result.session is not None:
            await cls._prepare_prompt_session(app, result.session)
        return await cls._save_or_clear(chat_id, result)

    @classmethod
    async def _start_persona_edit(
        cls, chat_id: int, persona_id: str, command: str, app: Any
    ) -> SkillResult:
        """Helper to initialize a persona-creator session for editing an existing persona."""
        from services.persona_registry_service import PersonaRegistryService
        from skills.persona_creator import PersonaCreatorSkill

        # 1. Fetch existing persona
        owner_key = f"telegram:{chat_id}"
        persona = await PersonaRegistryService.get_persona(
            persona_id, owner_key=owner_key
        )
        if not persona:
            return SkillResult(
                success=False,
                error=f"Persona '{persona_id}' not found in your workspace.",
            )

        # 2. Build skill session
        session = PersonaCreatorSkill.initial_session()
        session.artifacts["telegram_chat_id"] = str(chat_id)
        session.artifacts["is_editing"] = True
        session.artifacts["persona_data"] = persona

        # Pre-populate collected data
        session.collected["persona_id"] = persona_id
        session.collected["language"] = persona.get("language") or "English"
        session.collected["voice"] = (
            persona.get("tts_voice") or "English AU Female Clear"
        )
        session.collected["appearance_prompt_or_photo"] = (
            persona.get("avatar_prompt") or ""
        )

        # Ensure image URL is in artifacts for the renderer
        session.artifacts["avatar_image_url"] = persona.get("avatar_image_url")
        session.artifacts["persona_id"] = persona_id

        # 3. Determine entry point
        if command == "edit_p_name":
            # Jump to edit_p_name step to collect the display name
            session.step_key = "edit_p_name"
            result = SkillResult(
                success=True,
                next_step="edit_p_name",
                session=session,
                output={
                    "message": f"Editing persona *{persona_id}*. Send a new name, or send /cancel."
                },
            )
        elif command == "edit_p_appearance":
            session.step_key = "collect_appearance"
            # Flag to ensure prompt-to-generation flow
            session.artifacts["force_regenerate_avatar"] = True
            result = SkillResult(
                success=True,
                next_step="collect_appearance",
                session=session,
                output={
                    "message": f"Editing *{persona_id}*. Send a new appearance description, upload a photo, or send /cancel."
                },
            )
        elif command == "inspect_persona":
            from skills.persona_creator import PersonaCreatorSkill

            readiness = PersonaCreatorSkill._build_readiness_report(persona_id, persona)
            session.artifacts["readiness"] = readiness
            session.step_key = "preview"
            # Return result IMMEDIATELY without calling execute (which might trigger redundant POSTs)
            result = SkillResult(
                success=True,
                next_step="preview",
                output={
                    "persona": persona,
                    "readiness": readiness,
                    "preview_image_url": persona.get("avatar_image_url"),
                },
                session=session,
            )
        else:
            return SkillResult(
                success=False, error=f"Unsupported edit command: {command}"
            )

        # 4. Prepare session only if using picker (not for direct inspection)
        if result.session and command != "inspect_persona":
            await cls._prepare_prompt_session(app, result.session)

        return await cls._save_or_clear(chat_id, result)
