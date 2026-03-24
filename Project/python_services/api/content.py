"""
Content API Routes
Provides dashboard-friendly content views derived from workflow executions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, List
import logging
from datetime import datetime
from temporalio.client import Client

from api.security import require_internal_api_token
from config.settings import settings
from services.content_persistence_service import ContentPersistenceService
from api.workflows import TemporalUnavailableError

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


async def get_temporal_client(request: Request) -> Client:
    client = getattr(request.app.state, "temporal_client", None)
    if client:
        return client
    try:
        return await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )
    except Exception as exc:
        raise TemporalUnavailableError(
            f"Temporal unavailable at {settings.TEMPORAL_ADDRESS}: {exc}"
        ) from exc


def map_workflow_to_content_status(status: str) -> str:
    return {
        "waiting_approval": "pending_approval",
        "approved": "draft",
        "running": "draft",
        "completed": "published",
        "rejected": "failed",
        "timeout": "failed",
        "failed": "failed",
        "terminated": "failed",
        "timed_out": "failed",
    }.get(status, "draft")


async def list_persisted_content_items(limit: int) -> List[Dict[str, Any]]:
    try:
        return await ContentPersistenceService.list_content_items(limit=limit)
    except Exception as exc:
        logger.warning("Falling back to workflow-derived content view: %s", exc)
        return []


async def enrich_items_with_workflow_details(
    client: Client, items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    workflow_cache: Dict[str, Dict[str, Any]] = {}
    for item in items:
        workflow_id = item.get("workflowId")
        if not workflow_id:
            continue

        if workflow_id not in workflow_cache:
            try:
                handle = client.get_workflow_handle(workflow_id)
                workflow_cache[workflow_id] = await handle.query("get_workflow_status")
            except Exception:
                workflow_cache[workflow_id] = {}

        details = workflow_cache.get(workflow_id, {})
        if not details:
            continue

        item["workflowStatus"] = details.get("status", item.get("workflowStatus"))
        item["currentStep"] = details.get("current_step", item.get("currentStep"))
        item["approvalFeedback"] = details.get(
            "approval_feedback", item.get("approvalFeedback", "")
        )

    return items


@router.get("/list")
async def list_content_items(
    request: Request, limit: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """List content-like items for the dashboard."""
    try:
        persisted_items = await list_persisted_content_items(limit)
        try:
            client = await get_temporal_client(request)
        except TemporalUnavailableError as exc:
            return {
                "items": list(persisted_items)[:limit],
                "temporal_available": False,
                "detail": str(exc),
            }

        items: List[Dict[str, Any]] = await enrich_items_with_workflow_details(
            client, list(persisted_items)
        )
        represented_workflow_ids = {
            item.get("workflowId") for item in persisted_items if item.get("workflowId")
        }

        async for workflow_item in client.list_workflows(
            "WorkflowType = 'WeeklyMarketingWorkflow'"
        ):
            if workflow_item.id in represented_workflow_ids:
                continue

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
                    "logicalPostId": workflow_item.id,
                    "runId": workflow_item.run_id,
                    "workflowStatus": workflow_status,
                    "currentStep": current_step,
                    "approvalFeedback": approval_feedback,
                }
            )

            if len(items) >= limit:
                break

        return {"items": items[:limit]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list content items: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry/{content_id}")
async def retry_content_publish(request: Request, content_id: str) -> Dict[str, Any]:
    """Retry publishing for a persisted failed content item."""
    try:
        post_config = await ContentPersistenceService.get_retry_post_config(content_id)
        if not post_config:
            raise HTTPException(status_code=404, detail="Content item not found")

        if post_config.get("status") != "failed":
            raise HTTPException(
                status_code=400,
                detail="Only failed content items can be retried",
            )

        if not post_config.get("platform"):
            raise HTTPException(
                status_code=400,
                detail="Content item does not have a retryable platform",
            )

        client = await get_temporal_client(request)
        from workflows import PostPublishingWorkflow

        retry_workflow_id = (
            f"content-retry-{content_id}-"
            f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        )
        retry_post_config = dict(post_config)
        retry_post_config["scheduled_time"] = None

        handle = await client.start_workflow(
            PostPublishingWorkflow.run,
            args=[retry_post_config],
            id=retry_workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )

        return {
            "content_id": content_id,
            "workflow_id": retry_workflow_id,
            "run_id": handle.id,
            "status": "retry_started",
            "source_workflow_id": post_config.get("workflow_id"),
        }
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry content publish: {str(e)}")
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
