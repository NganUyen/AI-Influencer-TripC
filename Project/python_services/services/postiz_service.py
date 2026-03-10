"""
Postiz Service Integration
Handles official OAuth-based publishing to social platforms
"""

import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from config.settings import settings

logger = logging.getLogger(__name__)


class PostizService:
    """
    Integration with Postiz for multi-platform content distribution
    Supports: Twitter, Facebook, LinkedIn, TikTok, YouTube
    """

    def __init__(self):
        self.base_url = settings.POSTIZ_API_URL
        self.api_key = settings.POSTIZ_API_KEY
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60.0,
        )

    async def publish(
        self,
        platform: str,
        content: str,
        media_urls: List[str] = None,
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

            result = response.json()
            logger.info(f"Successfully published to {platform}: {result.get('id')}")
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
