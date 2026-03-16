"""
Workflow API Routes
Endpoints for managing Temporal workflows
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from temporalio.client import Client
from datetime import timedelta
import logging

from workflows import WeeklyMarketingWorkflow
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


@router.post("/start-weekly")
async def start_weekly_workflow(
    request: Request, user_id: str, brand_config: Dict[str, Any]
):
    """
    Start a new weekly marketing workflow

    Args:
        user_id: User identifier
        brand_config: Brand configuration (voice, platforms, content_pillars)
    """
    try:
        client = await get_temporal_client(request)

        # Start workflow
        workflow_id = f"weekly-marketing-{user_id}"

        handle = await client.start_workflow(
            WeeklyMarketingWorkflow.run,
            args=[user_id, brand_config],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(days=8),  # Allow time for approval
        )

        logger.info(f"Started workflow: {workflow_id}")

        return {"workflow_id": workflow_id, "run_id": handle.id, "status": "started"}

    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve/{workflow_id}")
async def approve_workflow(
    request: Request, workflow_id: str, approved: bool, feedback: str = ""
):
    """
    Approve or reject a workflow strategy
    """
    try:
        client = await get_temporal_client(request)

        handle = client.get_workflow_handle(workflow_id)

        # Send approval signal
        await handle.signal("approve_strategy", approved, feedback)

        return {
            "workflow_id": workflow_id,
            "approved": approved,
            "status": "signal_sent",
        }

    except Exception as e:
        logger.error(f"Failed to send approval: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{workflow_id}")
async def get_workflow_status(request: Request, workflow_id: str):
    """
    Get workflow status
    """
    try:
        client = await get_temporal_client(request)

        handle = client.get_workflow_handle(workflow_id)

        # Query workflow status
        status = await handle.query("get_workflow_status")

        return {"workflow_id": workflow_id, "status": status}

    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_workflows(
    request: Request, limit: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    """List recent weekly marketing workflows for dashboard polling."""
    try:
        client = await get_temporal_client(request)
        workflows: List[Dict[str, Any]] = []

        async for item in client.list_workflows(
            "WorkflowType = 'WeeklyMarketingWorkflow'"
        ):
            workflows.append(
                {
                    "workflow_id": item.id,
                    "run_id": item.run_id,
                    "status": item.status.name.lower(),
                    "start_time": (
                        item.start_time.isoformat() if item.start_time else None
                    ),
                }
            )
            if len(workflows) >= limit:
                break

        return {"workflows": workflows}
    except Exception as e:
        logger.error(f"Failed to list workflows: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{workflow_id}")
async def cancel_workflow(request: Request, workflow_id: str):
    """
    Cancel a running workflow
    """
    try:
        client = await get_temporal_client(request)

        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()

        return {"workflow_id": workflow_id, "status": "cancelled"}

    except Exception as e:
        logger.error(f"Failed to cancel workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
