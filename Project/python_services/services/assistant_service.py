"""
Persistent in-app assistant threads backed by OpenClaw.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.brand_profile_service import BrandProfileService
from services.customer_ai_backbone_service import CustomerAIBackboneService
from services.customer_auth_service import CustomerSession
from services.database_service import DatabaseService
from services.openclaw_gateway import OpenClawGateway


def _normalize_thread(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "title": row["title"],
        "status": row["status"],
        "last_message_preview": row["last_message_preview"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _normalize_message(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "thread_id": str(row["thread_id"]),
        "role": row["role"],
        "content": row["content"],
        "metadata": row["metadata"] or {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


class AssistantService:
    @classmethod
    async def list_threads(cls, user_id: str) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM public.assistant_threads
                WHERE user_id = $1::uuid
                ORDER BY updated_at DESC, created_at DESC
                """,
                user_id,
            )
        return [_normalize_thread(row) for row in rows]

    @classmethod
    async def create_thread(
        cls,
        session: CustomerSession,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.assistant_threads (user_id, title, status)
                VALUES ($1::uuid, $2, 'active')
                RETURNING *
                """,
                session.user_id,
                title or "New strategy thread",
            )
        return _normalize_thread(row)

    @classmethod
    async def list_messages(cls, user_id: str, thread_id: str) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.*
                FROM public.assistant_messages m
                JOIN public.assistant_threads t ON t.id = m.thread_id
                WHERE m.thread_id = $1::uuid
                  AND t.user_id = $2::uuid
                ORDER BY m.created_at ASC
                """,
                thread_id,
                user_id,
            )
        return [_normalize_message(row) for row in rows]

    @classmethod
    async def append_message(
        cls,
        session: CustomerSession,
        thread_id: str,
        content: str,
    ) -> Dict[str, Any]:
        pool = await DatabaseService.get_pool()

        async with pool.acquire() as conn:
            thread = await conn.fetchrow(
                """
                SELECT *
                FROM public.assistant_threads
                WHERE id = $1::uuid AND user_id = $2::uuid
                LIMIT 1
                """,
                thread_id,
                session.user_id,
            )
            if thread is None:
                raise ValueError("Assistant thread was not found")

        runtime_config = await CustomerAIBackboneService.resolve_runtime_config(session.user_id)
        brand_context = await BrandProfileService.get_for_user(session.user_id)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.assistant_messages (thread_id, role, content, metadata)
                VALUES ($1::uuid, 'user', $2, $3::jsonb)
                """,
                thread_id,
                content,
                json.dumps({"source": "web_app"}, sort_keys=True),
            )

        service = OpenClawGateway(
            base_url=runtime_config.get("base_url"),
            api_key=runtime_config.get("api_key"),
            connector_session_token=runtime_config.get("connector_session_token"),
        )
        try:
            result = await service.execute_task(
                task_type="strategy_planning",
                prompt=content,
                user_id=session.user_id,
                context={
                    "brand_profile": brand_context or {},
                    "thread_id": thread_id,
                    "ai_backbone": {
                        "access_mode": runtime_config.get("access_mode"),
                        "chatgpt_subject": runtime_config.get("chatgpt_subject"),
                        "subscription_tier": runtime_config.get("chatgpt_subscription_tier"),
                    },
                },
            )
        finally:
            await service.close()

        result_text = result.get("text") if isinstance(result, dict) else None
        if not isinstance(result_text, str) or not result_text.strip():
            result_text = json.dumps(result, ensure_ascii=True, indent=2)

        async with pool.acquire() as conn:
            assistant_row = await conn.fetchrow(
                """
                INSERT INTO public.assistant_messages (thread_id, role, content, metadata)
                VALUES ($1::uuid, 'assistant', $2, $3::jsonb)
                RETURNING *
                """,
                thread_id,
                result_text,
                json.dumps({"provider_result": result}, sort_keys=True, default=str),
            )
            await conn.execute(
                """
                UPDATE public.assistant_threads
                SET last_message_preview = $2,
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                thread_id,
                result_text[:240],
            )
            await conn.execute(
                """
                INSERT INTO public.assistant_artifacts (
                    thread_id,
                    artifact_type,
                    title,
                    payload
                )
                VALUES ($1::uuid, $2, $3, $4::jsonb)
                """,
                thread_id,
                "plan_snapshot",
                "OpenClaw strategy result",
                json.dumps(result, sort_keys=True, default=str),
            )

        return {
            "thread_id": thread_id,
            "assistant_message": _normalize_message(assistant_row),
            "artifact_type": "plan_snapshot",
        }

    @classmethod
    async def list_artifacts(cls, user_id: str, thread_id: str) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT a.*
                FROM public.assistant_artifacts a
                JOIN public.assistant_threads t ON t.id = a.thread_id
                WHERE a.thread_id = $1::uuid
                  AND t.user_id = $2::uuid
                ORDER BY a.created_at DESC
                """,
                thread_id,
                user_id,
            )

        artifacts = []
        for row in rows:
            artifacts.append(
                {
                    "id": str(row["id"]),
                    "thread_id": str(row["thread_id"]),
                    "artifact_type": row["artifact_type"],
                    "title": row["title"],
                    "payload": row["payload"] or {},
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                }
            )
        return artifacts
