"""
Workflow API Routes
Endpoints for managing Temporal workflows
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from temporalio.client import Client
from datetime import timedelta
import logging

from workflows import WeeklyMarketingWorkflow
from config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/start-weekly")
async def start_weekly_workflow(user_id: str, brand_config: Dict[str, Any]):
    """
    Start a new weekly marketing workflow

    Args:
        user_id: User identifier
        brand_config: Brand configuration (voice, platforms, content_pillars)
    """
    try:
        # Connect to Temporal
        client = await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )

        # Start workflow
        workflow_id = f"weekly-marketing-{user_id}"

        handle = await client.start_workflow(
            WeeklyMarketingWorkflow.run,
            args=[user_id, brand_config],
            id=workflow_id,
            task_queue="ai-influencer-tasks",
            execution_timeout=timedelta(days=8),  # Allow time for approval
        )

        logger.info(f"Started workflow: {workflow_id}")

        return {"workflow_id": workflow_id, "run_id": handle.id, "status": "started"}

    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve/{workflow_id}")
async def approve_workflow(workflow_id: str, approved: bool, feedback: str = ""):
    """
    Approve or reject a workflow strategy
    """
    try:
        client = await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )

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
async def get_workflow_status(workflow_id: str):
    """
    Get workflow status
    """
    try:
        client = await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )

        handle = client.get_workflow_handle(workflow_id)

        # Query workflow status
        status = await handle.query("get_workflow_status")

        return {"workflow_id": workflow_id, "status": status}

    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{workflow_id}")
async def cancel_workflow(workflow_id: str):
    """
    Cancel a running workflow
    """
    try:
        client = await Client.connect(
            settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
        )

        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()

        return {"workflow_id": workflow_id, "status": "cancelled"}

    except Exception as e:
        logger.error(f"Failed to cancel workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
