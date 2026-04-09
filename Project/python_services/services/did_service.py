"""
D-ID API service for talking-head clip generation.

Implements the V3 Pro Avatar quickstart flow:
- POST /clips
- GET /clips/{id} until status=done
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from config.settings import settings
from services.errors import DIDTimeoutError
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

DID_BASE_URL = "https://api.d-id.com"
_DID_SUCCESS_STATUSES = {"done", "completed", "complete", "success", "succeeded"}
_DID_FAILURE_STATUSES = {"error", "failed", "rejected", "canceled", "cancelled"}


class DIDService:
    """Service for D-ID clips-based fallback talking-head generation."""

    def __init__(self) -> None:
        self.api_key = settings.DID_API_KEY
        if not self.api_key:
            raise ValueError("DID_API_KEY is not configured in the environment")
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _record_usage(
        self,
        *,
        operation: str,
        usage: dict,
        metadata: dict | None = None,
        error: Exception | None = None,
        user_id: Optional[str] = None,
    ) -> None:
        quota_metadata = {
            "service": "did_service",
            "operation": operation,
            "status": "error" if error else "success",
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="did",
            usage=usage,
            metadata=quota_metadata,
            user_id=user_id,
        )

    async def create_clip(
        self,
        *,
        presenter_id: str,
        script_text: str,
        user_id: Optional[str] = None,
        result_format: str = "mp4",
    ) -> dict:
        normalized_script = str(script_text or "").strip()
        if not presenter_id:
            raise ValueError("presenter_id is required for D-ID clip generation")
        if not normalized_script:
            raise ValueError("script_text is required for D-ID clip generation")

        await QuotaMonitorService.assert_within_budget(
            provider="did",
            estimated_usage={"requests": 1, "clips": 1},
            operation="create_clip",
            user_id=user_id,
        )

        payload = {
            "presenter_id": presenter_id,
            "script": {
                "type": "text",
                "input": normalized_script,
            },
            "config": {
                "result_format": result_format,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                resp = await client.post(
                    f"{DID_BASE_URL}/clips",
                    headers=self.headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="create_clip",
                    usage={"requests": 1, "clips": 1},
                    metadata={"presenter_id": presenter_id},
                    error=exc,
                    user_id=user_id,
                )
                raise

        clip_id = self._extract_clip_id(data)
        await self._record_usage(
            operation="create_clip",
            usage={"requests": 1, "clips": 1},
            metadata={"presenter_id": presenter_id, "clip_id": clip_id},
            user_id=user_id,
        )
        return {"clip_id": clip_id, "raw": data}

    async def get_clip_status(
        self,
        clip_id: str,
        *,
        user_id: Optional[str] = None,
    ) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{DID_BASE_URL}/clips/{clip_id}",
                    headers=self.headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                await self._record_usage(
                    operation="get_clip_status",
                    usage={"requests": 1, "status_checks": 1},
                    metadata={"clip_id": clip_id},
                    error=exc,
                    user_id=user_id,
                )
                raise

        await self._record_usage(
            operation="get_clip_status",
            usage={"requests": 1, "status_checks": 1},
            metadata={
                "clip_id": clip_id,
                "provider_status": self._normalize_status(
                    data.get("status") or data.get("data", {}).get("status")
                ),
            },
            user_id=user_id,
        )
        return data

    async def poll_clip_status(
        self,
        clip_id: str,
        *,
        timeout_seconds: int = 600,
        poll_interval: int = 10,
        user_id: Optional[str] = None,
    ) -> str:
        elapsed = 0
        last_payload: dict | None = None

        while elapsed < timeout_seconds:
            last_payload = await self.get_clip_status(clip_id, user_id=user_id)
            status = self._normalize_status(
                last_payload.get("status") or last_payload.get("data", {}).get("status")
            )

            logger.info("D-ID clip %s status: %s (%ss)", clip_id, status or "unknown", elapsed)

            if status in _DID_SUCCESS_STATUSES:
                result_url = self._extract_result_url(last_payload)
                if result_url:
                    return result_url
                raise ValueError(f"D-ID clip {clip_id} completed without result_url")

            if status in _DID_FAILURE_STATUSES:
                raise ValueError(
                    f"D-ID clip failed (clip_id={clip_id}, status={status or 'unknown'})"
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise DIDTimeoutError(f"D-ID clip polling timed out for clip_id={clip_id}")

    @staticmethod
    def _normalize_status(value: object) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _extract_clip_id(payload: dict) -> str:
        clip_id = payload.get("id") or payload.get("data", {}).get("id")
        if not clip_id:
            raise ValueError(f"D-ID did not return clip id: {payload}")
        return str(clip_id)

    @staticmethod
    def _extract_result_url(payload: dict) -> Optional[str]:
        url = payload.get("result_url") or payload.get("data", {}).get("result_url")
        if not url:
            return None
        return str(url).strip() or None
