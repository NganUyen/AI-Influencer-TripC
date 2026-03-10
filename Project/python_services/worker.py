"""
Temporal Worker
Processes workflow activities
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from workflows import (
    WeeklyMarketingWorkflow,
    PostPublishingWorkflow,
    EngagementSyndicateWorkflow,
)
from activities import (
    generate_weekly_strategy,
    generate_media_prompts,
    generate_daily_content,
    generate_image,
    generate_video,
    generate_audio,
    upload_to_storage,
    schedule_posts,
    publish_to_platforms,
    track_engagement,
    send_telegram_approval_request,
    wait_for_approval,
)
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """
    Start Temporal worker
    """
    logger.info("Connecting to Temporal server...")

    # Connect to Temporal server
    client = await Client.connect(
        settings.TEMPORAL_ADDRESS, namespace=settings.TEMPORAL_NAMESPACE
    )

    logger.info("Starting Temporal worker...")

    # Create worker
    worker = Worker(
        client,
        task_queue="ai-influencer-tasks",
        workflows=[
            WeeklyMarketingWorkflow,
            PostPublishingWorkflow,
            EngagementSyndicateWorkflow,
        ],
        activities=[
            generate_weekly_strategy,
            generate_media_prompts,
            generate_daily_content,
            generate_image,
            generate_video,
            generate_audio,
            upload_to_storage,
            schedule_posts,
            publish_to_platforms,
            track_engagement,
            send_telegram_approval_request,
            wait_for_approval,
        ],
    )

    logger.info("Worker started successfully. Processing tasks...")

    # Run worker
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
