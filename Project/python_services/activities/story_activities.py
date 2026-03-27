"""
Story Activities (TripC Daily Bot)
====================================
Temporal activities for the daily story pipeline.

Activities:
    generate_daily_story(config)        — Calls Gemini to write today's story
    send_story_for_approval(config)     — Sends story to all active subscribers

Design:
    - generate_daily_story returns a plain dict (StoryDraft) — JSON-serialisable,
      safe to pass between Temporal activities.
    - send_story_for_approval sends one Telegram message per subscriber with
      three inline buttons: Post to TikTok / Post to Shorts / Skip Today.
      The callback_data encodes the workflow_id so the webhook can signal back.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import activity

from services.ai_service import AIService
from services.telegram_subscriber_service import TelegramSubscriberService
from api.telegram_webhook import _tg_call, _escape_md

logger = logging.getLogger(__name__)

# ─── Prompt templates ─────────────────────────────────────────────────────────

_STORY_SYSTEM_PROMPT = """You are a travel content creator writing daily micro-stories
for TripC — a Vietnamese travel AI brand. Your tone is warm, engaging, and inspiring.

Output ONLY valid JSON with exactly these keys:
{
  "title": "<story title, max 10 words>",
  "body": "<story text, 80-120 words, hooks in first sentence>",
  "hashtags": ["<3-5 relevant hashtags without #>"],
  "visual_prompt": "<fal.ai image prompt describing the hero visual, in English>",
  "platform_notes": {
    "tiktok": "<0-1 extra tip for TikTok format>",
    "shorts": "<0-1 extra tip for YouTube Shorts format>"
  }
}

No markdown, no extra keys, ONLY the JSON object."""

_STORY_USER_TEMPLATE = """\
Write today's travel micro-story for TripC.

Date: {date}
Topic / destination: {topic}
Language: {language}
Persona voice: {voice_style}
Target audience: {audience}
"""

# ─── StoryDraft contract (dict, not Pydantic — must be JSON-serialisable) ─────

def _validate_story_draft(data: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal validation — raises ValueError if required fields are missing."""
    required = {"title", "body", "hashtags", "visual_prompt"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Story draft missing fields: {missing}")
    if not isinstance(data["hashtags"], list):
        data["hashtags"] = [data["hashtags"]]
    return data


# ─── Activity 1: generate_daily_story ─────────────────────────────────────────

@activity.defn
async def generate_daily_story(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate today's story using Gemini.

    Input config:
        topic       str   — destination or theme (e.g. "Ha Giang Loop")
        language    str   — output language (default: "Vietnamese")
        voice_style str   — persona tone (default: "warm and inspiring")
        audience    str   — target audience (default: "young Vietnamese travellers")
        date        str   — ISO date string (default: today, provided by workflow)
        model       str   — Gemini model slug (default: "models/gemini-2.0-flash")

    Returns:
        StoryDraft dict:
            title, body, hashtags, visual_prompt, platform_notes
    """
    topic: str = config.get("topic", "Vietnam travel")
    language: str = config.get("language", "Vietnamese")
    voice_style: str = config.get("voice_style", "warm and inspiring")
    audience: str = config.get("audience", "young Vietnamese travellers")
    date: str = config.get("date", "today")
    model: str = config.get("model", "models/gemini-2.0-flash")

    logger.info("Generating daily story | topic=%s | lang=%s", topic, language)

    user_prompt = _STORY_USER_TEMPLATE.format(
        date=date,
        topic=topic,
        language=language,
        voice_style=voice_style,
        audience=audience,
    )

    async with AIService() as ai:
        raw = await ai.generate_text(
            prompt=user_prompt,
            system_prompt=_STORY_SYSTEM_PROMPT,
            model=model,
            temperature=0.75,
            max_tokens=800,
        )

    # Strip markdown fences if Gemini wraps JSON in ```
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        )

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned non-JSON story: {e}\n---\n{cleaned[:400]}") from e

    story = _validate_story_draft(data)

    # Attach metadata so the approval message is self-contained
    story["topic"] = topic
    story["language"] = language
    story["date"] = date

    logger.info("Story generated: %s", story.get("title"))
    return story


# ─── Activity 2: send_story_for_approval ──────────────────────────────────────

@activity.defn
async def send_story_for_approval(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send the story to all active Telegram subscribers for approval.

    Input config:
        story           dict   — StoryDraft from generate_daily_story
        workflow_id     str    — Temporal workflow ID (used in callback_data)
        persona_id      str    — Optional, to filter to persona_operators later
        chat_type_filter str   — 'private' | 'group' | None = all (default None)

    Returns:
        {"sent_to": [chat_id, ...], "count": N}
    """
    story: Dict[str, Any] = config["story"]
    workflow_id: str = config["workflow_id"]
    chat_type_filter: Optional[str] = config.get("chat_type_filter")

    # ── 1. Get all active subscribers ──────────────────────────────────────────
    chat_ids: List[int] = await TelegramSubscriberService.get_active_chat_ids(
        chat_type=chat_type_filter,
    )

    if not chat_ids:
        logger.warning("No active Telegram subscribers found — story not sent")
        return {"sent_to": [], "count": 0}

    # ── 2. Build the message ───────────────────────────────────────────────────
    title = _escape_md(story.get("title", "Daily Story"))
    body = _escape_md(story.get("body", ""))
    tags = " ".join(f"\\#{_escape_md(h)}" for h in story.get("hashtags", []))
    date = _escape_md(story.get("date", "today"))

    message_text = (
        f"*{title}*\n\n"
        f"{body}\n\n"
        f"{tags}\n\n"
        f"_Generated for {date}_ \\— Approve to post\\?"
    )

    # Safe workflow_id for callback_data (Telegram limit: 64 bytes)
    safe_wf_id = workflow_id[-40:] if len(workflow_id) > 40 else workflow_id

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Post to TikTok", "callback_data": f"post_tiktok_{safe_wf_id}"},
                {"text": "Post to Shorts", "callback_data": f"post_shorts_{safe_wf_id}"},
            ],
            [
                {"text": "Skip Today", "callback_data": f"skip_{safe_wf_id}"},
            ],
        ]
    }

    # ── 3. Send to each subscriber ─────────────────────────────────────────────
    sent_to: List[int] = []
    for chat_id in chat_ids:
        try:
            result = await _tg_call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": message_text,
                    "parse_mode": "MarkdownV2",
                    "reply_markup": reply_markup,
                },
            )
            if result.get("ok"):
                sent_to.append(chat_id)
                logger.info("Story sent to chat_id=%s", chat_id)
            else:
                logger.warning(
                    "Failed to send story to chat_id=%s: %s",
                    chat_id,
                    result.get("description"),
                )
        except Exception as exc:
            logger.error("Error sending to chat_id=%s: %s", chat_id, exc)

    logger.info("Story sent to %d/%d subscribers", len(sent_to), len(chat_ids))
    return {"sent_to": sent_to, "count": len(sent_to)}
