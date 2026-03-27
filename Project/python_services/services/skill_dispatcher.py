"""Telegram skill dispatcher for menu-driven skill execution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

import httpx

from skills import SKILL_REGISTRY
from skills.base import BaseSkill, SkillResult, SkillSession, SkillStatus

from .skill_session_store import TelegramSkillSessionStore
from .step_config import get_step_definition


class SkillDispatcher:
    """Load, update, execute, and persist skill sessions."""

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
        return await PersonaRegistryService.list_personas(status=status, owner_key=owner_key)

    @classmethod
    async def _prepare_prompt_session(cls, app: Any, session: SkillSession) -> SkillSession:
        step = get_step_definition(session.skill_name, session.step_key)
        input_type = step.get("input_type")
        if input_type in {"persona_picker", "persona_selector"}:
            ready_only = session.skill_name in {"video-ai", "carousel"}
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
        if session is None or (result.success and result.next_step == "done" and session.control.status.value == "done"):
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
    async def handle_text(cls, chat_id: int, text: str, app: Any) -> Optional[SkillResult]:
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return None
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

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
                    if normalized.lower() in {option_value.lower(), option_label.lower()}:
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
                        result = await skill_cls.execute(session, "http://backend", client)
                    if result.session is not None:
                        await cls._prepare_prompt_session(app, result.session)
                    return await cls._save_or_clear(chat_id, result)

            if input_type in {"persona_picker", "persona_selector", "content_selector"} and field and normalized:
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

        if session.skill_name != "persona-creator" or session.step_key != "collect_appearance":
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
        session.artifacts["uploaded_reference_asset_id"] = storage_result.get("media_asset_id")
        session.artifacts["uploaded_reference_filename"] = filename

        skill_cls = SKILL_REGISTRY[session.skill_name]
        async with cls._transport_client(app) as client:
            result = await skill_cls.execute(session, "http://backend", client)
        if result.session is not None:
            await cls._prepare_prompt_session(app, result.session)
        return await cls._save_or_clear(chat_id, result)

    @classmethod
    async def handle_option(cls, chat_id: int, value: str, app: Any) -> SkillResult:
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return SkillResult(
                success=False,
                error="Skill session expired. Use /media to start again.",
            )
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

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
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return SkillResult(success=False, error="No active skill session.")
        session.artifacts.setdefault("telegram_chat_id", str(chat_id))

        if action == "cancel":
            workflow_id = session.control.workflow_id or session.artifacts.get("workflow_id")
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
            return SkillResult(success=True, next_step="done", output=output, session=session)

        skill_cls = SKILL_REGISTRY[session.skill_name]

        if session.skill_name == "image-scene":
            if action == "use_images":
                result = skill_cls.enter_selection_mode(session)
                return await cls._save_or_clear(chat_id, result)
            if action.startswith("toggle:"):
                try:
                    selected_index = int(action.split(":", 1)[1])
                except (TypeError, ValueError):
                    return SkillResult(success=False, error=f"Unsupported action: {action}", session=session)
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
                    result = await skill_cls.inspect_provider_wiring(session, "http://backend", client)
                return await cls._save_or_clear(chat_id, result)
            elif action == "check_engagement":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.refresh_selected_engagement(session, "http://backend", client)
                return await cls._save_or_clear(chat_id, result)
            elif action == "boost_engagement":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.boost_selected_engagement(session, "http://backend", client)
                return await cls._save_or_clear(chat_id, result)
            elif action == "retry_publish":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.retry_selected(session, "http://backend", client)
                return await cls._save_or_clear(chat_id, result)

        if session.skill_name == "video-ai" and action in {"approve", "edit", "regenerate"}:
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
            persona_id = session.artifacts.get("persona_id") or session.collected.get("persona_id")
            if not persona_id:
                return SkillResult(
                    success=False,
                    error="Persona ID is missing. Restart persona creation from the studio menu.",
                    session=session,
                )

            from services.media_storage_service import MediaStorageService
            from services.persona_registry_service import PersonaRegistryService

            owner_key = (
                f"telegram:{session.artifacts.get('telegram_chat_id')}"
                if session.artifacts.get("telegram_chat_id")
                else None
            )
            avatar_url = session.artifacts.get("avatar_image_url") or session.artifacts.get("preview_image_url")
            avatar_media_asset_id = session.artifacts.get("avatar_media_asset_id")
            avatar_source_type = (
                session.artifacts.get("persona_data", {}).get("avatar_source_type")
                or ("telegram_upload" if session.artifacts.get("uploaded_reference_asset_id") else "generated")
            )

            if not avatar_media_asset_id:
                if not avatar_url:
                    return SkillResult(
                        success=False,
                        error="Persona avatar is missing. Send a photo or generate one before saving.",
                        session=session,
                    )

                storage_result = await MediaStorageService().upload_from_url(
                    avatar_url,
                    asset_type="IMAGE",
                    asset_kind="avatar",
                    asset_origin="uploaded"
                    if avatar_source_type == "telegram_upload"
                    else "generated",
                    generation_prompt="persona_avatar",
                    owner_key=owner_key,
                    persona_id=persona_id,
                    metadata={
                        "source": "telegram_persona_save",
                        "skill_name": session.skill_name,
                        "persona_id": persona_id,
                    },
                    file_name_hint=f"{persona_id}-avatar",
                )
                if not storage_result or not storage_result.get("media_asset_id"):
                    return SkillResult(
                        success=False,
                        error="I couldn't persist the persona avatar to storage. Please try saving again.",
                        session=session,
                    )
                avatar_media_asset_id = storage_result.get("media_asset_id")
                avatar_url = storage_result.get("access_url") or storage_result.get("url") or avatar_url

            persona = await PersonaRegistryService.update_persona(
                persona_id,
                {
                    "status": "ready",
                    "avatar_image_url": avatar_url,
                    "avatar_media_asset_id": avatar_media_asset_id,
                    "avatar_source_type": avatar_source_type,
                },
                owner_key=owner_key,
            )
            if not persona:
                return SkillResult(
                    success=False,
                    error="Persona was not found for this Telegram workspace.",
                    session=session,
                )

            await TelegramSkillSessionStore.clear_session(chat_id)
            return SkillResult(
                success=True,
                next_step="done",
                output={
                    "status": "saved",
                    "message": (
                        f"✅ Persona *{persona_id}* saved, linked to storage, and marked as ready\\!"
                    ),
                    "persona_id": persona_id,
                    "avatar_media_asset_id": avatar_media_asset_id,
                },
            )

        if action == "regenerate":
            existing_artifacts = deepcopy(session.artifacts)
            telegram_chat_id = existing_artifacts.get("telegram_chat_id")
            had_uploaded_reference = bool(existing_artifacts.get("uploaded_reference_image_url"))
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
