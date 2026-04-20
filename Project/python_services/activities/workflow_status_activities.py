"""
Lightweight activity to sync terminal workflow status to the public.workflows table.

Called fire-and-forget from ShortVideoWorkflow terminal paths so the Supabase
row stays in sync with Temporal's actual workflow state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def sync_workflow_terminal_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sync a terminal status (failed/completed/cancelled/discarded/expired)
    to public.workflows.

    Payload keys:
        workflow_id: str (required)
        status: str (required) — one of failed/completed/cancelled/discarded/expired
        current_step: str | None
        error_message: str | None
        output_data: dict | None
    """
    from services.workflow_state_service import WorkflowStateService

    workflow_id = payload["workflow_id"]
    status = payload["status"]
    current_step = payload.get("current_step")
    error_message = payload.get("error_message")
    output_data = payload.get("output_data")

    logger.info(
        "Syncing terminal status to DB | workflow_id=%s | status=%s | step=%s | has_error=%s",
        workflow_id,
        status,
        current_step,
        bool(error_message),
    )

    result = await WorkflowStateService.record_terminal_status(
        workflow_id=workflow_id,
        status=status,
        current_step=current_step,
        error_message=error_message,
        output_data=output_data,
    )

    return {
        "synced": result is not None,
        "workflow_id": workflow_id,
        "status": status,
    }
