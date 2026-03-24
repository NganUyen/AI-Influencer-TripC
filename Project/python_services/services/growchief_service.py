"""
GrowChief service adapter for the current public API.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List
from uuid import uuid4

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


def _canonical_job_status(value: Any) -> str:
    if value is None:
        return "pending"
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    status_map = {
        "queued": "pending",
        "pending": "pending",
        "scheduled": "pending",
        "running": "running",
        "processing": "running",
        "in_progress": "running",
        "completed": "completed",
        "complete": "completed",
        "success": "completed",
        "succeeded": "completed",
        "failed": "failed",
        "error": "failed",
        "canceled": "failed",
        "cancelled": "failed",
    }
    return status_map.get(normalized, normalized or "pending")


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _normalize_public_api_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    if base_url.endswith("/public") or base_url.endswith("/api/public"):
        return base_url
    return f"{base_url}/api/public"


def _parse_json_map(raw: str | None) -> Dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid GrowChief workflow map: %s", raw)
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key).strip().lower(): str(value).strip() for key, value in parsed.items() if str(value).strip()}


class GrowChiefService:
    """
    Adapter around the current workflow-based GrowChief public API.
    """

    def __init__(self):
        self.base_url = _normalize_public_api_base_url(settings.GROWCHIEF_API_URL or "")
        self.api_key = settings.GROWCHIEF_API_KEY
        if not self.base_url:
            raise ValueError("GROWCHIEF_API_URL is not configured")
        if not self.api_key:
            raise ValueError("GROWCHIEF_API_KEY is not configured")

        self.workflow_map = _parse_json_map(os.getenv("GROWCHIEF_WORKFLOW_MAP"))
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": self.api_key},
            timeout=120.0,
        )

    @staticmethod
    def normalize_webhook_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        payload_metadata = (
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        )
        metrics = _coalesce(
            data.get("metrics"),
            payload.get("metrics"),
            data.get("analytics"),
            payload.get("analytics"),
        )
        if not isinstance(metrics, dict):
            metrics = {}

        raw_status = _coalesce(data.get("status"), payload.get("status"))
        provider_job_id = _coalesce(
            data.get("job_id"),
            payload.get("job_id"),
            data.get("provider_job_id"),
            payload.get("provider_job_id"),
        )

        return {
            "provider": "growchief",
            "status": _canonical_job_status(raw_status),
            "provider_status": str(raw_status) if raw_status is not None else None,
            "provider_job_id": str(provider_job_id) if provider_job_id is not None else None,
            "platform": _coalesce(data.get("platform"), payload.get("platform")),
            "target_post_id": _coalesce(
                data.get("target_post_id"),
                payload.get("target_post_id"),
                data.get("post_id"),
                payload.get("post_id"),
            ),
            "target_url": _coalesce(
                data.get("target_url"),
                payload.get("target_url"),
                data.get("post_url"),
                payload.get("post_url"),
                data.get("url"),
                payload.get("url"),
            ),
            "action_types": _coalesce(
                data.get("action_types"),
                payload.get("action_types"),
                data.get("engagement_types"),
                payload.get("engagement_types"),
            )
            or [],
            "metrics": metrics,
            "error": _coalesce(
                data.get("error"),
                payload.get("error"),
                data.get("error_message"),
                payload.get("error_message"),
            ),
            "workflow_id": _coalesce(
                metadata.get("workflow_id"),
                payload_metadata.get("workflow_id"),
                data.get("workflow_id"),
                payload.get("workflow_id"),
            ),
            "content_id": _coalesce(
                metadata.get("content_id"),
                payload_metadata.get("content_id"),
                data.get("content_id"),
                payload.get("content_id"),
            ),
            "logical_post_id": _coalesce(
                metadata.get("logical_post_id"),
                payload_metadata.get("logical_post_id"),
                data.get("logical_post_id"),
                payload.get("logical_post_id"),
            ),
            "raw": payload,
        }

    async def list_workflows(self) -> List[Dict[str, Any]]:
        response = await self.client.get("/workflows")
        response.raise_for_status()
        workflows = response.json()
        return workflows if isinstance(workflows, list) else []

    async def _resolve_workflow_id(self, platform: str) -> str:
        mapped = self.workflow_map.get(platform.strip().lower())
        if mapped:
            return mapped

        workflows = [workflow for workflow in await self.list_workflows() if workflow.get("active") is not False]
        if len(workflows) == 1 and workflows[0].get("id"):
            return str(workflows[0]["id"])

        raise ValueError(
            f"No GrowChief workflow mapping configured for platform '{platform}'. "
            "Set GROWCHIEF_WORKFLOW_MAP or leave exactly one active workflow in GrowChief."
        )

    async def trigger_engagement(
        self,
        post_url: str,
        platform: str,
        engagement_type: List[str],
        account_count: int = 5,
        delay_minutes: int = 30,
    ) -> Dict[str, Any]:
        logger.info("Triggering GrowChief workflow for %s", post_url)

        workflow_id = await self._resolve_workflow_id(platform)
        payload = {"urls": [post_url]}

        response = await self.client.post(f"/workflows/{workflow_id}", json=payload)
        response.raise_for_status()
        raw = response.json()

        first_item = raw[0] if isinstance(raw, list) and raw else raw
        if not isinstance(first_item, dict):
            first_item = {}

        return {
            "job_id": f"growchief_{uuid4().hex}",
            "workflow_id": workflow_id,
            "status": _canonical_job_status(first_item.get("status")),
            "message": first_item.get("message"),
            "account_count": account_count,
            "delay_between_actions": delay_minutes,
            "engagement_types": engagement_type,
            "raw": raw,
        }

    async def get_engagement_metrics(
        self, platform: str, post_id: str
    ) -> Dict[str, Any]:
        logger.info("GrowChief public API does not expose post analytics; returning fallback metrics")
        return {
            "platform": platform,
            "post_id": post_id,
            "engagement_rate": 0.0,
            "source": "growchief_public_api_fallback",
            "message": "Current public GrowChief API does not expose direct post analytics.",
        }

    async def create_stealth_account(
        self, platform: str, persona_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.warning("GrowChief public API does not expose stealth account creation")
        return {
            "status": "unsupported",
            "platform": platform,
            "persona": persona_config,
            "message": "Current public GrowChief API does not expose stealth account creation.",
        }

    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        logger.warning("GrowChief public API does not expose account status")
        return {
            "account_id": account_id,
            "status": "unsupported",
            "message": "Current public GrowChief API does not expose account status.",
        }

    async def close(self):
        await self.client.aclose()
