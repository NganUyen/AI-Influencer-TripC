"""
Distribution Activities
Handles publishing to platforms via Postiz and browser automation
"""

from temporalio import activity
from typing import Dict, Any, List
import logging
from datetime import datetime

from services.postiz_service import PostizService
from services.growchief_service import GrowChiefService
from services.browser_automation import BrowserAutomationService

logger = logging.getLogger(__name__)


@activity.defn
async def schedule_posts(
    strategy: Dict[str, Any], media_assets: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Create posting schedule from strategy and media assets
    """
    logger.info("Creating posting schedule")

    schedule = []
    daily_content = strategy.get("strategy", {}).get("daily_content", [])

    for day_idx, day_content in enumerate(daily_content):
        # Find matching media assets for this day
        day_media = [
            m for m in media_assets if m.get("metadata", {}).get("day") == day_idx + 1
        ]

        platforms = day_content.get("platforms", [])
        for platform in platforms:
            platform_media = [
                m
                for m in day_media
                if m.get("metadata", {}).get("platform") == platform
            ]

            post = {
                "id": f"{strategy['user_id']}_day{day_idx + 1}_{platform}",
                "user_id": strategy["user_id"],
                "day": day_idx + 1,
                "platform": platform,
                "scheduled_time": day_content.get("posting_time"),
                "content": day_content.get(
                    f"{platform}_copy", day_content.get("message")
                ),
                "media": platform_media,
                "hashtags": day_content.get("hashtags", []),
                "cta": day_content.get("cta", ""),
            }
            schedule.append(post)

    logger.info(f"Created schedule with {len(schedule)} posts")
    return schedule


@activity.defn
async def publish_to_platforms(post_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish content to social media platforms
    Uses Postiz for official OAuth APIs, browser automation for others
    """
    logger.info(f"Publishing post {post_config['id']} to {post_config['platform']}")

    platform = post_config["platform"]
    postiz_service = PostizService()
    browser_service = BrowserAutomationService()

    results = {
        "post_id": post_config["id"],
        "platform": platform,
        "published_at": datetime.utcnow().isoformat(),
        "status": "pending",
    }

    # Platforms supported by Postiz OAuth
    postiz_platforms = ["twitter", "facebook", "linkedin", "tiktok", "youtube"]

    try:
        if platform in postiz_platforms:
            # Use Postiz for official API distribution
            result = await postiz_service.publish(
                platform=platform,
                content=post_config["content"],
                media_urls=[m["storage_url"] for m in post_config.get("media", [])],
                scheduled_time=post_config.get("scheduled_time"),
            )
            results.update(
                {
                    "status": "published",
                    "platform_post_id": result.get("post_id"),
                    "method": "postiz_oauth",
                }
            )
        else:
            # Use browser automation for platforms without OAuth
            result = await browser_service.publish(
                platform=platform,
                content=post_config["content"],
                media_urls=[m["storage_url"] for m in post_config.get("media", [])],
                user_id=post_config["user_id"],
            )
            results.update(
                {
                    "status": "published",
                    "platform_post_id": result.get("post_id"),
                    "method": "browser_automation",
                }
            )

    except Exception as e:
        logger.error(f"Failed to publish to {platform}: {str(e)}")
        results.update({"status": "failed", "error": str(e)})

    return results


@activity.defn
async def track_engagement(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monitor engagement metrics and trigger GrowChief syndicate
    """
    logger.info(f"Tracking engagement for post {post_data.get('post_id')}")

    growchief = GrowChiefService()

    # Get current engagement metrics
    metrics = await growchief.get_engagement_metrics(
        platform=post_data["platform"], post_id=post_data.get("platform_post_id")
    )

    # Trigger coordinated engagement from stealth accounts
    if metrics.get("engagement_rate", 0) < 2.0:  # Low engagement threshold
        logger.info("Triggering engagement syndicate")

        syndicate_result = await growchief.trigger_engagement(
            post_url=post_data.get("post_url"),
            platform=post_data["platform"],
            engagement_type=["like", "comment", "share"],
            account_count=5,  # Use 5 stealth accounts
        )

        return {
            "metrics": metrics,
            "syndicate_triggered": True,
            "syndicate_result": syndicate_result,
        }

    return {"metrics": metrics, "syndicate_triggered": False}
