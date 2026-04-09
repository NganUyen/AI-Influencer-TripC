"""
Workflow API Routes
Endpoints for managing Temporal workflows
"""

from uuid import uuid4
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from temporalio.api.enums.v1 import WorkflowExecutionStatus
from temporalio.client import Client
from datetime import timedelta
import logging

from api.security import require_internal_api_token
from workflows import WeeklyMarketingWorkflow
from config.settings import settings
from services.contracts import (
    ApprovedProductionPackageContract,
    VideoAudioPolicyContract,
    VideoReviewPlanContract,
    VideoWorkflowPersonaSnapshotContract,
    VideoWorkflowStartPayloadContract,
)
from services.persona_registry_service import PersonaRegistryService

try:
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
    review_plan: Optional[VideoReviewPlanContract] = None
    execution_mode: Optional[str] = None
    audio_policy: Optional[VideoAudioPolicyContract] = None


def _normalize_execution_status(status_value: Any) -> Optional[str]:
    """Convert Temporal WorkflowExecutionStatus enum to lowercase string."""
    try:
        enum_name = WorkflowExecutionStatus.Name(int(status_value))
    except Exception:
        return None
    normalized = enum_name.replace("WORKFLOW_EXECUTION_STATUS_", "").lower()
    return normalized or None


def _extract_describe_execution_status(description: Any) -> Optional[str]:
    """Extract execution status from workflow description."""
    raw_description = getattr(description, "raw_description", None)
    workflow_info = getattr(raw_description, "workflow_execution_info", None)
    status_value = getattr(workflow_info, "status", None)
    if status_value is not None:
        return _normalize_execution_status(status_value)

    # Test doubles and some client wrappers expose status directly as an enum-like object
    direct_status = getattr(description, "status", None)
    direct_status_name = getattr(direct_status, "name", None)
    if isinstance(direct_status_name, str) and direct_status_name.strip():
        return direct_status_name.strip().lower()

    return None


async def _resolve_workflow_status_payload(handle: Any) -> Dict[str, Any]:
    """
    Resolve workflow status through multiple fallback strategies:
    1. Query the workflow directly (if still running)
    2. Describe + result (if workflow completed/failed)
    """
    # Try query first (works for running workflows)
    try:
        status = await handle.query("get_workflow_status")
        return {
            "status": status,
            "execution_status": "running",
            "source": "query",
        }
    except Exception as query_exc:
        logger.info(
            "Workflow query unavailable, falling back to describe/result: %s", query_exc
        )

    # Fallback to describe for execution status
    execution_status = None
    try:
        description = await handle.describe()
        execution_status = _extract_describe_execution_status(description)
    except Exception as describe_exc:
        logger.warning("Workflow describe failed: %s", describe_exc)

    # If describe says the workflow is still open/running, don't call result()
    if execution_status in {"running"}:
        return {
            "status": {
                "status": execution_status,
                "current_step": execution_status,
                "workflow_id": getattr(handle, "id", None),
            },
            "execution_status": execution_status,
            "source": "describe",
        }

    # Try to get terminal result for completed/failed workflows
    try:
        terminal_result = await handle.result()
        if isinstance(terminal_result, dict):
            terminal_status = terminal_result.get("status")
            if terminal_status:
                return {
                    "status": terminal_result,
                    "execution_status": execution_status or "completed",
                    "source": "result",
                }
        return {
            "status": execution_status or "completed",
            "execution_status": execution_status or "completed",
            "source": "result",
            "result": terminal_result,
        }
    except Exception as result_exc:
        logger.warning("Workflow result fetch failed: %s", result_exc)
        return {
            "status": execution_status or "unknown",
            "execution_status": execution_status or "unknown",
            "source": "describe",
            "error": str(result_exc),
        }


def _build_video_workflow_persona_snapshot(
    persona: Dict[str, Any],
) -> VideoWorkflowPersonaSnapshotContract:
    return VideoWorkflowPersonaSnapshotContract(
        persona_id=persona.get("persona_id"),
        display_name=persona.get("display_name"),
        language=persona.get("language") or "English",
        tts_voice=persona.get("tts_voice"),
        heygen_avatar_id=persona.get("heygen_avatar_id"),
        avatar_image_url=persona.get("avatar_image_url"),
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
            review_plan=payload.review_plan,
            execution_mode=payload.execution_mode,
            audio_policy=payload.audio_policy,
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
        logger.error(
            "Temporal unavailable for workflow start | persona_id=%s | topic=%s | error=%s",
            payload.persona_id,
            payload.topic,
            exc,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to start short-video workflow | persona_id=%s | topic=%s | error=%s",
            payload.persona_id,
            payload.topic,
            e,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        status = await _resolve_workflow_status_payload(handle)

        return {"workflow_id": workflow_id, "status": status}
    except TemporalUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as e:
        logger.error(f"Failed to get workflow status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_workflows(request: Request, limit: int = 20) -> Dict[str, Any]:
    """List recent weekly marketing and short-video workflows for polling/debugging."""
    try:
        client = await get_temporal_client(request)
        workflows: List[Dict[str, Any]] = []

        async for item in client.list_workflows(
            "WorkflowType = 'WeeklyMarketingWorkflow' OR WorkflowType = 'ShortVideoWorkflow'"
        ):
            workflows.append(
                {
                    "workflow_id": item.id,
                    "run_id": item.run_id,
                    "status": item.status.name.lower(),
                    "workflow_type": getattr(item, "workflow_type", None),
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
