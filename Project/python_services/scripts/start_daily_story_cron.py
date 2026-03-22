"""
start_daily_story_cron.py
===========================
One-time script: registers the DailyStoryWorkflow as a Temporal cron workflow.
Run this ONCE from the VPS after deploying. The workflow will then fire every
day at 08:00 server time (UTC by default — adjust cron_schedule if needed).

Usage:
    python scripts/start_daily_story_cron.py

    # With a custom topic override:
    python scripts/start_daily_story_cron.py --topic "Ha Long Bay" --language Vietnamese

To check current run state:
    python scripts/check_telegram_webhook.py   (bot side)
    # or open Temporal UI → Workflows → search "daily-story-workflow"

To cancel the cron:
    python scripts/start_daily_story_cron.py --cancel
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from temporalio.client import Client
from config.settings import settings
from workflows.daily_story_workflow import DailyStoryWorkflow

# ── Cron schedule ──────────────────────────────────────────────────────────────
# "0 8 * * *"  = every day at 08:00 server time (UTC)
# "0 1 * * *"  = every day at 08:00 Vietnam time (UTC+7)
# Adjust to match your server's timezone.
CRON_SCHEDULE = "0 1 * * *"   # 08:00 Vietnam time

WORKFLOW_ID = "daily-story-workflow"

# ── Default story config ───────────────────────────────────────────────────────
# The workflow picks a fresh `date` at runtime; topic/language are defaults.
DEFAULT_CONFIG = {
    "topic": "Vietnam travel discovery",
    "language": "Vietnamese",
    "voice_style": "warm, inspiring, and authentic",
    "audience": "young Vietnamese travellers aged 22-35",
    "model": "models/gemini-2.0-flash",
}


async def start_cron(config: dict, cancel: bool = False) -> None:
    client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
        namespace=settings.TEMPORAL_NAMESPACE,
    )

    if cancel:
        print(f"Cancelling workflow: {WORKFLOW_ID}")
        handle = client.get_workflow_handle(WORKFLOW_ID)
        try:
            await handle.cancel()
            print("Cron workflow cancelled.")
        except Exception as e:
            print(f"Could not cancel: {e}")
        return

    print(f"\nStarting DailyStoryWorkflow cron")
    print(f"  Workflow ID : {WORKFLOW_ID}")
    print(f"  Schedule    : {CRON_SCHEDULE}  (08:00 Vietnam time)")
    print(f"  Task queue  : {settings.TEMPORAL_TASK_QUEUE}")
    print(f"  Config      : {config}")

    try:
        handle = await client.start_workflow(
            DailyStoryWorkflow.run,
            args=[config],
            id=WORKFLOW_ID,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            cron_schedule=CRON_SCHEDULE,
        )
        print(f"\nCron workflow started. Run ID: {handle.result_run_id}")
        print("It will fire every day at 08:00 Vietnam time.")
        print(f"\nCheck status: Temporal UI → Workflows → {WORKFLOW_ID}")
    except Exception as e:
        # If the workflow already exists with the same ID, Temporal returns an error.
        # To update the schedule, cancel first then re-run this script.
        print(f"\nError starting workflow: {e}")
        print("If the cron is already running, cancel it first:")
        print(f"  python scripts/start_daily_story_cron.py --cancel")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start or cancel the daily story cron")
    parser.add_argument("--topic", default=DEFAULT_CONFIG["topic"])
    parser.add_argument("--language", default=DEFAULT_CONFIG["language"])
    parser.add_argument("--cancel", action="store_true", help="Cancel the running cron")
    args = parser.parse_args()

    config = {**DEFAULT_CONFIG, "topic": args.topic, "language": args.language}
    asyncio.run(start_cron(config, cancel=args.cancel))
