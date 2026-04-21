"""
Temporal orchestration helpers for TikTok publish and account automation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from temporalio.client import Client

from config.settings import settings


def _parse_schedule_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    scheduled_time = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
    return scheduled_time.astimezone(timezone.utc)


class TikTokOrchestrationService:
    @staticmethod
    def _publish_workflow_id(post_config: Dict[str, Any], *, deterministic: bool) -> str:
        if deterministic:
            suffix = (
                post_config.get("content_record_id")
                or post_config.get("id")
                or uuid4().hex[:8]
            )
            return f"publish-{suffix}"
        return f"publish-{post_config.get('id') or uuid4().hex[:8]}-{uuid4().hex[:6]}"

    @staticmethod
    def _looks_like_workflow_already_started(exc: Exception) -> bool:
        text = str(exc).lower()
        return "already started" in text or "workflow execution already started" in text

    @classmethod
    async def _get_temporal_client(cls, existing_client: Any | None = None) -> Client:
        if existing_client:
            return existing_client
        return await Client.connect(
            settings.temporal_connection_address,
            namespace=settings.TEMPORAL_NAMESPACE,
        )

    @classmethod
    async def start_publish_workflow(
        cls,
        *,
        post_config: Dict[str, Any],
        temporal_client: Any | None = None,
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        from workflows.weekly_marketing_workflow import PostPublishingWorkflow

        client = await cls._get_temporal_client(temporal_client)
        deterministic = cls.schedule_is_future(post_config.get("scheduled_time"))
        workflow_id = cls._publish_workflow_id(
            post_config,
            deterministic=deterministic,
        )
        try:
            handle = await client.start_workflow(
                PostPublishingWorkflow.run,
                args=[post_config],
                id=workflow_id,
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            )
        except Exception as exc:
            if deterministic and cls._looks_like_workflow_already_started(exc):
                client.get_workflow_handle(workflow_id)
                return {
                    "status": "scheduled",
                    "workflow_id": workflow_id,
                    "run_id": None,
                    "result": None,
                    "reused_existing": True,
                }
            raise
        if not wait_for_completion:
            return {
                "status": "scheduled",
                "workflow_id": workflow_id,
                "run_id": getattr(handle, "first_execution_run_id", None),
            }
        result = await handle.result()
        return {
            "status": result.get("status", "published"),
            "workflow_id": workflow_id,
            "run_id": getattr(handle, "first_execution_run_id", None),
            "result": result.get("results") or result,
        }

    @classmethod
    async def start_account_bootstrap(
        cls,
        *,
        payload: Dict[str, Any],
        temporal_client: Any | None = None,
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        from workflows.tiktok_account_workflow import TikTokAccountBootstrapWorkflow

        client = await cls._get_temporal_client(temporal_client)
        workflow_id = (
            f"tiktok-bootstrap-{payload.get('social_account_id') or uuid4().hex[:8]}-"
            f"{uuid4().hex[:6]}"
        )
        handle = await client.start_workflow(
            TikTokAccountBootstrapWorkflow.run,
            args=[payload],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        if not wait_for_completion:
            return {
                "status": "started",
                "workflow_id": workflow_id,
                "run_id": getattr(handle, "first_execution_run_id", None),
            }
        result = await handle.result()
        return {
            "status": result.get("status", "connected"),
            "workflow_id": workflow_id,
            "run_id": getattr(handle, "first_execution_run_id", None),
            "result": result,
        }

    @classmethod
    async def start_account_refresh(
        cls,
        *,
        payload: Dict[str, Any],
        temporal_client: Any | None = None,
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        from workflows.tiktok_account_workflow import TikTokAccountRefreshWorkflow

        client = await cls._get_temporal_client(temporal_client)
        workflow_id = (
            f"tiktok-refresh-{payload.get('social_account_id') or uuid4().hex[:8]}-"
            f"{uuid4().hex[:6]}"
        )
        handle = await client.start_workflow(
            TikTokAccountRefreshWorkflow.run,
            args=[payload],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
        if not wait_for_completion:
            return {
                "status": "started",
                "workflow_id": workflow_id,
                "run_id": getattr(handle, "first_execution_run_id", None),
            }
        result = await handle.result()
        return {
            "status": result.get("status", "connected"),
            "workflow_id": workflow_id,
            "run_id": getattr(handle, "first_execution_run_id", None),
            "result": result,
        }

    @classmethod
    def schedule_is_future(cls, schedule_time: Optional[str]) -> bool:
        parsed = _parse_schedule_time(schedule_time)
        return bool(parsed and parsed > datetime.now(timezone.utc))
