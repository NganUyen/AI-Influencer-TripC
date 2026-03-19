"""
Postiz Service Integration
Handles official OAuth-based publishing to social platforms
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from config.settings import settings

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


class PostizService:
    """
    Integration with Postiz for multi-platform content distribution
    Supports: Twitter, Facebook, LinkedIn, TikTok, YouTube
    """

    def __init__(self):
        self.base_url = settings.POSTIZ_API_URL
        self.api_key = settings.POSTIZ_API_KEY
        if not self.base_url:
            raise ValueError("POSTIZ_API_URL is not configured")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=60.0,
        )

    @staticmethod
    def _normalize_publish_response(
        raw_result: Dict[str, Any], scheduled_time: Optional[str] = None
    ) -> Dict[str, Any]:
        provider_post_id = (
            raw_result.get("id")
            or raw_result.get("provider_post_id")
            or raw_result.get("post_id")
            or raw_result.get("platform_post_id")
        )
        platform_post_id = (
            raw_result.get("post_id")
            or raw_result.get("platform_post_id")
            or provider_post_id
        )
        post_url = (
            raw_result.get("post_url")
            or raw_result.get("url")
            or raw_result.get("permalink")
        )
        status = raw_result.get("status") or ("scheduled" if scheduled_time else "published")

        return {
            "provider_post_id": (
                str(provider_post_id) if provider_post_id is not None else None
            ),
            "platform_post_id": (
                str(platform_post_id) if platform_post_id is not None else None
            ),
            "post_url": post_url,
            "status": status,
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
            data.get("provider_post_id"),
            payload.get("id"),
            payload.get("provider_post_id"),
            data.get("post_id"),
            payload.get("post_id"),
        )
        platform_post_id = _coalesce(
            data.get("post_id"),
            payload.get("post_id"),
            data.get("platform_post_id"),
            payload.get("platform_post_id"),
            provider_post_id,
        )

        return {
            "provider": "postiz",
            "event_type": str(event_type) if event_type is not None else None,
            "status": _canonical_post_status(raw_status),
            "provider_status": str(raw_status) if raw_status is not None else None,
            "provider_post_id": (
                str(provider_post_id) if provider_post_id is not None else None
            ),
            "platform_post_id": (
                str(platform_post_id) if platform_post_id is not None else None
            ),
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

    async def publish(
        self,
        platform: str,
        content: str,
        media_urls: Optional[List[str]] = None,
        scheduled_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish content to a platform via Postiz

        Args:
            platform: Target platform (twitter, facebook, linkedin, tiktok, youtube)
            content: Post content/caption
            media_urls: List of media URLs to attach
            scheduled_time: Optional schedule time (ISO format)
        """
        logger.info(f"Publishing to {platform} via Postiz")

        payload = {
            "platform": platform,
            "content": content,
            "media": media_urls or [],
            "status": "scheduled" if scheduled_time else "published",
        }

        if scheduled_time:
            payload["scheduled_at"] = scheduled_time

        try:
            response = await self.client.post("/api/posts", json=payload)
            response.raise_for_status()

            raw_result = response.json()
            result = self._normalize_publish_response(raw_result, scheduled_time)
            logger.info(
                "Successfully published to %s via Postiz: %s",
                platform,
                result.get("provider_post_id") or result.get("platform_post_id"),
            )
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to publish to {platform}: {str(e)}")
            raise

    async def get_post_status(self, post_id: str) -> Dict[str, Any]:
        """Get status of a published post"""
        response = await self.client.get(f"/api/posts/{post_id}")
        response.raise_for_status()
        return response.json()

    async def delete_post(self, post_id: str) -> Dict[str, Any]:
        """Delete a scheduled or published post"""
        response = await self.client.delete(f"/api/posts/{post_id}")
        response.raise_for_status()
        return response.json()

    async def get_analytics(self, post_id: str) -> Dict[str, Any]:
        """Get engagement analytics for a post"""
        response = await self.client.get(f"/api/posts/{post_id}/analytics")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
