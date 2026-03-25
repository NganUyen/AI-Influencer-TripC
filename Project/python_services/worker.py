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
    ShortVideoWorkflow,
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
    generate_and_send_script_for_approval,
    wait_for_script_approval,
    send_preview_to_telegram,
    wait_for_publish_decision,
    create_talking_head_video,
    generate_scene_images,
    build_split_screen_video,
    generate_daily_story,
    send_story_for_approval,
)
from config.settings import settings
from services.content_persistence_service import ContentPersistenceService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

workflows = [
    WeeklyMarketingWorkflow,
    PostPublishingWorkflow,
    EngagementSyndicateWorkflow,
    DailyStoryWorkflow,
    ShortVideoWorkflow,
]

activities = [
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
    generate_and_send_script_for_approval,
    wait_for_script_approval,
    send_preview_to_telegram,
    wait_for_publish_decision,
    create_talking_head_video,
    generate_scene_images,
    build_split_screen_video,
    generate_daily_story,
    send_story_for_approval,
]


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
        workflows=workflows,
        activities=activities,
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
