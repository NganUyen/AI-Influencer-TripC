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
    DailyStoryWorkflow,
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
    generate_daily_story,
    send_story_for_approval,
)
from config.settings import settings
from services.content_persistence_service import ContentPersistenceService

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
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[
            WeeklyMarketingWorkflow,
            PostPublishingWorkflow,
            EngagementSyndicateWorkflow,
            DailyStoryWorkflow,
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
            generate_daily_story,
            send_story_for_approval,
        ],
        max_concurrent_activity_task_polls=settings.WORKER_CONCURRENCY,
        max_concurrent_workflow_task_polls=settings.WORKER_CONCURRENCY,
    )

    logger.info("Worker started successfully. Processing tasks...")

    # Run worker
    try:
        await worker.run()
    finally:
        await ContentPersistenceService.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
