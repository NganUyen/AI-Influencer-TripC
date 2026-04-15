"""
Durable approval request state backed by public.approvals.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from services.database_service import DatabaseService
from services.workflow_state_service import WorkflowStateService


_ACTION_TO_STATUS = {
    "approve": ("approved", True, ""),
    "reject": ("rejected", False, ""),
    "save": ("save", True, "save"),
    "discard": ("discard", False, "discard"),
}


def _normalize_approval_row(row: Any) -> Dict[str, Any]:
    status = row.get("status") or "pending"
    approved = True if status in {"approved", "save"} else False
    if status == "pending":
        approved = False
    return {
        "approval_id": str(row["id"]) if row.get("id") else row.get("approval_id"),
        "content_id": str(row["content_id"]) if row.get("content_id") else None,
        "workflow_id": row.get("workflow_id"),
        "approver_id": str(row["approver_id"]) if row.get("approver_id") else None,
        "channel": row.get("channel") or "telegram",
        "request_key": row.get("request_key"),
        "telegram_message_ref": row.get("telegram_message_ref") or None,
        "status": status,
        "approved": approved,
        "feedback": row.get("feedback") or "",
        "decision_source": row.get("decision_source"),
        "decision_payload": row.get("decision_payload") or {},
        "metadata": row.get("metadata") or {},
        "approved_at": row["approved_at"].isoformat() if row.get("approved_at") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


class ApprovalStateService:
    _memory_store: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _row_matches_identifier(row: Dict[str, Any], identifier: str) -> bool:
        return (
            str(row.get("approval_id") or row.get("id") or "").strip() == identifier
            or str(row.get("request_key") or "").strip() == identifier
        )

    @classmethod
    async def create_request(
        cls,
        *,
        approver_id: str,
        workflow_id: Optional[str] = None,
        content_id: Optional[str] = None,
        channel: str = "telegram",
        request_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        approval_id = str(uuid4())
        resolved_request_key = request_key or approval_id
        payload = {
            "approval_id": approval_id,
            "content_id": content_id,
            "workflow_id": workflow_id,
            "approver_id": approver_id,
            "channel": channel,
            "request_key": resolved_request_key,
            "telegram_message_ref": None,
            "status": "pending",
            "approved": False,
            "feedback": "",
            "decision_source": None,
            "decision_payload": {},
            "metadata": metadata or {},
            "approved_at": None,
            "created_at": None,
            "updated_at": None,
        }

        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO public.approvals (
                        id,
                        content_id,
                        workflow_id,
                        approver_id,
                        channel,
                        request_key,
                        telegram_message_ref,
                        status,
                        decision_source,
                        decision_payload,
                        metadata
                    )
                    VALUES (
                        $1::uuid,
                        $2::uuid,
                        $3,
                        $4::uuid,
                        $5,
                        $6,
                        NULL,
                        'pending',
                        NULL,
                        '{}'::jsonb,
                        $7::jsonb
                    )
                    RETURNING *
                    """,
                    approval_id,
                    content_id,
                    workflow_id,
                    approver_id,
                    channel,
                    resolved_request_key,
                    json.dumps(metadata or {}, sort_keys=True),
                )
        except Exception:
            cls._memory_store[approval_id] = payload
            if workflow_id:
                await WorkflowStateService.attach_approval_request(
                    workflow_id=workflow_id,
                    request_key=resolved_request_key,
                    channel=channel,
                )
            return dict(payload)

        normalized = _normalize_approval_row(dict(row))
        cls._memory_store[approval_id] = normalized
        if workflow_id:
            await WorkflowStateService.attach_approval_request(
                workflow_id=workflow_id,
                request_key=resolved_request_key,
                channel=channel,
            )
        return normalized

    @classmethod
    async def attach_telegram_message(
        cls,
        *,
        approval_id: str,
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
                    UPDATE public.approvals
                    SET telegram_message_ref = $2::jsonb,
                        updated_at = NOW()
                    WHERE id = $1::uuid
                    RETURNING *
                    """,
                    approval_id,
                    json.dumps(ref, sort_keys=True),
                )
        except Exception:
            approval = cls._memory_store.get(approval_id)
            if approval is None:
                return None
            approval["telegram_message_ref"] = ref
            if approval.get("workflow_id"):
                await WorkflowStateService.attach_telegram_message_ref(
                    workflow_id=approval["workflow_id"],
                    chat_id=chat_id,
                    message_id=message_id,
                )
            return dict(approval)

        if row is None:
            return None
        normalized = _normalize_approval_row(dict(row))
        cls._memory_store[approval_id] = normalized
        if normalized.get("workflow_id"):
            await WorkflowStateService.attach_telegram_message_ref(
                workflow_id=normalized["workflow_id"],
                chat_id=chat_id,
                message_id=message_id,
            )
        return normalized

    @classmethod
    async def get_status(cls, approval_id: str) -> Dict[str, Any]:
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT *
                    FROM public.approvals
                    WHERE id::text = $1
                       OR request_key = $1
                    LIMIT 1
                    """,
                    approval_id,
                )
        except Exception:
            row = next(
                (
                    value
                    for value in cls._memory_store.values()
                    if cls._row_matches_identifier(value, approval_id)
                ),
                None,
            )

        if row is None:
            return {"approved": False, "feedback": "Request not found"}
        return _normalize_approval_row(dict(row))

    @classmethod
    async def apply_decision(
        cls,
        *,
        approval_id: str,
        action: str,
        decision_source: str,
        decision_payload: Optional[Dict[str, Any]] = None,
        feedback: str = "",
    ) -> Optional[Dict[str, Any]]:
        if action not in _ACTION_TO_STATUS:
            raise ValueError(f"Unsupported approval action: {action}")

        status, approved, default_feedback = _ACTION_TO_STATUS[action]
        resolved_feedback = feedback or default_feedback

        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE public.approvals
                    SET status = $2,
                        feedback = NULLIF($3, ''),
                        approved_at = CASE
                            WHEN $2 IN ('approved', 'save') THEN NOW()
                            ELSE approved_at
                        END,
                        decision_source = $4,
                        decision_payload = $5::jsonb,
                        updated_at = NOW()
                    WHERE id = $1::uuid
                    RETURNING *
                    """,
                    approval_id,
                    status,
                    resolved_feedback,
                    decision_source,
                    json.dumps(decision_payload or {}, sort_keys=True),
                )
        except Exception:
            row = cls._memory_store.get(approval_id)
            if row is None:
                return None
            row["status"] = status
            row["approved"] = approved
            row["feedback"] = resolved_feedback
            row["decision_source"] = decision_source
            row["decision_payload"] = decision_payload or {}
        else:
            if row is None:
                return None
            row = _normalize_approval_row(dict(row))
            cls._memory_store[approval_id] = row

        if row.get("workflow_id"):
            await WorkflowStateService.apply_approval_decision(
                workflow_id=row["workflow_id"],
                status=status,
                feedback=resolved_feedback,
                decision_source=decision_source,
                decision_payload=decision_payload,
            )
        return dict(row)

    @classmethod
    async def list_for_approver(
        cls,
        *,
        approver_id: str,
        limit: int = 20,
        statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 20), 100))
        status_list = [str(item).strip() for item in (statuses or []) if str(item).strip()]
        try:
            pool = await DatabaseService.get_pool()
            async with pool.acquire() as conn:
                if status_list:
                    rows = await conn.fetch(
                        """
                        SELECT *
                        FROM public.approvals
                        WHERE approver_id = $1::uuid
                          AND status = ANY($2::text[])
                        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                        LIMIT $3
                        """,
                        approver_id,
                        status_list,
                        normalized_limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT *
                        FROM public.approvals
                        WHERE approver_id = $1::uuid
                        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                        LIMIT $2
                        """,
                        approver_id,
                        normalized_limit,
                    )
        except Exception:
            rows = [
                value
                for value in cls._memory_store.values()
                if str(value.get("approver_id") or "").strip() == approver_id
                and (
                    not status_list
                    or str(value.get("status") or "").strip() in status_list
                )
            ][:normalized_limit]
            return [dict(item) for item in rows]

        return [_normalize_approval_row(dict(row)) for row in rows]
