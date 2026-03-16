"""
GrowChief Service Integration
Manages the engagement syndicate and stealth account network
"""

import httpx
import logging
from typing import Dict, Any, List
from config.settings import settings

logger = logging.getLogger(__name__)


class GrowChiefService:
    """
    Integration with GrowChief for coordinated engagement operations
    Manages multiple stealth accounts with proxies and scheduled interactions
    """

    def __init__(self):
        self.base_url = settings.GROWCHIEF_API_URL
        self.api_key = settings.GROWCHIEF_API_KEY
        if not self.base_url:
            raise ValueError("GROWCHIEF_API_URL is not configured")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=120.0,
        )

    async def trigger_engagement(
        self,
        post_url: str,
        platform: str,
        engagement_type: List[str],
        account_count: int = 5,
        delay_minutes: int = 30,
    ) -> Dict[str, Any]:
        """
        Trigger coordinated engagement from stealth accounts

        Args:
            post_url: URL of the post to engage with
            platform: Social platform (twitter, instagram, etc.)
            engagement_type: Types of engagement (like, comment, share, view)
            account_count: Number of stealth accounts to use
            delay_minutes: Delay between engagements (for natural pacing)
        """
        logger.info(f"Triggering engagement syndicate for {post_url}")

        payload = {
            "post_url": post_url,
            "platform": platform,
            "engagement_types": engagement_type,
            "account_count": account_count,
            "delay_between_actions": delay_minutes,
            "randomize_timing": True,
            "use_proxies": True,
        }

        try:
            response = await self.client.post("/api/engagements/trigger", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Engagement syndicate triggered: {result.get('job_id')}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to trigger engagement: {str(e)}")
            raise

    async def get_engagement_metrics(
        self, platform: str, post_id: str
    ) -> Dict[str, Any]:
        """
        Get current engagement metrics for a post

        Returns metrics like likes, comments, shares, views
        """
        logger.info(f"Fetching engagement metrics for {post_id}")

        try:
            response = await self.client.get(
                f"/api/analytics/engagement",
                params={"platform": platform, "post_id": post_id},
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch metrics: {str(e)}")
            raise

    async def create_stealth_account(
        self, platform: str, persona_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new stealth account with unique identity

        Args:
            platform: Target platform
            persona_config: Account persona (name, bio, profile pic, voice_id)
        """
        logger.info(f"Creating stealth account for {platform}")

        payload = {
            "platform": platform,
            "persona": persona_config,
            "proxy_enabled": True,
            "browser_engine": "camoufox",
        }

        try:
            response = await self.client.post("/api/accounts/create", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Stealth account created: {result.get('account_id')}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to create stealth account: {str(e)}")
            raise

    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Get status of a stealth account"""
        response = await self.client.get(f"/api/accounts/{account_id}/status")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
