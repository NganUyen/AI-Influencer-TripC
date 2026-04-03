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
from services.script_service import ScriptService
from utils.json_helpers import extract_json_from_llm_response

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

    async with OpenClawService() as openclaw:
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

    prompts = []

    daily_content = strategy.get("strategy", {}).get("daily_content", [])

    for day_idx, day_content in enumerate(daily_content):
        media_requirements = day_content.get("media", [])

        for media in media_requirements:
            media_type = media.get("type")

            if media_type in ["image", "video"]:
                # Generate prompt for fal.ai using OpenClaw
                openclaw = OpenClawService()
                visual_prompt = f"""You are an expert at creating prompts for AI image and video generation.
Create detailed, vivid prompts that will produce high-quality visuals optimized for social media.

Create an image generation prompt for:

Content: {day_content.get("theme")}
Visual Style: {media.get("style", "modern")}
Platform: {media.get("platform")}

The prompt should be detailed, specific, and optimized for modern AI image models.
Include details about composition, lighting, colors, and mood.
Keep it under 200 words."""
                
                prompt = await openclaw.execute_task(
                    task_type="visual_prompt_generation",
                    prompt=visual_prompt,
                    user_id="system",
                    context={
                        "theme": day_content.get("theme"),
                        "style": media.get("style", "modern"),
                        "platform": media.get("platform"),
                    }
                )
                if isinstance(prompt, dict):
                    prompt = prompt.get("result", str(prompt))

                prompts.append(
                    {
                        "type": media_type,
                        "service": "fal_ai",
                        "prompt": prompt,
                        "day": day_idx + 1,
                        "platform": media.get("platform"),
                        "config": media.get("config", {}),
                        "campaign_id": strategy.get("brand_config", {}).get("campaign_id"),
                    }
                )

            elif media_type == "audio":
                # Generate script for PlayHT using OpenClaw
                voice_persona = media.get("voice_persona", "professional")
                content = day_content.get("message")
                audio_prompt = f"""You are a scriptwriter creating content for {voice_persona} voice synthesis.
Optimize the text for natural speech patterns, including appropriate pauses and intonation guidance.

Convert this content into a natural-sounding speech script:

{content}

Ensure it sounds conversational and engaging when spoken aloud."""
                
                openclaw = OpenClawService()
                script = await openclaw.execute_task(
                    task_type="audio_script_generation",
                    prompt=audio_prompt,
                    user_id="system",
                    context={
                        "content": content,
                        "voice_persona": voice_persona,
                    }
                )
                if isinstance(script, dict):
                    script = script.get("result", str(script))

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

    daily_strategy = strategy["strategy"]["daily_content"][day_number - 1]

    # Generate platform-specific copy using OpenClaw
    theme = daily_strategy.get("theme")
    platforms = strategy.get("platforms")
    brand_voice = strategy.get("brand_config", {}).get("voice")
    
    openclaw = OpenClawService()
    content = {}
    
    for platform in platforms:
        platform_prompt = f"""You are a {brand_voice} social media copywriter.
Create engaging content optimized for {platform}'s audience and format.

Create a post about: {theme}

Platform: {platform}
Format requirements:
- Twitter: 280 characters max, hashtag-friendly
- LinkedIn: Professional, longer-form (500-1000 chars)
- Instagram: Visual-first, emoji-friendly, hashtags at end
- TikTok: Short, punchy, trend-aware

Return only the post text, no explanations."""
        
        result = await openclaw.execute_task(
            task_type="platform_copy_generation",
            prompt=platform_prompt,
            user_id="system",
            context={
                "theme": theme,
                "platform": platform,
                "brand_voice": brand_voice,
            }
        )
        content[platform] = result.get("result", str(result)) if isinstance(result, dict) else str(result)

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
    model = config.get("model", "claude-3-5-sonnet-20241022")
    tone = config.get("tone", "clear and persuasive")
    style = config.get("style", "modern social carousel")
    freeform_brief = config.get("freeform_brief")
    creative_notes = config.get("creative_notes")
    language = persona.get("language_name", "English")
    skin_color = persona.get("skin_color", "diverse")

    logger.info(f"Generating carousel | topic={topic} | slides={num_slides} | platform={platform}")

    CAROUSEL_PROMPT = f"""
You are a social media content creator. Generate a {num_slides}-slide carousel for {platform}.
App: {app_name} | Topic: {topic}
Persona language: {language} | Model skin tone in images: {skin_color}
Tone: {tone}
Visual style: {style}
Extra brief: {freeform_brief or "None"}
Creative notes: {creative_notes or "None"}

Return ONLY valid JSON:
{{
  "slides": [
    {{
      "slide_num": 1,
      "image_prompt": "<fal.ai English prompt — specific, visual, {skin_color} person natural>",
      "caption": "<short slide text in {language}, max 12 words>",
      "cta_overlay": "<optional small overlay text, e.g. 'Swipe for tip 2'>"
    }}
  ],
  "platform_caption": "<main post caption in {language}, max 150 chars>",
  "hashtags": ["#tag1", "#tag2"]
}}

    Slide 1: Hook/Problem. Slides 2-7: Features/Benefits. Slide 8: CTA to download {app_name}.
    Keep each slide visually distinct and suitable for text overlay on top of the image.
    """

    openclaw = OpenClawService()
    raw = await openclaw.execute_task(
        task_type="carousel_strategy",
        prompt=CAROUSEL_PROMPT,
        user_id="system",
        context={
            "app_name": app_name,
            "topic": topic,
            "platform": platform,
            "num_slides": num_slides,
        }
    )
    if isinstance(raw, dict) and "result" in raw:
        raw = raw["result"]

    data = extract_json_from_llm_response(raw)
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
    model = config.get("model", "claude-3-5-sonnet-20241022")
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

    openclaw = OpenClawService()
    raw = await openclaw.execute_task(
        task_type="long_post_strategy",
        prompt=LONG_POST_PROMPT,
        user_id="system",
        context={
            "app_name": app_name,
            "topic": topic,
            "platform": platform,
            "word_count": word_count,
        }
    )
    if isinstance(raw, dict) and "result" in raw:
        raw = raw["result"]

    data = extract_json_from_llm_response(raw)
    logger.info(f"Long post generated: title='{data.get('title', '')[:50]}'")
    return data
