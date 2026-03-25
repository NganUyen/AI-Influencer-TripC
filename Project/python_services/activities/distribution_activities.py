"""
Distribution Activities
Handles publishing to platforms via Postiz and browser automation
"""

from temporalio.exceptions import ApplicationError
from temporalio import activity
from typing import Dict, Any, List
import logging
from datetime import datetime, timezone

from services.growchief_service import GrowChiefService
from services.browser_automation import BrowserAutomationService
from services.content_persistence_service import ContentPersistenceService
from config.settings import settings
from services.errors import SocialProviderError
from services.publisher_service import PublisherService

logger = logging.getLogger(__name__)


def _parse_scheduled_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        scheduled_time = value
    else:
        scheduled_time = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

    if scheduled_time.tzinfo is None:
        return scheduled_time.replace(tzinfo=timezone.utc)
    return scheduled_time.astimezone(timezone.utc)


def _get_postiz_scheduled_time(post_config: Dict[str, Any]) -> str | None:
    scheduled_time = _parse_scheduled_time(post_config.get("scheduled_time"))
    if not scheduled_time:
        return None
    if scheduled_time > datetime.now(timezone.utc):
        return scheduled_time.isoformat()
    return None


def _temporal_provider_error(
    context: str, exc: SocialProviderError
) -> ApplicationError:
    return ApplicationError(
        f"{context}: {str(exc)}",
        non_retryable=not getattr(exc, "retryable", False),
    )


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
                "theme": day_content.get("theme"),
                "media": platform_media,
                "hashtags": day_content.get("hashtags", []),
                "cta": day_content.get("cta", ""),
                "workflow_id": strategy.get("workflow_id"),
            }
            try:
                persisted = await ContentPersistenceService.persist_scheduled_post(
                    workflow_id=strategy.get("workflow_id", ""),
                    post_config=post,
                )
                post.update(persisted)
            except Exception as exc:
                logger.warning(
                    "Failed to persist scheduled post %s: %s",
                    post["id"],
                    exc,
                )
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
    publisher_service: PublisherService | None = None
    browser_service = BrowserAutomationService()

    results = {
        "post_id": post_config["id"],
        "logical_post_id": post_config["id"],
        "workflow_id": post_config.get("workflow_id"),
        "content_record_id": post_config.get("content_record_id"),
        "platform": platform,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    deferred_error: ApplicationError | None = None

    # Platforms supported by Postiz OAuth
    postiz_platforms = ["twitter", "facebook", "linkedin", "tiktok", "youtube"]

    try:
        if platform in postiz_platforms:
            # Use Postiz for official API distribution
            publisher_service = PublisherService()
            result = await publisher_service.publish(
                {
                    **post_config,
                    "scheduled_time": _get_postiz_scheduled_time(post_config),
                }
            )
            results.update(
                {
                    "status": result.get("status", "published"),
                    "platform_post_id": result.get("platform_post_id"),
                    "provider_post_id": result.get("provider_post_id"),
                    "post_url": result.get("post_url"),
                    "provider_status": result.get("status"),
                    "provider_response": result.get("raw"),
                    "method": result.get("method", "postiz_oauth"),
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
                    "status": result.get("status", "published"),
                    "platform_post_id": result.get("platform_post_id")
                    or result.get("post_id"),
                    "provider_post_id": result.get("provider_post_id")
                    or result.get("post_id"),
                    "post_url": result.get("post_url") or result.get("url"),
                    "provider_status": result.get("status", "published"),
                    "provider_response": result,
                    "method": "browser_automation",
                }
            )

        if results.get("status") != "published":
            results["published_at"] = None
    except SocialProviderError as exc:
        logger.error("Provider publish failure for %s: %s", platform, exc)
        results.update({"status": "failed", "error": str(exc), "published_at": None})
        deferred_error = _temporal_provider_error(
            f"Failed to publish to {platform}",
            exc,
        )
    except Exception as e:
        logger.error(f"Failed to publish to {platform}: {str(e)}")
        results.update({"status": "failed", "error": str(e), "published_at": None})
    finally:
        try:
            await ContentPersistenceService.update_publish_result(
                workflow_id=post_config.get("workflow_id"),
                post_config=post_config,
                publish_result=results,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist publish result for %s: %s",
                post_config["id"],
                exc,
            )
        if publisher_service is not None:
            await publisher_service.close()
        await browser_service.close()

    if deferred_error is not None:
        raise deferred_error
    return results


@activity.defn
async def track_engagement(post_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Monitor engagement metrics and trigger GrowChief syndicate
    """
    logger.info(f"Tracking engagement for post {post_data.get('post_id')}")

    growchief = GrowChiefService()
    engagement_result: Dict[str, Any] = {
        "metrics": {},
        "syndicate_triggered": False,
        "status": "pending",
    }
    deferred_error: ApplicationError | None = None

    # Get current engagement metrics
    try:
        metrics = await growchief.get_engagement_metrics(
            platform=post_data["platform"], post_id=post_data.get("platform_post_id")
        )
        engagement_result.update({"metrics": metrics, "status": "completed"})

        # Trigger coordinated engagement from stealth accounts
        if metrics.get("engagement_rate", 0) < settings.SYNDICATE_ENGAGEMENT_THRESHOLD:
            logger.info("Triggering engagement syndicate")
            action_types = ["like", "comment", "share"]

            post_url = (
                post_data.get("post_url")
                or f"{post_data['platform']}://{post_data.get('platform_post_id', '')}"
            )

            syndicate_result = await growchief.trigger_engagement(
                post_url=post_url,
                platform=post_data["platform"],
                engagement_type=action_types,
                account_count=settings.STEALTH_ACCOUNT_COUNT,
            )

            engagement_result.update(
                {
                    "syndicate_triggered": True,
                    "syndicate_result": syndicate_result,
                    "action_types": action_types,
                }
            )

        return engagement_result
    except SocialProviderError as exc:
        logger.error(
            "Provider engagement failure for post %s: %s",
            post_data.get("post_id"),
            exc,
        )
        engagement_result.update({"status": "failed", "error": str(exc)})
        deferred_error = _temporal_provider_error(
            f"Failed to track engagement for post {post_data.get('post_id')}",
            exc,
        )
    except Exception as exc:
        logger.error(
            "Failed to track engagement for post %s: %s",
            post_data.get("post_id"),
            exc,
        )
        engagement_result.update({"status": "failed", "error": str(exc)})
        return engagement_result
    finally:
        try:
            await ContentPersistenceService.record_engagement_result(
                workflow_id=post_data.get("workflow_id"),
                post_data=post_data,
                engagement_result=engagement_result,
            )
        except Exception as exc:
            logger.warning(
                "Failed to persist engagement result for %s: %s",
                post_data.get("post_id"),
                exc,
            )
        await growchief.close()

    if deferred_error is not None:
        raise deferred_error
