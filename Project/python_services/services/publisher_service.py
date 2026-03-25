"""
Customer-aware publishing abstraction.
"""

from __future__ import annotations

from typing import Any, Dict, List

from config.settings import settings
from services.account_connection_service import AccountConnectionService
from services.errors import PostizConfigurationError
from services.postiz_service import PostizService


class PublisherService:
    POSTIZ_PLATFORMS = {"twitter", "facebook", "linkedin", "youtube"}

    def __init__(self) -> None:
        self.postiz_service = PostizService()

    async def publish(self, post_config: Dict[str, Any]) -> Dict[str, Any]:
        platform = str(post_config["platform"]).strip().lower()
        user_id = str(post_config.get("user_id") or "").strip()
        media_urls = [item["storage_url"] for item in post_config.get("media", []) if item.get("storage_url")]

        connected_account = None
        if user_id:
            connected_account = await AccountConnectionService.get_connected_account(
                user_id=user_id,
                platform=platform,
            )

        if connected_account and settings.CUSTOMER_POSTIZ_FALLBACK_ENABLED:
            result = await self.postiz_service.publish(
                platform=platform,
                content=post_config["content"],
                media_urls=media_urls,
                scheduled_time=post_config.get("scheduled_time"),
            )
            result["method"] = "customer_postiz_fallback"
            result["connected_account_id"] = str(connected_account["id"])
            return result

        if platform in self.POSTIZ_PLATFORMS:
            result = await self.postiz_service.publish(
                platform=platform,
                content=post_config["content"],
                media_urls=media_urls,
                scheduled_time=post_config.get("scheduled_time"),
            )
            result["method"] = "postiz_oauth"
            return result

        raise PostizConfigurationError(
            f"No supported publisher strategy is configured for platform '{platform}'."
        )

    async def close(self) -> None:
        await self.postiz_service.close()
