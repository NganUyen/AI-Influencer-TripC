"""
Durable workflow state helpers backed by public.workflows.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.database_service import DatabaseService


def _normalize_workflow_row(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row["id"]) if row.get("id") else None,
        "workflow_id": row["workflow_id"],
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        "type": row.get("type"),
        "status": row.get("status"),
        "channel": row.get("channel"),
        "current_step": row.get("current_step"),
        "progress": int(row.get("progress") or 0),
        "request_key": row.get("request_key"),
        "telegram_message_ref": row.get("telegram_message_ref") or None,
        "decision_source": row.get("decision_source"),
        "decision_payload": row.get("decision_payload") or {},
        "input_data": row.get("input_data") or {},
        "output_data": row.get("output_data") or {},
        "error_message": row.get("error_message"),
        "approval_required": bool(row.get("approval_required") or False),
        "approval_status": row.get("approval_status"),
        "approval_feedback": row.get("approval_feedback"),
        "approved_by": str(row["approved_by"]) if row.get("approved_by") else None,
        "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
        "completed_at": row["completed_at"].isoformat()
        if row.get("completed_at")
        else None,
        "approved_at": row["approved_at"].isoformat() if row.get("approved_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


class WorkflowStateService:
    _memory_store: Dict[str, Dict[str, Any]] = {}

    @classmethod
    async def record_started(
        cls,
        *,
        workflow_id: str,
        user_id: str,
        workflow_type: str,
        status: str = "running",
        current_step: Optional[str] = None,
        progress: int = 0,
        input_data: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
        request_key: Optional[str] = None,
        telegram_message_ref: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "workflow_id": workflow_id,
            "user_id": user_id,
            "type": workflow_type,
            "status": status,
            "channel": channel,
            "current_step": current_step,
            "progress": progress,
            "request_key": request_key,
            "telegram_message_ref": telegram_message_ref or None,
            "decision_source": None,
            "decision_payload": {},
            "input_data": input_data or {},
            "output_data": {},
            "error_message": None,
            "approval_required": status == "waiting_approval",
            "approval_status": "pending" if status == "waiting_approval" else None,
            "approval_feedback": None,
            "approved_by": None,
            "started_at": None,
            "completed_at": None,
            "approved_at": None,
            "updated_at": None,
            "id": None,
        }

        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
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
                        telegram_message_ref,
                        decision_source,
                        decision_payload,
                        input_data
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
                        NULL,
                        '{}'::jsonb,
                        $10::jsonb
                    )
                    ON CONFLICT (workflow_id) DO UPDATE
                    SET user_id = EXCLUDED.user_id,
                        type = EXCLUDED.type,
                        status = EXCLUDED.status,
                        channel = EXCLUDED.channel,
                        current_step = EXCLUDED.current_step,
                        progress = EXCLUDED.progress,
                        request_key = EXCLUDED.request_key,
                        telegram_message_ref = EXCLUDED.telegram_message_ref,
                        input_data = EXCLUDED.input_data,
                        updated_at = NOW()
                    RETURNING *
                    """,
                    workflow_id,
                    user_id,
                    workflow_type,
                    status,
                    channel,
                    current_step,
                    progress,
                    request_key,
                    json.dumps(telegram_message_ref or {}, sort_keys=True),
                    json.dumps(input_data or {}, sort_keys=True),
                )
        except Exception:
            cls._memory_store[workflow_id] = payload
            return dict(payload)

        normalized = _normalize_workflow_row(dict(row))
        cls._memory_store[workflow_id] = normalized
        return normalized

    @classmethod
    async def attach_approval_request(
        cls,
        *,
        workflow_id: str,
        request_key: str,
        channel: str = "telegram",
        current_step: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE public.workflows
                    SET channel = $2,
                        request_key = $3,
                        approval_required = TRUE,
                        approval_status = 'pending',
                        status = 'waiting_approval',
                        current_step = COALESCE($4, current_step, 'waiting_approval'),
                        updated_at = NOW()
                    WHERE workflow_id = $1
                    RETURNING *
                    """,
                    workflow_id,
                    channel,
                    request_key,
                    current_step,
                )
        except Exception:
            payload = cls._memory_store.get(workflow_id)
            if payload is None:
                return None
            payload["channel"] = channel
            payload["request_key"] = request_key
            payload["approval_required"] = True
            payload["approval_status"] = "pending"
            payload["status"] = "waiting_approval"
            payload["current_step"] = current_step or payload.get("current_step")
            return dict(payload)

        if row is None:
            return None
        normalized = _normalize_workflow_row(dict(row))
        cls._memory_store[workflow_id] = normalized
        return normalized

    @classmethod
    async def attach_telegram_message_ref(
        cls,
        *,
        workflow_id: str,
        chat_id: int | str,
        message_id: int,
    ) -> Optional[Dict[str, Any]]:
        ref = {
            "chat_id": str(chat_id),
            "message_id": int(message_id),
        }

        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE public.workflows
                    SET telegram_message_ref = $2::jsonb,
                        updated_at = NOW()
                    WHERE workflow_id = $1
                    RETURNING *
                    """,
                    workflow_id,
                    json.dumps(ref, sort_keys=True),
                )
        except Exception:
            payload = cls._memory_store.get(workflow_id)
            if payload is None:
                return None
            payload["telegram_message_ref"] = ref
            return dict(payload)

        if row is None:
            return None
        normalized = _normalize_workflow_row(dict(row))
        cls._memory_store[workflow_id] = normalized
        return normalized

    @classmethod
    async def apply_approval_decision(
        cls,
        *,
        workflow_id: str,
        status: str,
        feedback: str = "",
        decision_source: Optional[str] = None,
        decision_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE public.workflows
                    SET approval_status = $2,
                        approval_feedback = NULLIF($3, ''),
                        approved_at = CASE
                            WHEN $2 IN ('approved', 'save') THEN NOW()
                            ELSE approved_at
                        END,
                        decision_source = $4,
                        decision_payload = COALESCE($5::jsonb, decision_payload, '{}'::jsonb),
                        updated_at = NOW()
                    WHERE workflow_id = $1
                    RETURNING *
                    """,
                    workflow_id,
                    status,
                    feedback,
                    decision_source,
                    json.dumps(decision_payload or {}, sort_keys=True),
                )
        except Exception:
            payload = cls._memory_store.get(workflow_id)
            if payload is None:
                return None
            payload["approval_status"] = status
            payload["approval_feedback"] = feedback or None
            payload["decision_source"] = decision_source
            payload["decision_payload"] = decision_payload or {}
            return dict(payload)

        if row is None:
            return None
        normalized = _normalize_workflow_row(dict(row))
        cls._memory_store[workflow_id] = normalized
        return normalized

    @classmethod
    async def record_terminal_status(
        cls,
        *,
        workflow_id: str,
        status: str,
        current_step: Optional[str] = None,
        error_message: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Sync a terminal workflow state (failed/completed/cancelled/discarded/expired)
        back to the public.workflows table so the DB row matches Temporal.
        """
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE public.workflows
                    SET status = $2,
                        current_step = COALESCE($3, current_step),
                        error_message = $4,
                        output_data = COALESCE(output_data, '{}'::jsonb) || COALESCE($5::jsonb, '{}'::jsonb),
                        completed_at = CASE
                            WHEN completed_at IS NULL THEN NOW()
                            ELSE completed_at
                        END,
                        updated_at = NOW()
                    WHERE workflow_id = $1
                    RETURNING *
                    """,
                    workflow_id,
                    status,
                    current_step,
                    error_message,
                    json.dumps(output_data or {}, sort_keys=True) if output_data else None,
                )
        except Exception:
            payload = cls._memory_store.get(workflow_id)
            if payload is None:
                return None
            payload["status"] = status
            if current_step:
                payload["current_step"] = current_step
            payload["error_message"] = error_message
            if output_data:
                payload["output_data"] = {
                    **(payload.get("output_data") or {}),
                    **output_data,
                }
            return dict(payload)

        if row is None:
            return None
        normalized = _normalize_workflow_row(dict(row))
        cls._memory_store[workflow_id] = normalized
        return normalized

    @classmethod
    async def list_for_user(
        cls,
        *,
        user_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 20), 50))
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT *
                    FROM public.workflows
                    WHERE user_id = $1::uuid
                    ORDER BY updated_at DESC NULLS LAST, started_at DESC NULLS LAST
                    LIMIT $2
                    """,
                    user_id,
                    normalized_limit,
                )
        except Exception:
            rows = [
                value
                for value in cls._memory_store.values()
                if value.get("user_id") == user_id
            ][:normalized_limit]
            return [dict(item) for item in rows]

        return [_normalize_workflow_row(dict(row)) for row in rows]
