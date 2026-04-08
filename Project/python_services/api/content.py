"""
Content API Routes
Provides dashboard-friendly content views derived from workflow executions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, List
import logging
from datetime import datetime
from temporalio.client import Client
from pydantic import BaseModel, Field

from api.security import require_internal_api_token
from config.settings import settings
from services.content_persistence_service import ContentPersistenceService
from services.growchief_service import GrowChiefService
from api.workflows import TemporalUnavailableError, _resolve_workflow_status_payload

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


class EngagementTriggerRequest(BaseModel):
    action_types: List[str] = Field(
        default_factory=lambda: ["like", "comment", "share"]
    )
    account_count: int = Field(default=5, ge=1, le=50)
    delay_minutes: int = Field(default=30, ge=0, le=240)


async def _get_content_item_or_404(content_id: str) -> Dict[str, Any]:
    item = await ContentPersistenceService.get_retry_post_config(content_id)
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    return item


def _build_post_data_for_engagement(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id") or item.get("content_record_id"),
        "post_id": item.get("id") or item.get("content_record_id"),
        "logical_post_id": item.get("logical_post_id") or item.get("id"),
        "content_record_id": item.get("content_record_id"),
        "workflow_id": item.get("workflow_id"),
        "platform": item.get("platform"),
        "platform_post_id": item.get("platform_post_id")
        or item.get("provider_post_id"),
        "provider_post_id": item.get("provider_post_id")
        or item.get("platform_post_id"),
        "post_url": item.get("post_url"),
    }


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
                # [SAFETY-3] Use fallback status resolution for closed workflows
                resolved = await _resolve_workflow_status_payload(handle)
                status_data = resolved.get("status", {})
                if isinstance(status_data, dict):
                    workflow_cache[workflow_id] = status_data
                else:
                    workflow_cache[workflow_id] = {}
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
) -> Dict[str, Any]:
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
            "WorkflowType = 'WeeklyMarketingWorkflow' OR WorkflowType = 'ShortVideoWorkflow'"
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
            f"content-retry-{content_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
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


@router.get("/providers/{content_id}")
async def get_content_provider_wiring(content_id: str) -> Dict[str, Any]:
    """Inspect Postiz/GrowChief linkage metadata for a content item."""
    try:
        item = await _get_content_item_or_404(content_id)
        return {
            "content_id": content_id,
            "logical_post_id": item.get("logical_post_id") or item.get("id"),
            "workflow_id": item.get("workflow_id"),
            "platform": item.get("platform"),
            "status": item.get("status"),
            "publish_method": item.get("publish_method"),
            "platform_post_id": item.get("platform_post_id"),
            "provider_post_id": item.get("provider_post_id"),
            "post_url": item.get("post_url"),
            "publish_error": item.get("publish_error"),
            "syndicate_triggered": bool(item.get("syndicate_triggered")),
            "syndicate_job_id": item.get("syndicate_job_id"),
            "engagement_metrics": item.get("engagement_metrics") or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to inspect provider wiring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engagement/{content_id}")
async def check_content_engagement(content_id: str) -> Dict[str, Any]:
    """Fetch and persist the latest GrowChief engagement snapshot for a content item."""
    growchief = GrowChiefService()
    try:
        item = await _get_content_item_or_404(content_id)
        platform = item.get("platform")
        post_id = (
            item.get("platform_post_id")
            or item.get("provider_post_id")
            or item.get("id")
        )
        if not platform:
            raise HTTPException(
                status_code=400, detail="Content item platform is missing"
            )

        metrics = await growchief.get_engagement_metrics(
            platform=platform, post_id=str(post_id)
        )
        engagement_result = {
            "status": "completed",
            "metrics": metrics,
            "syndicate_triggered": bool(item.get("syndicate_triggered")),
        }
        await ContentPersistenceService.record_engagement_result(
            workflow_id=item.get("workflow_id"),
            post_data=_build_post_data_for_engagement(item),
            engagement_result=engagement_result,
        )
        return {
            "content_id": content_id,
            "platform": platform,
            "post_id": post_id,
            "metrics": metrics,
            "status": "engagement_snapshot_recorded",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check content engagement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await growchief.close()


@router.post("/engagement/{content_id}/trigger")
async def trigger_content_engagement(
    content_id: str,
    payload: EngagementTriggerRequest,
) -> Dict[str, Any]:
    """Trigger GrowChief engagement actions for a content item and persist the outcome."""
    growchief = GrowChiefService()
    try:
        item = await _get_content_item_or_404(content_id)
        platform = item.get("platform")
        if not platform:
            raise HTTPException(
                status_code=400, detail="Content item platform is missing"
            )

        post_url = item.get("post_url")
        post_id = (
            item.get("platform_post_id")
            or item.get("provider_post_id")
            or item.get("id")
        )
        if not post_url and post_id:
            post_url = f"{platform}://{post_id}"
        if not post_url:
            raise HTTPException(
                status_code=400,
                detail="Content item does not have a publish URL or provider post id for engagement",
            )

        trigger_result = await growchief.trigger_engagement(
            post_url=post_url,
            platform=platform,
            engagement_type=payload.action_types,
            account_count=payload.account_count,
            delay_minutes=payload.delay_minutes,
        )

        engagement_result = {
            "status": "completed",
            "metrics": {},
            "syndicate_triggered": True,
            "syndicate_result": trigger_result,
            "action_types": payload.action_types,
        }
        post_data = _build_post_data_for_engagement(item)
        post_data["post_url"] = post_url
        await ContentPersistenceService.record_engagement_result(
            workflow_id=item.get("workflow_id"),
            post_data=post_data,
            engagement_result=engagement_result,
        )

        return {
            "content_id": content_id,
            "platform": platform,
            "post_url": post_url,
            "action_types": payload.action_types,
            "account_count": payload.account_count,
            "status": "engagement_triggered",
            "job": trigger_result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger content engagement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await growchief.close()


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
