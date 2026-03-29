"""
Weekly Marketing Workflow - Core Orchestration
Manages the entire weekly content generation and distribution cycle
"""

from datetime import timedelta, datetime
from typing import List, Dict, Any
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, TimeoutError as TemporalTimeoutError

with workflow.unsafe.imports_passed_through():
    from activities.strategy_activities import (
        generate_weekly_strategy,
        generate_media_prompts,
        generate_daily_content,
    )
    from activities.media_activities import (
        generate_image,
        generate_video,
        generate_audio,
    )
    from activities.distribution_activities import (
        schedule_posts,
        publish_to_platforms,
        track_engagement,
    )
    from activities.approval_activities import (
        send_telegram_approval_request,
        wait_for_approval,
    )


@workflow.defn
class WeeklyMarketingWorkflow:
    """
    Main workflow that orchestrates the weekly marketing cycle:
    1. Generate strategic content plan
    2. Wait for human approval via Telegram
    3. Generate media assets (images, videos, audio)
    4. Schedule and distribute across platforms
    5. Monitor engagement and trigger syndicate actions
    """

    @workflow.run
    async def run(self, user_id: str, brand_config: Dict[str, Any]) -> Dict[str, Any]:
        workflow.logger.info(f"Starting weekly marketing workflow for user: {user_id}")
        self.approval_received = False
        self.approval_approved = False
        self.approval_feedback = ""
        self.current_step = "generating_strategy"
        self.workflow_status = "running"

        # Step 1: Generate weekly strategy using OpenClaw
        strategy = await workflow.execute_activity(
            generate_weekly_strategy,
            args=[user_id, brand_config],
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self.current_step = "waiting_approval"
        self.workflow_status = "waiting_approval"

        skip_internal_approval = bool(brand_config.get("skip_internal_approval"))
        if skip_internal_approval:
            workflow.logger.info("Skipping in-workflow approval because review already happened in the web app")
            self.approval_received = True
            self.approval_approved = True
            self.workflow_status = "running"
        else:
            # Step 2: Send strategy to Telegram for approval
            approval_request_id = await workflow.execute_activity(
                send_telegram_approval_request,
                args=[user_id, strategy],
                start_to_close_timeout=timedelta(minutes=2),
            )

            # Step 3: Wait for Telegram callback decision persisted by TelegramService
            workflow.logger.info(f"Waiting for approval on request: {approval_request_id}")
            try:
                approval_result = await workflow.execute_activity(
                    wait_for_approval,
                    args=[approval_request_id],
                    start_to_close_timeout=timedelta(days=8),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except ActivityError as exc:
                if not isinstance(exc.cause, (TemporalTimeoutError, TimeoutError)):
                    raise
                workflow.logger.warning("Approval timeout - canceling workflow")
                self.current_step = "approval_timed_out"
                self.workflow_status = "timed_out"
                return {
                    "status": "timed_out",
                    "message": "Approval not received within 7 days",
                }
            except (TemporalTimeoutError, TimeoutError):
                workflow.logger.warning("Approval timeout - canceling workflow")
                self.current_step = "approval_timed_out"
                self.workflow_status = "timed_out"
                return {
                    "status": "timed_out",
                    "message": "Approval not received within 7 days",
                }

            self.approval_received = True
            self.approval_approved = bool(approval_result.get("approved", False))
            self.approval_feedback = approval_result.get("feedback", "")

            if not self.approval_approved:
                workflow.logger.info("Strategy rejected by operator")
                self.current_step = "rejected"
                self.workflow_status = "rejected"
                return {
                    "status": "rejected",
                    "message": "Strategy was rejected",
                    "feedback": self.approval_feedback,
                }

        self.workflow_status = "running"
        self.current_step = "generating_media"

        # Step 4: Generate media prompts for each content piece
        media_prompts = await workflow.execute_activity(
            generate_media_prompts,
            args=[strategy],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 5: Generate media assets in parallel
        media_tasks = []
        media_retry_policy = RetryPolicy(maximum_attempts=3)
        for prompt in media_prompts:
            if prompt["type"] == "image":
                task = workflow.execute_activity(
                    generate_image,
                    args=[prompt],
                    start_to_close_timeout=timedelta(minutes=3),
                    retry_policy=media_retry_policy,
                )
            elif prompt["type"] == "video":
                task = workflow.execute_activity(
                    generate_video,
                    args=[prompt],
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=media_retry_policy,
                )
            elif prompt["type"] == "audio":
                task = workflow.execute_activity(
                    generate_audio,
                    args=[prompt],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=media_retry_policy,
                )
            media_tasks.append(task)

        # Temporal 1.5.1 activity handles are asyncio tasks already. Creating
        # them above starts the activities in parallel, so awaiting the handles
        # here preserves concurrency without relying on missing gather helpers.
        uploaded_assets = [await task for task in media_tasks]

        strategy["workflow_id"] = workflow.info().workflow_id

        # Step 6: Schedule posts across the week
        self.current_step = "scheduling_distribution"
        schedule = await workflow.execute_activity(
            schedule_posts,
            args=[strategy, uploaded_assets],
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Step 7: Execute publishing workflow for each scheduled post
        for post in schedule:
            await workflow.start_child_workflow(
                PostPublishingWorkflow.run,
                args=[post],
                id=f"{workflow.info().workflow_id}-publish-{post['id']}",
                task_queue="ai-influencer-tasks",
            )

        workflow.logger.info("Weekly marketing workflow completed successfully")
        self.current_step = "completed"
        self.workflow_status = "completed"
        return {
            "status": "success",
            "strategy": strategy,
            "media_count": len(uploaded_assets),
            "posts_scheduled": len(schedule),
        }

    @workflow.signal
    async def approve_strategy(self, approved: bool, feedback: str = ""):
        """Signal handler for strategy approval"""
        self.approval_received = True
        self.approval_approved = approved
        self.approval_feedback = feedback
        self.workflow_status = "running" if approved else "rejected"

    @workflow.query
    def get_workflow_status(self) -> Dict[str, Any]:
        """Query handler to get current workflow status"""
        return {
            "status": getattr(self, "workflow_status", "running"),
            "current_step": getattr(self, "current_step", "starting"),
            "approval_received": getattr(self, "approval_received", False),
            "approval_approved": getattr(self, "approval_approved", False),
            "approval_feedback": getattr(self, "approval_feedback", ""),
            "workflow_id": workflow.info().workflow_id,
        }


@workflow.defn
class PostPublishingWorkflow:
    """
    Child workflow for publishing individual posts
    Handles distribution to multiple platforms and engagement tracking
    """

    @workflow.run
    async def run(self, post_config: Dict[str, Any]) -> Dict[str, Any]:
        workflow.logger.info(f"Publishing post: {post_config.get('id')}")

        # Wait until scheduled time
        scheduled_time = post_config.get("scheduled_time")
        if isinstance(scheduled_time, str):
            scheduled_time = datetime.fromisoformat(
                scheduled_time.replace("Z", "+00:00")
            )
        if isinstance(scheduled_time, datetime):
            await workflow.wait_condition(lambda: workflow.now() >= scheduled_time)

        # Publish to platforms (Postiz for official, browser automation for others)
        publish_results = await workflow.execute_activity(
            publish_to_platforms,
            args=[post_config],
            start_to_close_timeout=timedelta(minutes=10),
        )

        # Start engagement syndicate workflow
        await workflow.start_child_workflow(
            EngagementSyndicateWorkflow.run,
            args=[publish_results],
            id=f"{workflow.info().workflow_id}-engagement-{post_config.get('id')}",
            task_queue="ai-influencer-tasks",
        )

        return {"status": "published", "results": publish_results}


@workflow.defn
class EngagementSyndicateWorkflow:
    """
    Manages the coordinated engagement network
    Triggers stealth accounts to interact with published content
    """

    @workflow.run
    async def run(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        workflow.logger.info("Starting engagement syndicate actions")

        # Wait random delay before starting engagement (1-4 hours)
        await workflow.sleep(timedelta(hours=2))

        # Track engagement metrics
        engagement_results = await workflow.execute_activity(
            track_engagement,
            args=[post_data],
            start_to_close_timeout=timedelta(minutes=5),
        )

        return {"status": "completed", "engagement": engagement_results}
