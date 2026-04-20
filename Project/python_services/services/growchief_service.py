"""
GrowChief service adapter for the current public API.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from config.settings import settings
from services.errors import (
    GrowChiefAuthError,
    GrowChiefConfigurationError,
    QuotaExceededError,
    GrowChiefRetryableError,
    GrowChiefServiceError,
)
from services.quota_monitor_service import QuotaMonitorService

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


def _public_api_base_urls(value: str) -> List[str]:
    base_url = value.rstrip("/")
    if not base_url:
        return []
    if base_url.endswith("/public") or base_url.endswith("/api/public"):
        return [base_url]
    # Support current prod `/public` and older `/api/public` layouts.
    return [f"{base_url}/public", f"{base_url}/api/public"]


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


def _response_content_type(response: Any) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get("content-type") or headers.get("Content-Type") or "").lower()


def _response_preview(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text.strip()[:200]
    return ""


class GrowChiefService:
    """
    Adapter around the current workflow-based GrowChief public API.
    """

    def __init__(self):
        self.base_urls = _public_api_base_urls(settings.GROWCHIEF_API_URL or "")
        self.base_url = self.base_urls[0] if self.base_urls else ""
        self.api_key = settings.GROWCHIEF_API_KEY
        if not self.base_url:
            raise ValueError("GROWCHIEF_API_URL is not configured")
        if not self.api_key:
            raise ValueError("GROWCHIEF_API_KEY is not configured")

        self.workflow_map = _parse_json_map(os.getenv("GROWCHIEF_WORKFLOW_MAP"))
        self.client = httpx.AsyncClient(
            headers={"Authorization": self.api_key},
            timeout=120.0,
        )

    async def _record_usage(
        self,
        operation: str,
        usage: Dict[str, Any],
        error: Exception | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from services.quota_monitor_service import QuotaMonitorService
        quota_metadata = {
            "service": "growchief_service",
            "operation": operation,
            "status": "error" if error else "success",
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="growchief",
            usage=usage,
            metadata=quota_metadata,
        )

    @staticmethod
    def _raise_for_http_status(response: Any, operation: str) -> None:
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 400:
            return

        if status_code == 401:
            raise GrowChiefAuthError(
                "GrowChief API key was rejected or the GrowChief admin bootstrap is incomplete."
            )
        if status_code == 429 or status_code >= 500:
            raise GrowChiefRetryableError(
                f"GrowChief {operation} failed with status {status_code}."
            )
        raise GrowChiefServiceError(
            f"GrowChief {operation} failed with status {status_code}."
        )

    @classmethod
    def _decode_json(cls, response: Any, operation: str) -> Any:
        cls._raise_for_http_status(response, operation)
        try:
            return response.json()
        except ValueError as exc:
            preview = _response_preview(response)
            content_type = _response_content_type(response)
            if "html" in content_type or preview.startswith("<"):
                raise GrowChiefRetryableError(
                    f"GrowChief {operation} returned HTML instead of JSON."
                ) from exc
            raise GrowChiefRetryableError(
                f"GrowChief {operation} returned invalid JSON."
            ) from exc

    @staticmethod
    def _classify_transport_error(
        exc: httpx.HTTPError, operation: str
    ) -> GrowChiefServiceError:
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                GrowChiefService._raise_for_http_status(response, operation)
            except GrowChiefServiceError as provider_exc:
                return provider_exc
        return GrowChiefRetryableError(f"GrowChief {operation} request failed.")

    async def _get_json(self, path: str, *, operation: str) -> Any:
        last_transport_error: Optional[httpx.HTTPError] = None
        for index, base_url in enumerate(self.base_urls):
            try:
                response = await self.client.get(f"{base_url}{path}")
            except httpx.HTTPError as exc:
                last_transport_error = exc
                if index < len(self.base_urls) - 1:
                    continue
                raise self._classify_transport_error(exc, operation) from exc

            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code == 404 and index < len(self.base_urls) - 1:
                continue
            return self._decode_json(response, operation)

        if last_transport_error is not None:
            raise self._classify_transport_error(last_transport_error, operation) from last_transport_error
        raise GrowChiefConfigurationError("GROWCHIEF_API_URL is not configured")

    async def _post_json(
        self, path: str, *, json_payload: Dict[str, Any], operation: str
    ) -> Any:
        last_transport_error: Optional[httpx.HTTPError] = None
        for index, base_url in enumerate(self.base_urls):
            try:
                response = await self.client.post(f"{base_url}{path}", json=json_payload)
            except httpx.HTTPError as exc:
                last_transport_error = exc
                if index < len(self.base_urls) - 1:
                    continue
                raise self._classify_transport_error(exc, operation) from exc

            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code == 404 and index < len(self.base_urls) - 1:
                continue
            return self._decode_json(response, operation)

        if last_transport_error is not None:
            raise self._classify_transport_error(last_transport_error, operation) from last_transport_error
        raise GrowChiefConfigurationError("GROWCHIEF_API_URL is not configured")

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
        workflows = await self._get_json("/workflows", operation="list workflows")
        return workflows if isinstance(workflows, list) else []

    async def _resolve_workflow_id(self, platform: str) -> str:
        mapped = self.workflow_map.get(platform.strip().lower())
        if mapped:
            return mapped

        workflows = [workflow for workflow in await self.list_workflows() if workflow.get("active") is not False]
        if len(workflows) == 1 and workflows[0].get("id"):
            return str(workflows[0]["id"])

        raise GrowChiefConfigurationError(
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
        try:
            await QuotaMonitorService.assert_within_budget(
                provider="growchief",
                estimated_usage={"requests": 1, "workflows": 1},
                operation=f"trigger_engagement:{platform}",
            )
        except QuotaExceededError as exc:
            raise GrowChiefServiceError(str(exc)) from exc

        workflow_id = await self._resolve_workflow_id(platform)
        payload = {"urls": [post_url]}

        try:
            raw = await self._post_json(
                f"/workflows/{workflow_id}",
                json_payload=payload,
                operation=f"trigger workflow {workflow_id}",
            )
            await self._record_usage(
                operation="trigger_engagement",
                usage={"requests": 1, "workflows": 1},
                metadata={"platform": platform},
            )
        except Exception as exc:
            await self._record_usage(
                operation="trigger_engagement",
                usage={"requests": 1},
                metadata={"platform": platform},
                error=exc,
            )
            raise

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
