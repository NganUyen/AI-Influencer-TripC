import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from temporalio.client import Client
from workflows.daily_story_workflow import DailyStoryWorkflow
from config.settings import settings

async def main():
    print("Connecting to Temporal...")

    client = await Client.connect(
        settings.TEMPORAL_ADDRESS,
        namespace=settings.TEMPORAL_NAMESPACE
    )

    # Customize these values
    config = {
        "topic": "Ha Giang Loop",           # Change this to whatever you want
        "language": "Vietnamese",
        "persona_id": "your-persona-id-here",   # ← VERY IMPORTANT: put a real persona_id from Supabase
        "date": datetime.now().strftime("%Y-%m-%d")
    }

    workflow_id = f"daily-story-test-{int(datetime.now().timestamp())}"

    print(f"🚀 Starting Daily Story Workflow")
    print(f"   Workflow ID : {workflow_id}")
    print(f"   Topic       : {config['topic']}")
    print(f"   Language    : {config['language']}")

    handle = await client.start_workflow(
        DailyStoryWorkflow.run,
        config,
        id=workflow_id,
        task_queue="ai-influencer-tasks",      # Make sure this matches your worker.py
    )

    print("✅ Workflow started successfully!")
    print("   Go to your Telegram bot/group and wait ~10-30 seconds...")
    print("   You should receive the story with 3 buttons.")

asyncio.run(main())