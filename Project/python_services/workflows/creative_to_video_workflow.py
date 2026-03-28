from typing import Dict, Any
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from services.creative_director_service import CreativeDirectorService
    from activities.approval_activities import send_preview_to_telegram

@workflow.defn
class CreativeToVideoWorkflow:
    """
    End-to-End pipeline that accepts a minimal idea (e.g. from Telegram),
    spins up the Creative Director to generate a Concept and BeatSheet,
    and then invokes the ShortVideoWorkflow entirely automatically.
    """

    @workflow.run
    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        idea = payload.get("idea", "Check out this feature on our website!")
        reference_url = payload.get("reference_url", "https://example.com")
        persona_id = payload.get("persona_id", "default_persona")
        user_id = payload.get("user_id")
        owner_key = payload.get("owner_key")
        telegram_chat_id = payload.get("telegram_chat_id")

        # In a real setup, we'd run CreativeDirectorService as Activities.
        # But since we want to compose this here natively, we use an activity
        # to offload the LLM calls of CreativeDirectorService.
        
        # Step 1: Generate Package via Activity
        package_result = await workflow.execute_activity(
            "generate_creative_package_activity",
            args=[
                {
                    "idea": idea,
                    "reference_url": reference_url,
                    "persona_id": persona_id
                }
            ],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        app_package = package_result.get("approved_package")
        if not app_package:
            raise ValueError("Failed to generate approved package.")

        # Step 2: Kick off ShortVideoWorkflow as a Child Workflow
        child_workflow_id = f"video-build-{workflow.info().workflow_id}"
        
        child_payload = {
            "persona_id": persona_id,
            "topic": idea,
            "telegram_chat_id": telegram_chat_id,
            "user_id": user_id,
            "owner_key": owner_key,
            "approved_package": app_package
        }

        # Dynamically import to avoid circular dependencies
        from workflows.short_video_workflow import ShortVideoWorkflow

        video_result = await workflow.execute_child_workflow(
            ShortVideoWorkflow.run,
            args=[child_payload],
            id=child_workflow_id,
            execution_timeout=timedelta(minutes=30),
        )

        return {
            "status": "completed",
            "creative_package": app_package,
            "video_result": video_result
        }
