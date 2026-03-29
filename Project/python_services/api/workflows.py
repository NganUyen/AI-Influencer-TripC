"""
Workflow API Routes
Endpoints for managing Temporal workflows
"""

from uuid import uuid4
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from temporalio.client import Client
from datetime import timedelta
import logging

from api.security import require_internal_api_token
from workflows import WeeklyMarketingWorkflow
from config.settings import settings
from services.contracts import (
    ApprovedProductionPackageContract,
    VideoWorkflowPersonaSnapshotContract,
    VideoWorkflowStartPayloadContract,
)
from services.persona_registry_service import PersonaRegistryService

try:
    # TODO: ShortVideoWorkflow needs full registration after Step 3.
    from workflows.short_video_workflow import ShortVideoWorkflow
except ImportError:  # pragma: no cover - stepwise rollout compatibility
    ShortVideoWorkflow = None

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


class TemporalUnavailableError(RuntimeError):
    """Raised when Temporal cannot be reached for a request."""


class StartVideoRequest(BaseModel):
    persona_id: str
    topic: str
    tone: str = "natural"
    platform: str = "tiktok"
    telegram_chat_id: Optional[str] = None
    user_id: Optional[str] = None
    owner_key: Optional[str] = None
    talking_head_optional: bool = False
    approved_package: Optional[ApprovedProductionPackageContract] = None


def _build_video_workflow_persona_snapshot(
    persona: Dict[str, Any],
) -> VideoWorkflowPersonaSnapshotContract:
    return VideoWorkflowPersonaSnapshotContract(
        display_name=persona.get("display_name"),
        language=persona.get("language") or "English",
        tts_voice=persona.get("tts_voice"),
        heygen_avatar_id=persona.get("heygen_avatar_id"),
    )


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
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start-video")
async def start_video_workflow(request: Request, payload: StartVideoRequest):
    """
    Start a new short-video workflow.
    """
    telegram_chat_id = payload.telegram_chat_id or settings.TELEGRAM_CHAT_ID
    owner_key = payload.owner_key
    if not owner_key and telegram_chat_id:
        owner_key = f"telegram:{telegram_chat_id}"

    persona = await PersonaRegistryService.get_persona(
        payload.persona_id,
        user_id=payload.user_id,
        owner_key=owner_key,
    )
    if not persona:
        raise HTTPException(
            status_code=400,
            detail=f"Persona '{payload.persona_id}' does not exist.",
        )
    if persona.get("status") != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Persona '{payload.persona_id}' is not ready.",
        )
    if not persona.get("tts_voice"):
        raise HTTPException(
            status_code=400,
            detail="Persona is missing tts_voice.",
        )
    # When talking_head is required, verify heygen_avatar_id exists
    if not payload.talking_head_optional and not persona.get("heygen_avatar_id"):
        raise HTTPException(
            status_code=400,
            detail="Persona is missing heygen_avatar_id. Run persona avatar setup first, or set talking_head_optional=True.",
        )
    if ShortVideoWorkflow is None:
        raise HTTPException(
            status_code=503,
            detail="ShortVideoWorkflow is not available yet.",
        )

    try:
        client = await get_temporal_client(request)
        workflow_id = f"video-{payload.persona_id}-{uuid4().hex[:8]}"
        start_payload = VideoWorkflowStartPayloadContract(
            persona_id=payload.persona_id,
            topic=payload.topic,
            tone=payload.tone,
            platform=payload.platform,
            telegram_chat_id=telegram_chat_id,
            user_id=payload.user_id,
            owner_key=owner_key,
            talking_head_optional=payload.talking_head_optional,
            approved_package=payload.approved_package,
            persona_snapshot=_build_video_workflow_persona_snapshot(persona),
        )

        handle = await client.start_workflow(
            ShortVideoWorkflow.run,
            args=[start_payload.model_dump(mode="json")],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(hours=2),
        )

        logger.info("Started short-video workflow: %s", workflow_id)
        return {"workflow_id": workflow_id, "run_id": handle.id, "status": "started"}
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start short-video workflow: {str(e)}")
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
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_workflows(request: Request, limit: int = 20) -> Dict[str, Any]:
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
    except TemporalUnavailableError as exc:
        return {
            "workflows": [],
            "temporal_available": False,
            "detail": str(exc),
        }
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
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as e:
        logger.error(f"Failed to cancel workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
