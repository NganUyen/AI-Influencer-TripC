"""
Telegram event/audit logging with duplicate-update protection.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from services.database_service import DatabaseService


class TelegramAuditService:
    _memory_store: Dict[int, Dict[str, Any]] = {}

    @classmethod
    async def begin_update(
        cls,
        *,
        update_id: int,
        chat_id: int | str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        existing = cls._memory_store.get(update_id)
        if existing is not None:
            return False

        entry = {
            "telegram_update_id": int(update_id),
            "chat_id": str(chat_id),
            "linked_user_id": None,
            "route": "received",
            "approval_id": None,
            "workflow_id": None,
            "event_type": event_type,
            "payload": payload or {},
            "error_message": None,
        }

        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchrow(
                    """
                    INSERT INTO public.telegram_events (
                        telegram_update_id,
                        chat_id,
                        event_type,
                        route,
                        payload
                    )
                    VALUES ($1, $2, $3, 'received', $4::jsonb)
                    ON CONFLICT (telegram_update_id) DO NOTHING
                    RETURNING telegram_update_id
                    """,
                    int(update_id),
                    int(chat_id),
                    event_type,
                    json.dumps(payload or {}, sort_keys=True),
                )
        except Exception:
            cls._memory_store[update_id] = entry
            return True

        if result is None:
            return False
        cls._memory_store[update_id] = entry
        return True

    @classmethod
    async def complete_update(
        cls,
        *,
        update_id: int,
        route: str,
        linked_user_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        entry = cls._memory_store.get(update_id, {"telegram_update_id": update_id})
        entry["route"] = route
        entry["linked_user_id"] = linked_user_id
        entry["approval_id"] = approval_id
        entry["workflow_id"] = workflow_id
        entry["error_message"] = error_message
        cls._memory_store[update_id] = entry

        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE public.telegram_events
                    SET linked_user_id = $2::uuid,
                        route = $3,
                        approval_id = $4::uuid,
                        workflow_id = $5,
                        error_message = $6,
                        updated_at = NOW()
                    WHERE telegram_update_id = $1
                    """,
                    int(update_id),
                    linked_user_id,
                    route,
                    approval_id,
                    workflow_id,
                    error_message,
                )
        except Exception:
            return
