"""
Workspace-native persona studio session orchestration.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

import httpx

from services.database_service import DatabaseService
from services.step_config import get_step_definition
from skills.base import SkillResult, SkillSession, SkillStatus
from skills.persona_creator import PersonaCreatorSkill


PersonaStudioMessageKind = Literal["text", "action"]
PersonaStudioCommitMode = Literal["save_draft", "finalize"]


class PersonaStudioService:
    _WORKFLOW_TYPE = "persona_studio"
    _WORKFLOW_CHANNEL = "workspace"

    @classmethod
    def _transport_client(cls, app: Any) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://backend")

    @classmethod
    def _workflow_id(cls, session_id: str) -> str:
        return f"persona-studio-{session_id}"

    @classmethod
    def _workflow_status(cls, status: SkillStatus) -> str:
        if status == SkillStatus.done:
            return "completed"
        if status == SkillStatus.failed:
            return "failed"
        if status == SkillStatus.waiting_approval:
            return "waiting_approval"
        return "running"

    @classmethod
    def _progress_for_step(cls, step_key: str, status: SkillStatus) -> int:
        if status == SkillStatus.done:
            return 100
        if status == SkillStatus.failed:
            return 100
        progress_map = {
            "choose_creation_mode": 5,
            "collect_nationality": 15,
            "collect_persona_id": 20,
            "choose_voice": 30,
            "choose_language": 40,
            "collect_dream_brief": 50,
            "collect_appearance": 55,
            "confirm_dream": 70,
            "generate_preview": 80,
            "preview": 90,
            "save": 95,
            "done": 100,
        }
        return progress_map.get(step_key, 25)

    @classmethod
    def _normalize_text(cls, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @classmethod
    def _display_text_from_prompt(cls, prompt_text: str) -> str:
        prompt = str(prompt_text or "").strip()
        prompt = re.sub(r"[*`_]", "", prompt)
        prompt = prompt.replace("\\.", ".")
        prompt = re.sub(r"\n{3,}", "\n\n", prompt)
        return prompt.strip()

    @classmethod
    def _message_history(cls, session: SkillSession) -> List[Dict[str, Any]]:
        history = session.artifacts.get("web_messages")
        if isinstance(history, list):
            return history
        history = []
        session.artifacts["web_messages"] = history
        return history

    @classmethod
    def _append_history(
        cls,
        session: SkillSession,
        message: Dict[str, Any],
    ) -> None:
        history = cls._message_history(session)
        history.append(message)
        session.artifacts["web_messages"] = history

    @classmethod
    def _step_actions(cls, skill_name: str, step_key: str) -> List[Dict[str, Any]]:
        step = get_step_definition(skill_name, step_key)
        options = step.get("options") or []
        actions: List[Dict[str, Any]] = []
        for option in options:
            value = cls._normalize_text(option.get("value"))
            label = cls._normalize_text(option.get("label")) or value
            if not value:
                continue
            actions.append(
                {
                    "id": value,
                    "label": label,
                    "value": value,
                    "kind": "action",
                }
            )
        return actions

    @classmethod
    def _composer_payload(cls, session: SkillSession) -> Dict[str, Any]:
        step = get_step_definition(session.skill_name, session.step_key)
        input_type = step.get("input_type")
        prompt_text = cls._display_text_from_prompt(step.get("prompt_text") or "")
        if input_type == "free_text":
            placeholder = prompt_text or "Describe your persona..."
            return {
                "enabled": True,
                "kind": "text",
                "placeholder": placeholder,
                "submit_label": "Send",
            }
        return {
            "enabled": False,
            "kind": "action",
            "placeholder": "Choose an option below...",
            "submit_label": "Select",
        }

    @classmethod
    def _preview_payload(cls, session: SkillSession, output: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        persona = None
        if isinstance(output, dict):
            persona = output.get("persona")
        if not isinstance(persona, dict):
            persona = session.artifacts.get("persona_data")
        readiness = None
        if isinstance(output, dict):
            readiness = output.get("readiness")
        if not isinstance(readiness, dict):
            readiness = session.artifacts.get("readiness")

        preview_image_url = None
        if isinstance(output, dict):
            preview_image_url = output.get("preview_image_url")
        if not preview_image_url:
            preview_image_url = session.artifacts.get("preview_image_url")
        if not preview_image_url and isinstance(persona, dict):
            preview_image_url = persona.get("avatar_image_url")

        if not preview_image_url and not persona and not readiness:
            return None

        return {
            "image_url": preview_image_url,
            "persona": persona if isinstance(persona, dict) else None,
            "readiness": readiness if isinstance(readiness, dict) else None,
        }

    @classmethod
    def _message_payload(
        cls,
        *,
        role: Literal["assistant", "user", "system"],
        content: str,
        actions: Optional[List[Dict[str, Any]]] = None,
        preview: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": str(uuid4()),
            "role": role,
            "content": cls._normalize_text(content),
        }
        if actions:
            payload["actions"] = actions
        if preview:
            payload["preview"] = preview
        return payload

    @classmethod
    def _append_assistant_turn(
        cls,
        session: SkillSession,
        result: SkillResult,
    ) -> None:
        output = result.output or {}
        step = get_step_definition(session.skill_name, session.step_key)
        prompt_text = cls._display_text_from_prompt(
            output.get("message") or step.get("prompt_text") or ""
        )
        actions = cls._step_actions(session.skill_name, session.step_key)
        preview = cls._preview_payload(session, output)
        if not prompt_text and not actions and not preview:
            return

        history = cls._message_history(session)
        candidate = {
            "role": "assistant",
            "content": prompt_text,
            "actions": actions or None,
            "preview": preview or None,
        }
        if history:
            last = history[-1]
            if (
                last.get("role") == "assistant"
                and cls._normalize_text(last.get("content")) == candidate["content"]
                and (last.get("actions") or None) == candidate["actions"]
                and (last.get("preview") or None) == candidate["preview"]
            ):
                return
        cls._append_history(
            session,
            cls._message_payload(
                role="assistant",
                content=prompt_text,
                actions=actions,
                preview=preview,
            ),
        )

    @classmethod
    def _build_state(
        cls,
        *,
        session_id: str,
        session: SkillSession,
        result: Optional[SkillResult] = None,
    ) -> Dict[str, Any]:
        output = result.output if result and isinstance(result.output, dict) else {}
        preview = cls._preview_payload(session, output)
        persona = output.get("persona") if isinstance(output.get("persona"), dict) else session.artifacts.get("persona_data")
        readiness = output.get("readiness") if isinstance(output.get("readiness"), dict) else session.artifacts.get("readiness")
        can_finalize = (
            session.step_key == "preview"
            and session.control.status in {SkillStatus.preview_ready, SkillStatus.done}
        )
        return {
            "session_id": session_id,
            "status": session.control.status.value,
            "step_key": session.step_key,
            "messages": list(cls._message_history(session)),
            "composer": cls._composer_payload(session),
            "actions": cls._step_actions(session.skill_name, session.step_key),
            "preview": preview,
            "persona": persona if isinstance(persona, dict) else None,
            "readiness": readiness if isinstance(readiness, dict) else None,
            "can_finalize": can_finalize,
        }

    @classmethod
    def _dump_session(cls, session: SkillSession) -> Dict[str, Any]:
        return session.model_dump(mode="json")

    @classmethod
    async def _persist_state(
        cls,
        *,
        session_id: str,
        user_id: str,
        session: SkillSession,
        studio_state: Dict[str, Any],
    ) -> None:
        workflow_id = cls._workflow_id(session_id)
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.workflows (
                    workflow_id,
                    user_id,
                    type,
                    status,
                    channel,
                    current_step,
                    progress,
                    request_key,
                    input_data,
                    output_data,
                    updated_at,
                    completed_at
                )
                VALUES (
                    $1,
                    $2::uuid,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9::jsonb,
                    $10::jsonb,
                    NOW(),
                    CASE WHEN $4 IN ('completed', 'failed', 'canceled', 'cancelled') THEN NOW() ELSE NULL END
                )
                ON CONFLICT (workflow_id) DO UPDATE
                SET status = EXCLUDED.status,
                    channel = EXCLUDED.channel,
                    current_step = EXCLUDED.current_step,
                    progress = EXCLUDED.progress,
                    request_key = EXCLUDED.request_key,
                    input_data = EXCLUDED.input_data,
                    output_data = EXCLUDED.output_data,
                    updated_at = NOW(),
                    completed_at = CASE
                        WHEN EXCLUDED.status IN ('completed', 'failed', 'canceled', 'cancelled') THEN NOW()
                        ELSE public.workflows.completed_at
                    END
                """,
                workflow_id,
                user_id,
                cls._WORKFLOW_TYPE,
                cls._workflow_status(session.control.status),
                cls._WORKFLOW_CHANNEL,
                session.step_key,
                cls._progress_for_step(session.step_key, session.control.status),
                session_id,
                json.dumps({"studio_session": cls._dump_session(session)}, sort_keys=True),
                json.dumps(studio_state, sort_keys=True),
            )

    @classmethod
    async def _load_session(
        cls,
        *,
        session_id: str,
        user_id: str,
    ) -> SkillSession:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT input_data
                FROM public.workflows
                WHERE user_id = $1::uuid
                  AND type = $2
                  AND request_key = $3
                LIMIT 1
                """,
                user_id,
                cls._WORKFLOW_TYPE,
                session_id,
            )
        if row is None:
            raise ValueError("Persona studio session not found.")
        payload = row.get("input_data") or {}
        studio_session = payload.get("studio_session")
        if not isinstance(studio_session, dict):
            raise ValueError("Persona studio session is invalid.")
        return SkillSession.model_validate(studio_session)

    @classmethod
    async def _execute(
        cls,
        *,
        app: Any,
        session: SkillSession,
    ) -> SkillResult:
        async with cls._transport_client(app) as client:
            return await PersonaCreatorSkill.execute(session, "http://backend", client)

    @classmethod
    async def start_session(
        cls,
        *,
        app: Any,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if session_id:
            session = await cls._load_session(session_id=session_id, user_id=user_id)
            state = cls._build_state(session_id=session_id, session=session)
            await cls._persist_state(
                session_id=session_id,
                user_id=user_id,
                session=session,
                studio_state=state,
            )
            return state

        session_id = str(uuid4())
        session = PersonaCreatorSkill.initial_session()
        session.artifacts["web_messages"] = []
        result = await cls._execute(app=app, session=session)
        next_session = result.session or session
        cls._append_assistant_turn(next_session, result)
        state = cls._build_state(session_id=session_id, session=next_session, result=result)
        await cls._persist_state(
            session_id=session_id,
            user_id=user_id,
            session=next_session,
            studio_state=state,
        )
        return state

    @classmethod
    def _resolve_action_label(
        cls,
        *,
        session: SkillSession,
        value: str,
    ) -> str:
        for option in cls._step_actions(session.skill_name, session.step_key):
            if option.get("value") == value:
                return str(option.get("label") or value)
        return value

    @classmethod
    def _apply_message_to_session(
        cls,
        *,
        session: SkillSession,
        kind: PersonaStudioMessageKind,
        content: Optional[str],
        action: Optional[str],
        value: Optional[str],
    ) -> Dict[str, Any]:
        step = get_step_definition(session.skill_name, session.step_key)
        input_type = step.get("input_type")
        field = step.get("field")

        if kind == "text":
            text = cls._normalize_text(content)
            if input_type != "free_text" or not field:
                raise ValueError("This step requires choosing one of the available actions.")
            if not text:
                raise ValueError("Message content is required.")
            session.collected[field] = text
            return cls._message_payload(role="user", content=text)

        selected_value = cls._normalize_text(value or action)
        if not selected_value:
            raise ValueError("Action value is required.")
        if input_type not in {"inline_keyboard", "preview_actions", "content_actions"} or not field:
            raise ValueError("This step does not accept actions.")

        normalized_value: Any = selected_value
        if selected_value in {"__skip__", "__summary__"}:
            normalized_value = None
        elif field == "num_slides":
            normalized_value = int(selected_value)

        session.collected[field] = normalized_value
        return cls._message_payload(
            role="user",
            content=cls._resolve_action_label(session=session, value=selected_value),
        )

    @classmethod
    async def append_message(
        cls,
        *,
        app: Any,
        user_id: str,
        session_id: str,
        kind: PersonaStudioMessageKind,
        content: Optional[str] = None,
        action: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Dict[str, Any]:
        session = await cls._load_session(session_id=session_id, user_id=user_id)
        cls._append_history(
            session,
            cls._apply_message_to_session(
                session=session,
                kind=kind,
                content=content,
                action=action,
                value=value,
            ),
        )
        result = await cls._execute(app=app, session=session)
        next_session = result.session or session
        if result.success:
            cls._append_assistant_turn(next_session, result)
        elif result.error:
            cls._append_history(
                next_session,
                cls._message_payload(role="system", content=result.error),
            )
        state = cls._build_state(session_id=session_id, session=next_session, result=result)
        await cls._persist_state(
            session_id=session_id,
            user_id=user_id,
            session=next_session,
            studio_state=state,
        )
        return state

    @classmethod
    async def commit(
        cls,
        *,
        app: Any,
        user_id: str,
        session_id: str,
        mode: PersonaStudioCommitMode,
    ) -> Dict[str, Any]:
        session = await cls._load_session(session_id=session_id, user_id=user_id)
        if mode == "save_draft":
            cls._append_history(
                session,
                cls._message_payload(role="system", content="Draft saved."),
            )
            state = cls._build_state(session_id=session_id, session=session)
            await cls._persist_state(
                session_id=session_id,
                user_id=user_id,
                session=session,
                studio_state=state,
            )
            return state

        if session.step_key != "preview":
            raise ValueError("Persona is not ready to finalize yet.")

        session.collected["preview_command"] = "ready"
        cls._append_history(
            session,
            cls._message_payload(role="user", content="Finalize Persona"),
        )
        result = await cls._execute(app=app, session=session)
        next_session = result.session or session
        if result.success:
            message = (
                (result.output or {}).get("message")
                or "Persona finalized."
            )
            cls._append_history(
                next_session,
                cls._message_payload(role="system", content=message),
            )
        elif result.error:
            cls._append_history(
                next_session,
                cls._message_payload(role="system", content=result.error),
            )
        state = cls._build_state(session_id=session_id, session=next_session, result=result)
        await cls._persist_state(
            session_id=session_id,
            user_id=user_id,
            session=next_session,
            studio_state=state,
        )
        return state
