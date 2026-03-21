"""
Strategy Activities - Content Planning and Generation
Includes: weekly strategy, carousel, long-form SEO post.
"""

from temporalio import activity
from typing import Dict, Any, List
import logging
import json
from datetime import datetime, timedelta

from services.openclaw_service import OpenClawService
from services.ai_service import AIService
from services.script_service import ScriptService

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
                        "config": {
                            **media.get("config", {}),
                            "voice": media.get("voice_id"),
                        },
                        "metadata": {
                            "day": day_idx + 1,
                            "platform": media.get("platform"),
                        },
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


# ─── Phase F1: Carousel Strategy (8 slides) ──────────────────────────────────

@activity.defn
async def generate_carousel_strategy(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase F1: Generate 8-slide carousel for TikTok/Facebook.
    Each slide has image prompt + caption.

    Input config:
        app_name: str
        topic: str
        persona_config: dict (language_name, voice, skin_color)
        platform: str (tiktok, facebook, instagram)
        num_slides: int (default 8)
        model: str

    Returns:
        slides: List[{slide_num, image_prompt, caption, cta_overlay}]
        platform_caption: str   — main post caption
        hashtags: List[str]
    """
    app_name = config["app_name"]
    topic = config["topic"]
    persona = config.get("persona_config", {})
    platform = config.get("platform", "tiktok")
    num_slides = config.get("num_slides", 8)
    model = config.get("model", "models/gemini-2.0-flash")
    language = persona.get("language_name", "English")
    skin_color = persona.get("skin_color", "diverse")

    logger.info(f"Generating carousel | topic={topic} | slides={num_slides} | platform={platform}")

    CAROUSEL_PROMPT = f"""
You are a social media content creator. Generate a {num_slides}-slide carousel for {platform}.
App: {app_name} | Topic: {topic}
Persona language: {language} | Model skin tone in images: {skin_color}

Return ONLY valid JSON:
{{
  "slides": [
    {{
      "slide_num": 1,
      "image_prompt": "<fal.ai English prompt — specific, visual, {skin_color} person natural>",
      "caption": "<short slide text in {language}, max 10 words>",
      "cta_overlay": "<optional small overlay text, e.g. 'Swipe for tip 2'>"
    }}
  ],
  "platform_caption": "<main post caption in {language}, max 150 chars>",
  "hashtags": ["#tag1", "#tag2"]
}}

Slide 1: Hook/Problem. Slides 2-7: Features/Benefits. Slide 8: CTA to download {app_name}.
"""

    ai = AIService()
    raw = await ai.generate_text(prompt=CAROUSEL_PROMPT, model=model, temperature=0.7, max_tokens=3000)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(cleaned)
    logger.info(f"Carousel generated: {len(data.get('slides', []))} slides")
    return data


# ─── Phase F2: Long-form SEO Post ────────────────────────────────────────────

@activity.defn
async def generate_long_post_strategy(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Phase F2: Generate single image + long-form SEO content for Facebook/Blogs.

    Input config:
        app_name: str
        topic: str
        persona_config: dict
        platform: str (facebook, blog, linkedin)
        target_word_count: int (default 500)
        model: str

    Returns:
        hero_image_prompt: str    — for fal.ai
        title: str
        body: str                 — full post in persona language
        meta_description: str     — SEO meta (150 chars)
        hashtags: List[str]
        cta: str
    """
    app_name = config["app_name"]
    topic = config["topic"]
    persona = config.get("persona_config", {})
    platform = config.get("platform", "facebook")
    word_count = config.get("target_word_count", 500)
    model = config.get("model", "models/gemini-2.0-flash")
    language = persona.get("language_name", "English")
    skin_color = persona.get("skin_color", "diverse")

    logger.info(f"Generating long post | topic={topic} | platform={platform} | words={word_count}")

    LONG_POST_PROMPT = f"""
You are an SEO content writer. Create a long-form {platform} post about: {topic}
App: {app_name} | Language: {language} | Target: ~{word_count} words

Return ONLY valid JSON:
{{
  "hero_image_prompt": "<fal.ai English prompt for main image — {skin_color} person, relevant scene>",
  "title": "<catchy SEO title in {language}>",
  "body": "<full post body in {language}, ~{word_count} words, with subheadings using ##>",
  "meta_description": "<SEO meta, {language}, max 155 chars>",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "cta": "<call to action sentence in {language}>"
}}

Structure: intro hook → problem → solution (features) → social proof → CTA to download {app_name}.
"""

    ai = AIService()
    raw = await ai.generate_text(prompt=LONG_POST_PROMPT, model=model, temperature=0.7, max_tokens=4000)

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(cleaned)
    logger.info(f"Long post generated: title='{data.get('title', '')[:50]}'")
    return data
