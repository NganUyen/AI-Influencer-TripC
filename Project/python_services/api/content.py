"""
Content API Routes
Provides dashboard-friendly content views derived from workflow executions.
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
import logging
from temporalio.client import Client

from config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_temporal_client(request: Request) -> Client:
    client = getattr(request.app.state, "temporal_client", None)
    if client:
        return client
    return await Client.connect(
        settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
    )


def map_workflow_to_content_status(status: str) -> str:
    return {
        "waiting_approval": "pending_approval",
        "running": "draft",
        "completed": "published",
        "failed": "failed",
        "terminated": "failed",
        "timed_out": "failed",
    }.get(status, "draft")


@router.get("/list")
async def list_content_items(
    request: Request, limit: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """List content-like items for the dashboard."""
    try:
        client = await get_temporal_client(request)
        items: List[Dict[str, Any]] = []

        async for workflow_item in client.list_workflows(
            "WorkflowType = 'WeeklyMarketingWorkflow'"
        ):
            workflow_status = workflow_item.status.name.lower()
            current_step = None
            approval_feedback = ""

            try:
                handle = client.get_workflow_handle(
                    workflow_item.id, run_id=workflow_item.run_id
                )
                detailed_status = await handle.query("get_workflow_status")
                workflow_status = detailed_status.get("status", workflow_status)
                current_step = detailed_status.get("current_step")
                approval_feedback = detailed_status.get("approval_feedback", "")
            except Exception:
                pass

            created_at = (
                workflow_item.start_time.isoformat()
                if workflow_item.start_time
                else None
            )

            content_status = map_workflow_to_content_status(workflow_status)
            items.append(
                {
                    "id": workflow_item.id,
                    "title": f"Workflow {workflow_item.id}",
                    "content": f"Status: {workflow_status}",
                    "platform": [],
                    "status": content_status,
                    "scheduledAt": None,
                    "publishedAt": (
                        created_at if content_status == "published" else None
                    ),
                    "mediaUrls": [],
                    "createdAt": created_at,
                    "updatedAt": created_at,
                    "workflowId": workflow_item.id,
                    "runId": workflow_item.run_id,
                    "workflowStatus": workflow_status,
                    "currentStep": current_step,
                    "approvalFeedback": approval_feedback,
                }
            )

            if len(items) >= limit:
                break

        return {"items": items}
    except Exception as e:
        logger.error(f"Failed to list content items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_content_stats(request: Request) -> Dict[str, Any]:
    """Get summary stats for dashboard cards."""
    try:
        content_response = await list_content_items(request, limit=200)
        items = content_response.get("items", [])

        stats = {
            "total_content": len(items),
            "draft": 0,
            "pending_approval": 0,
            "scheduled": 0,
            "published": 0,
            "failed": 0,
            "active_campaigns": 0,
        }

        for item in items:
            status = item.get("status", "draft")
            if status in stats:
                stats[status] += 1
            if status in ["draft", "pending_approval", "scheduled"]:
                stats["active_campaigns"] += 1

        return stats
    except Exception as e:
        logger.error(f"Failed to get content stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
