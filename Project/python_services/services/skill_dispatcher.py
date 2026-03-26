"""Telegram skill dispatcher for menu-driven skill execution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

import httpx

from skills import SKILL_REGISTRY
from skills.base import SkillResult, SkillSession

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
    ) -> list[Dict[str, Any]]:
        from skills.base import BaseSkill

        params = {"status": "ready"} if ready_only else None
        async with cls._transport_client(app) as client:
            response = await client.get(
                "/api/personas",
                params=params,
                headers=BaseSkill._auth_headers(),
            )
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return payload["items"]
        return []

    @classmethod
    async def _prepare_prompt_session(cls, app: Any, session: SkillSession) -> SkillSession:
        step = get_step_definition(session.skill_name, session.step_key)
        input_type = step.get("input_type")
        if input_type in {"persona_picker", "persona_selector"}:
            ready_only = session.skill_name in {"video-ai", "carousel"}
            session.artifacts["available_personas"] = await cls._fetch_personas(
                app,
                ready_only=ready_only,
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

        step = get_step_definition(session.skill_name, session.step_key)
        if step.get("input_type") != "free_text":
            return SkillResult(success=False, error="Current step expects button input.", session=session)

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
    async def handle_option(cls, chat_id: int, value: str, app: Any) -> SkillResult:
        session = await TelegramSkillSessionStore.get_session(chat_id)
        if session is None:
            return SkillResult(
                success=False,
                error="Skill session expired. Use /media to start again.",
            )

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

        if action == "cancel":
            await TelegramSkillSessionStore.clear_session(chat_id)
            return SkillResult(success=True, next_step="done", output={"status": "cancelled"})

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
            elif action == "retry_publish":
                async with cls._transport_client(app) as client:
                    result = await skill_cls.retry_selected(session, "http://backend", client)
                return await cls._save_or_clear(chat_id, result)

        # ── Persona-creator: Save action ─────────────────────────────────────
        if action == "save" and session.skill_name == "persona-creator":
            persona_id = session.artifacts.get("persona_id") or session.collected.get("persona_id")
            avatar_url = session.artifacts.get("avatar_image_url") or session.artifacts.get("preview_image_url")

            # 1. Mark persona status = ready via API
            try:
                async with cls._transport_client(app) as client:
                    from skills.base import BaseSkill
                    await client.patch(
                        f"/api/personas/{persona_id}",
                        json={"status": "ready"},
                        headers=BaseSkill._auth_headers(),
                    )
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("Could not mark persona ready: %s", exc)

            # 2. Upload avatar to Supabase media bucket (fire-and-forget)
            if avatar_url:
                try:
                    import asyncio
                    from services.media_storage_service import MediaStorageService

                    async def _upload_persona_avatar() -> None:
                        import logging as _log
                        try:
                            svc = MediaStorageService()
                            result = await svc.upload_from_url(avatar_url, asset_type="image")
                            if result:
                                _log.getLogger(__name__).info(
                                    "Persona avatar uploaded to storage: %s", result.get("public_url")
                                )
                        except Exception as e:
                            _log.getLogger(__name__).warning("Persona avatar storage upload failed: %s", e)

                    asyncio.create_task(_upload_persona_avatar())
                except Exception:
                    pass

            await TelegramSkillSessionStore.clear_session(chat_id)
            return SkillResult(
                success=True,
                next_step="done",
                output={
                    "status": "saved",
                    "message": f"✅ Persona *{persona_id}* saved and marked as ready\\!",
                    "persona_id": persona_id,
                },
            )

        if action == "regenerate":
            template = skill_cls.initial_session()
            session.artifacts = deepcopy(template.artifacts)
            if session.skill_name == "image-scene":
                session.step_key = "generating_candidates"
            elif session.skill_name == "carousel":
                session.step_key = "pick_persona"
            elif session.skill_name == "persona-creator":
                # Re-run the full creation cycle with the same collected params
                pass

        async with cls._transport_client(app) as client:
            result = await skill_cls.execute(session, "http://backend", client)
        if result.session is not None:
            await cls._prepare_prompt_session(app, result.session)
        return await cls._save_or_clear(chat_id, result)

