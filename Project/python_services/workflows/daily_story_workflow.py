from __future__ import annotations
"""
Daily Story Workflow
=====================
Temporal workflow that runs every morning, generates a travel story via Gemini,
sends it to all registered Telegram subscribers for approval, then publishes
to the chosen platform when a button is tapped.

Cron: "0 8 * * *"  → fires at 08:00 server time every day.

Approval lifecycle:
    1. generate_daily_story  → StoryDraft dict
    2. send_story_for_approval → sends Telegram message with 3 buttons
    3. wait_condition         → pause until telegram_webhook signals us
    4. Route decision:
         post_tiktok  → publish_to_platforms(platform="tiktok")
         post_shorts  → publish_to_platforms(platform="youtube")
         skip         → exit cleanly (no publish)

Timeout: if nobody taps within 23 h the workflow logs a skip and exits.
This prevents zombie workflows when subscribers ignore the message.

Signal contract:
    signal name : "story_decision"
    payload     : {"action": "post_tiktok" | "post_shorts" | "skip",
                   "chat_id": int}
"""

"""
Run in order on VPS
# 1. Register bot webhook (once)
python scripts/register_telegram_webhook.py
# 2. Start the server
./run-backend.cmd  (or uvicorn main:app)
# 3. Start the Temporal worker (separate terminal)
python worker.py
# 4. Register the cron (ONCE — it runs daily forever after)
python scripts/start_daily_story_cron.py
# Optional: custom topic
python scripts/start_daily_story_cron.py --topic "Ha Giang Loop" --language Vietnamese

"""


from datetime import timedelta, timezone, datetime
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.story_activities import (
        generate_daily_story,
        send_story_for_approval,
    )
    from activities.distribution_activities import publish_to_platforms


# ─── Platform publish config ──────────────────────────────────────────────────

_PLATFORM_PUBLISH_CONFIG: Dict[str, Dict[str, Any]] = {
    "post_tiktok": {
        "platform": "tiktok",
        "format": "vertical_short",
    },
    "post_shorts": {
        "platform": "youtube",
        "format": "shorts",
    },
}

# ─── Workflow ──────────────────────────────────────────────────────────────────

@workflow.defn
class DailyStoryWorkflow:
    """
    Runs daily via Temporal cron. Generates → sends for approval → publishes.

    To start with cron (from API or start script):
        client.start_workflow(
            DailyStoryWorkflow.run,
            args=[story_config],
            id="daily-story-workflow",
            task_queue="ai-influencer-tasks",
            cron_schedule="0 8 * * *",
        )
    """

    def __init__(self) -> None:
        self._decision: Optional[Dict[str, Any]] = None
        self._decision_received: bool = False

    @workflow.signal
    async def story_decision(self, payload: Dict[str, Any]) -> None:
        """
        Received from telegram_webhook when a subscriber taps a button.

        payload = {"action": "post_tiktok"|"post_shorts"|"skip", "chat_id": int}
        """
        workflow.logger.info(
            "story_decision signal received: action=%s from chat_id=%s",
            payload.get("action"),
            payload.get("chat_id"),
        )
        self._decision = payload
        self._decision_received = True

    @workflow.run
    async def run(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main cron run. config is passed when registering the cron workflow.

        config keys:
            topic       str  — destination/theme (e.g. "Hoi An Ancient Town")
            language    str  — content language (default: "Vietnamese")
            voice_style str  — persona tone
            audience    str  — target market
            model       str  — Gemini model
        """
        # Attach today's date so Gemini includes it in the story
        today = workflow.now().astimezone(timezone.utc).strftime("%Y-%m-%d")
        config = {**config, "date": today}

        workflow.logger.info("DailyStoryWorkflow started for date=%s topic=%s",
                             today, config.get("topic"))

        # ── Step 1: Generate story ────────────────────────────────────────────
        story: Dict[str, Any] = await workflow.execute_activity(
            generate_daily_story,
            args=[config],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                backoff_coefficient=2.0,
            ),
        )
        workflow.logger.info("Story generated: %s", story.get("title"))

        # ── Step 2: Send to all subscribers ──────────────────────────────────
        send_result: Dict[str, Any] = await workflow.execute_activity(
            send_story_for_approval,
            args=[{
                "story": story,
                "workflow_id": workflow.info().workflow_id,
            }],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        workflow.logger.info("Story sent to %d subscribers", send_result.get("count", 0))

        if send_result.get("count", 0) == 0:
            workflow.logger.warning("No subscribers — skipping approval wait")
            return {"status": "no_subscribers", "date": today}

        # ── Step 3: Wait for a button tap (max 23 h) ─────────────────────────
        try:
            await workflow.wait_condition(
                lambda: self._decision_received,
                timeout=timedelta(hours=23),
            )
        except TimeoutError:
            workflow.logger.info("No decision received within 23h — auto-skip")
            return {"status": "timeout_skipped", "story": story["title"], "date": today}

        action: str = self._decision.get("action", "skip")
        chat_id: Optional[int] = self._decision.get("chat_id")
        workflow.logger.info("Decision: %s by chat_id=%s", action, chat_id)

        # ── Step 4: Route action ──────────────────────────────────────────────
        if action == "skip":
            workflow.logger.info("Story skipped by subscriber")
            return {"status": "skipped", "story": story["title"], "date": today}

        publish_config = _PLATFORM_PUBLISH_CONFIG.get(action)
        if not publish_config:
            workflow.logger.warning("Unknown action '%s' — treating as skip", action)
            return {"status": "unknown_action", "action": action, "date": today}

        # Build publish payload for distribution_activities.publish_to_platforms
        publish_payload = {
            **publish_config,
            "content": story.get("body", ""),
            "title": story.get("title", ""),
            "hashtags": story.get("hashtags", []),
            "visual_prompt": story.get("visual_prompt", ""),
            "story_date": today,
            "workflow_id": workflow.info().workflow_id,
        }

        publish_result: Dict[str, Any] = await workflow.execute_activity(
            publish_to_platforms,
            args=[publish_payload],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=30),
                backoff_coefficient=2.0,
            ),
        )

        workflow.logger.info(
            "Story published to %s: %s",
            publish_config["platform"],
            publish_result.get("status"),
        )
        return {
            "status": "published",
            "platform": publish_config["platform"],
            "story": story["title"],
            "date": today,
            "publish_result": publish_result,
        }
