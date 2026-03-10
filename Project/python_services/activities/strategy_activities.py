"""
Strategy Activities - Content Planning and Generation
Powered by OpenClaw for intelligent content strategy
"""

from temporalio import activity
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

from services.openclaw_service import OpenClawService
from services.ai_service import AIService

logger = logging.getLogger(__name__)


@activity.defn
async def generate_weekly_strategy(
    user_id: str, brand_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a 7-day content strategy using OpenClaw's AI capabilities

    Returns a structured JSON with daily content plans including:
    - Content themes
    - Platform-specific variations
    - Media requirements (image/video/audio)
    - Posting times
    """
    logger.info(f"Generating weekly strategy for user: {user_id}")

    openclaw = OpenClawService()
    ai_service = AIService()

    # Get brand voice and preferences
    brand_voice = brand_config.get("voice", "professional and engaging")
    target_platforms = brand_config.get(
        "platforms", ["twitter", "linkedin", "instagram"]
    )
    content_pillars = brand_config.get("content_pillars", [])

    # Use OpenClaw to generate strategy
    strategy_prompt = f"""
    Create a comprehensive 7-day content marketing strategy for:
    
    Brand Voice: {brand_voice}
    Target Platforms: {target_platforms}
    Content Pillars: {content_pillars}
    
    Generate a structured plan with:
    - Daily themes aligned with content pillars
    - Platform-specific content variations
    - Optimal posting times for each platform
    - Media type requirements (image, video, carousel, etc.)
    - Engagement hooks and CTAs
    
    Return as JSON structure.
    """

    strategy = await openclaw.execute_task(
        task_type="content_strategy", prompt=strategy_prompt, user_id=user_id
    )

    return {
        "user_id": user_id,
        "generated_at": datetime.utcnow().isoformat(),
        "strategy": strategy,
        "platforms": target_platforms,
        "brand_config": brand_config,
    }


@activity.defn
async def generate_media_prompts(strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert content strategy into specific media generation prompts

    Returns list of prompts for fal.ai (images/videos) and PlayHT (audio)
    """
    logger.info("Generating media prompts from strategy")

    ai_service = AIService()
    prompts = []

    daily_content = strategy.get("strategy", {}).get("daily_content", [])

    for day_idx, day_content in enumerate(daily_content):
        media_requirements = day_content.get("media", [])

        for media in media_requirements:
            media_type = media.get("type")

            if media_type in ["image", "video"]:
                # Generate prompt for fal.ai
                prompt = await ai_service.generate_visual_prompt(
                    content_description=day_content.get("theme"),
                    style=media.get("style", "modern"),
                    platform=media.get("platform"),
                )

                prompts.append(
                    {
                        "type": media_type,
                        "service": "fal_ai",
                        "prompt": prompt,
                        "day": day_idx + 1,
                        "platform": media.get("platform"),
                        "config": media.get("config", {}),
                    }
                )

            elif media_type == "audio":
                # Generate script for PlayHT
                script = await ai_service.generate_audio_script(
                    content=day_content.get("message"),
                    voice_persona=media.get("voice_persona", "professional"),
                )

                prompts.append(
                    {
                        "type": "audio",
                        "service": "playht",
                        "script": script,
                        "day": day_idx + 1,
                        "voice_id": media.get("voice_id"),
                        "config": media.get("config", {}),
                    }
                )

    logger.info(f"Generated {len(prompts)} media prompts")
    return prompts


@activity.defn
async def generate_daily_content(
    day_number: int, strategy: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate detailed content for a specific day
    """
    logger.info(f"Generating content for day {day_number}")

    ai_service = AIService()
    daily_strategy = strategy["strategy"]["daily_content"][day_number - 1]

    # Generate platform-specific copy
    content = await ai_service.generate_platform_copy(
        theme=daily_strategy.get("theme"),
        platforms=strategy.get("platforms"),
        brand_voice=strategy.get("brand_config", {}).get("voice"),
    )

    return {
        "day": day_number,
        "theme": daily_strategy.get("theme"),
        "content": content,
        "posting_time": daily_strategy.get("posting_time"),
    }
