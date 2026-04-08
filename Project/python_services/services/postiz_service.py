"""
Postiz service adapter for the current public API.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from config.settings import settings
from services.errors import (
    PostizAuthError,
    PostizConfigurationError,
    PostizRetryableError,
    PostizServiceError,
)

logger = logging.getLogger(__name__)


def _canonical_post_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    status_map = {
        "queued": "scheduled",
        "pending": "scheduled",
        "scheduled": "scheduled",
        "schedule_created": "scheduled",
        "draft": "scheduled",
        "published": "published",
        "live": "published",
        "posted": "published",
        "completed": "published",
        "success": "published",
        "failed": "failed",
        "error": "failed",
        "rejected": "failed",
        "canceled": "canceled",
        "cancelled": "canceled",
    }
    return status_map.get(normalized, normalized or None)


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _normalize_public_api_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    if base_url.endswith("/public/v1") or base_url.endswith("/api/public/v1"):
        return base_url
    return f"{base_url}/api/public/v1"


def _parse_json_map(raw: str | None) -> Dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ignoring invalid JSON map: %s", raw)
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key).strip().lower(): str(value).strip() for key, value in parsed.items() if str(value).strip()}


def _provider_identifier(platform: str) -> str:
    mapping = {
        "twitter": "x",
        "x": "x",
        "facebook": "facebook",
        "linkedin": "linkedin",
        "linkedin-page": "linkedin-page",
        "instagram": "instagram",
        "threads": "threads",
        "youtube": "youtube",
        "tiktok": "tiktok",
    }
    return mapping.get(platform.strip().lower(), platform.strip().lower())


def _truncate_title(value: str, default: str) -> str:
    title = value.strip() or default
    title = title.replace("\n", " ").strip()
    if len(title) < 2:
        return default
    return title[:100]


def _default_post_settings(platform: str, content: str) -> Dict[str, Any]:
    provider = _provider_identifier(platform)
    if provider == "x":
        return {
            "__type": "x",
            "who_can_reply_post": "everyone",
            "community": "",
        }
    if provider in {"linkedin", "linkedin-page", "facebook", "threads", "instagram"}:
        return {"__type": provider}
    if provider == "youtube":
        return {
            "__type": "youtube",
            "title": _truncate_title(content, "AI Influencer Video"),
            "type": "public",
            "selfDeclaredMadeForKids": "no",
            "tags": [],
        }
    if provider == "tiktok":
        return {
            "__type": "tiktok",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "duet": False,
            "stitch": False,
            "comment": True,
            "autoAddMusic": False,
            "brand_content_toggle": False,
            "brand_organic_toggle": True,
            "content_posting_method": "DIRECT_POST",
        }
    return {"__type": provider}


def _response_content_type(response: Any) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get("content-type") or headers.get("Content-Type") or "").lower()


def _response_preview(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text.strip()[:200]
    return ""


class PostizService:
    """
    Integration with the current Postiz public API.
    """

    def __init__(self):
        self.base_url = _normalize_public_api_base_url(settings.POSTIZ_API_URL or "")
        self.api_key = settings.POSTIZ_API_KEY
        if not self.base_url:
            raise ValueError("POSTIZ_API_URL is not configured")
        if not self.api_key:
            raise ValueError("POSTIZ_API_KEY is not configured")

        self.integration_map = _parse_json_map(os.getenv("POSTIZ_INTEGRATION_MAP"))
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
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
            "service": "postiz_service",
            "operation": operation,
            "status": "error" if error else "success",
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="postiz",
            usage=usage,
            metadata=quota_metadata,
        )

    @staticmethod
    def _raise_for_http_status(response: Any, operation: str) -> None:
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 400:
            return

        if status_code == 401:
            raise PostizAuthError(
                "Postiz API key was rejected or the Postiz admin bootstrap is incomplete."
            )
        if status_code == 429 or status_code >= 500:
            raise PostizRetryableError(
                f"Postiz {operation} failed with status {status_code}."
            )
        raise PostizServiceError(
            f"Postiz {operation} failed with status {status_code}."
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
                raise PostizRetryableError(
                    f"Postiz {operation} returned HTML instead of JSON."
                ) from exc
            raise PostizRetryableError(
                f"Postiz {operation} returned invalid JSON."
            ) from exc

    @staticmethod
    def _classify_transport_error(exc: httpx.HTTPError, operation: str) -> PostizServiceError:
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                PostizService._raise_for_http_status(response, operation)
            except PostizServiceError as provider_exc:
                return provider_exc
        return PostizRetryableError(f"Postiz {operation} request failed.")

    async def _get_json(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        operation: str,
    ) -> Any:
        try:
            response = await self.client.get(path, params=params)
        except httpx.HTTPError as exc:
            raise self._classify_transport_error(exc, operation) from exc
        return self._decode_json(response, operation)

    async def _post_json(
        self,
        path: str,
        *,
        json_payload: Dict[str, Any],
        operation: str,
    ) -> Any:
        try:
            response = await self.client.post(path, json=json_payload)
        except httpx.HTTPError as exc:
            raise self._classify_transport_error(exc, operation) from exc
        return self._decode_json(response, operation)

    async def _delete_json(self, path: str, *, operation: str) -> Any:
        try:
            response = await self.client.delete(path)
        except httpx.HTTPError as exc:
            raise self._classify_transport_error(exc, operation) from exc
        return self._decode_json(response, operation)

    @staticmethod
    def _normalize_publish_response(
        raw_result: Any,
        scheduled_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        first_item = raw_result[0] if isinstance(raw_result, list) and raw_result else raw_result
        if not isinstance(first_item, dict):
            first_item = {}

        provider_post_id = _coalesce(first_item.get("id"), first_item.get("postId"))
        platform_post_id = _coalesce(
            first_item.get("postId"),
            first_item.get("id"),
            provider_post_id,
        )

        return {
            "provider_post_id": str(provider_post_id) if provider_post_id is not None else None,
            "platform_post_id": str(platform_post_id) if platform_post_id is not None else None,
            "post_url": None,
            "status": "scheduled" if scheduled_time else "published",
            "raw": raw_result,
        }

    @staticmethod
    def normalize_webhook_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
        payload_metadata = (
            payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        )
        event_type = _coalesce(
            payload.get("event"),
            payload.get("type"),
            data.get("event"),
            data.get("type"),
            data.get("status"),
        )
        raw_status = _coalesce(data.get("status"), payload.get("status"), event_type)
        provider_post_id = _coalesce(
            data.get("id"),
            data.get("postId"),
            data.get("provider_post_id"),
            payload.get("id"),
            payload.get("postId"),
            payload.get("provider_post_id"),
            data.get("post_id"),
            payload.get("post_id"),
        )
        platform_post_id = _coalesce(
            data.get("post_id"),
            payload.get("post_id"),
            data.get("postId"),
            payload.get("postId"),
            data.get("platform_post_id"),
            payload.get("platform_post_id"),
            provider_post_id,
        )

        return {
            "provider": "postiz",
            "event_type": str(event_type) if event_type is not None else None,
            "status": _canonical_post_status(raw_status),
            "provider_status": str(raw_status) if raw_status is not None else None,
            "provider_post_id": str(provider_post_id) if provider_post_id is not None else None,
            "platform_post_id": str(platform_post_id) if platform_post_id is not None else None,
            "platform": _coalesce(data.get("platform"), payload.get("platform")),
            "post_url": _coalesce(
                data.get("post_url"),
                payload.get("post_url"),
                data.get("url"),
                payload.get("url"),
                data.get("permalink"),
                payload.get("permalink"),
            ),
            "scheduled_for": _coalesce(
                data.get("scheduled_at"),
                data.get("scheduled_for"),
                payload.get("scheduled_at"),
                payload.get("scheduled_for"),
            ),
            "published_at": _coalesce(
                data.get("published_at"),
                data.get("posted_at"),
                payload.get("published_at"),
                payload.get("posted_at"),
            ),
            "error": _coalesce(
                data.get("error"),
                payload.get("error"),
                data.get("error_message"),
                payload.get("error_message"),
            ),
            "content_id": _coalesce(
                metadata.get("content_id"),
                payload_metadata.get("content_id"),
                data.get("content_id"),
                payload.get("content_id"),
            ),
            "workflow_id": _coalesce(
                metadata.get("workflow_id"),
                payload_metadata.get("workflow_id"),
                data.get("workflow_id"),
                payload.get("workflow_id"),
            ),
            "logical_post_id": _coalesce(
                metadata.get("logical_post_id"),
                payload_metadata.get("logical_post_id"),
                data.get("logical_post_id"),
                payload.get("logical_post_id"),
            ),
            "raw": payload,
        }

    async def _resolve_integration_id(self, platform: str) -> str:
        platform_key = platform.strip().lower()
        mapped = self.integration_map.get(platform_key)
        if mapped:
            return mapped

        integrations = await self._get_json(
            "/integrations",
            operation=f"list integrations for {platform_key}",
        )
        provider = _provider_identifier(platform_key)

        for integration in integrations:
            if not isinstance(integration, dict):
                continue
            if integration.get("disabled"):
                continue
            if str(integration.get("identifier") or "").strip().lower() == provider:
                integration_id = integration.get("id")
                if integration_id:
                    return str(integration_id)

        raise PostizConfigurationError(
            f"No active Postiz integration found for platform '{platform_key}'. "
            "Set POSTIZ_INTEGRATION_MAP to override the automatic lookup."
        )

    async def _upload_media(self, media_urls: List[str]) -> List[Dict[str, str]]:
        uploaded: List[Dict[str, str]] = []
        for media_url in media_urls:
            item = await self._post_json(
                "/upload-from-url",
                json_payload={"url": media_url},
                operation="upload media",
            )
            uploaded.append(
                {
                    "id": str(item["id"]),
                    "path": str(item["path"]),
                }
            )
        return uploaded

    async def publish(
        self,
        platform: str,
        content: str,
        media_urls: Optional[List[str]] = None,
        scheduled_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info("Publishing to %s via Postiz public API", platform)

        integration_id = await self._resolve_integration_id(platform)
        uploaded_media = await self._upload_media(media_urls or [])
        settings_payload = _default_post_settings(platform, content)

        payload = {
            "type": "schedule" if scheduled_time else "now",
            "date": scheduled_time or datetime.now(timezone.utc).isoformat(),
            "shortLink": False,
            "tags": [],
            "posts": [
                {
                    "integration": {"id": integration_id},
                    "value": [
                        {
                            "content": content,
                            "image": uploaded_media,
                        }
                    ],
                    "settings": settings_payload,
                }
            ],
        }

        try:
            raw_result = await self._post_json(
                "/posts",
                json_payload=payload,
                operation=f"publish post for {platform}",
            )
            await self._record_usage(
                operation="publish",
                usage={"requests": 1, "posts": 1},
                metadata={"platform": platform},
            )
        except Exception as exc:
            await self._record_usage(
                operation="publish",
                usage={"requests": 1},
                metadata={"platform": platform},
                error=exc,
            )
            raise

        result = self._normalize_publish_response(raw_result, scheduled_time)
        logger.info(
            "Successfully published to %s via Postiz: %s",
            platform,
            result.get("provider_post_id") or result.get("platform_post_id"),
        )
        return result

    async def get_post_status(self, post_id: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        payload = await self._get_json(
            "/posts",
            params={
                "startDate": (now - timedelta(days=365)).date().isoformat(),
                "endDate": (now + timedelta(days=365)).date().isoformat(),
            },
            operation=f"fetch post status for {post_id}",
        )
        posts = payload.get("posts") if isinstance(payload, dict) else payload
        if not isinstance(posts, list):
            posts = []

        for item in posts:
            if not isinstance(item, dict):
                continue
            if str(item.get("id")) != str(post_id):
                continue
            return {
                "provider_post_id": str(item.get("id")),
                "platform_post_id": str(item.get("id")),
                "post_url": _coalesce(
                    item.get("url"),
                    item.get("releaseURL"),
                    item.get("permalink"),
                ),
                "status": _canonical_post_status(item.get("state") or item.get("status")),
                "raw": item,
            }

        raise PostizConfigurationError(f"Postiz post '{post_id}' was not found")

    async def delete_post(self, post_id: str) -> Dict[str, Any]:
        payload = await self._delete_json(
            f"/posts/{post_id}",
            operation=f"delete post {post_id}",
        )
        return payload if isinstance(payload, dict) else {"raw": payload}

    async def get_analytics(self, post_id: str) -> Dict[str, Any]:
        metrics = await self._get_json(
            f"/analytics/post/{post_id}",
            params={"date": "30"},
            operation=f"fetch analytics for {post_id}",
        )
        return {"metrics": metrics}

    async def close(self):
        await self.client.aclose()
