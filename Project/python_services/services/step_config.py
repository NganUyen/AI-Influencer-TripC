"""Step metadata for Telegram/OpenClaw skill routing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _options(*items: tuple[str, str]) -> List[Dict[str, str]]:
    return [{"label": label, "value": value} for label, value in items]


MAIN_MENU: Dict[str, Any] = {
    "text": "🎨 Welcome to the TripC Media Editor!\n\nWhat would you like to create today? Please select an option below:",
    "rows": [
        [("🖼️ Create Image", "menu_image"), ("🎬 Create Video", "menu_video")],
        [("🎠 Carousel", "skill_carousel"), ("⚙️ Manage", "menu_manage")],
    ],
}

SUBMENUS: Dict[str, Dict[str, Any]] = {
    "menu_image": {
        "text": "🖼️ Select Image Creation Mode:",
        "rows": [
            [("🌄 Scene/Slideshow", "skill_image-scene")],
            [("🔙 Back", "menu_main")],
        ],
    },
    "menu_video": {
        "text": "🎬 Select Video Creation Mode:",
        "rows": [
            [("🎭 AI Influencer", "skill_video-ai")],
            [("🔙 Back", "menu_main")],
        ],
    },
    "menu_manage": {
        "text": "⚙️ Manage Your Content:",
        "rows": [
            [("➕ Create Persona", "skill_persona-creator")],
            [("📋 Inspect Personas", "skill_persona-inspector")],
            [("📊 Quota", "skill_quota-inspector"), ("📅 Weekly Plan", "skill_weekly-planner")],
            [("🔙 Back", "menu_main")],
        ],
    },
}

PREVIEW_ACTIONS = _options(
    ("✅ Use", "use"),
    ("🔄 Regenerate", "regenerate"),
    ("❌ Cancel", "cancel"),
)

IMAGE_SCENE_BATCH_ACTIONS = _options(
    ("Use Images", "use_images"),
    ("Regenerate", "regenerate"),
    ("Cancel", "cancel"),
)

PUBLISH_MANAGER_ACTIONS = _options(
    ("Retry Publish", "retry_publish"),
    ("Refresh Queue", "refresh_queue"),
    ("Back to Queue", "back_to_queue"),
    ("Cancel", "cancel"),
)


STEP_CONFIG: Dict[str, Dict[str, Dict[str, Any]]] = {
    "image-poster": {
        "collect_brief": {
            "input_type": "free_text",
            "field": "topic_or_brief",
            "prompt_text": "What should the poster promote?",
        },
        "choose_style": {
            "input_type": "inline_keyboard",
            "field": "style",
            "prompt_text": "Choose a poster style.",
            "options": _options(
                ("Bold", "bold"),
                ("Clean", "clean"),
                ("Editorial", "editorial"),
            ),
        },
        "choose_tone": {
            "input_type": "inline_keyboard",
            "field": "tone",
            "prompt_text": "Choose a tone.",
            "options": _options(
                ("Premium", "premium"),
                ("Friendly", "friendly"),
                ("Urgent", "urgent"),
            ),
        },
        "confirm_or_regenerate": {
            "input_type": "preview_actions",
            "prompt_text": "Poster preview ready. Use it, regenerate, or cancel.",
            "options": PREVIEW_ACTIONS,
        },
    },
    "image-scene": {
        "collect_prompt": {
            "input_type": "free_text",
            "field": "topic_or_prompt",
            "prompt_text": "🌅 What would you like to see in the scene? Please describe it:",
        },
        "choose_style": {
            "input_type": "inline_keyboard",
            "field": "style",
            "prompt_text": "🎨 Please choose an artistic style for your image:",
            "options": _options(
                ("Clean", "clean"),
                ("Cinematic", "cinematic"),
                ("Minimal", "minimal"),
            ),
        },
        "choose_ratio": {
            "input_type": "inline_keyboard",
            "field": "aspect_ratio",
            "prompt_text": "📐 Select the aspect ratio for your image:",
            "options": _options(
                ("16:9", "16:9"),
                ("9:16", "9:16"),
                ("1:1", "1:1"),
                ("4:3", "4:3"),
            ),
        },
        "confirm_or_regenerate": {
            "input_type": "preview_actions",
            "prompt_text": "✨ Here's your preview! How does it look?",
            "options": IMAGE_SCENE_BATCH_ACTIONS,
        },
        "selecting_images": {
            "input_type": "image_multi_select",
            "prompt_text": "Select one or more images, then submit.",
        },
    },
    "carousel": {
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "👤 Who will be the star? Choose a persona (or skip):",
            "allow_skip": True,
        },
        "collect_topic": {
            "input_type": "free_text",
            "field": "topic",
            "prompt_text": "Carousel topic.",
        },
        "choose_platform": {
            "input_type": "inline_keyboard",
            "field": "platform",
            "prompt_text": "📱 Which platform is this carousel for?",
            "options": _options(
                ("Instagram", "instagram"),
                ("LinkedIn", "linkedin"),
                ("Facebook", "facebook"),
            ),
        },
        "choose_slide_count": {
            "input_type": "inline_keyboard",
            "field": "num_slides",
            "prompt_text": "🔢 How many slides do you want?",
            "options": _options(
                ("4", "4"),
                ("6", "6"),
                ("8", "8"),
                ("10", "10"),
            ),
        },
        "choose_tone": {
            "input_type": "inline_keyboard",
            "field": "tone",
            "prompt_text": "🎭 What tone should we use for the content?",
            "options": _options(
                ("Educational", "educational"),
                ("Bold", "bold"),
                ("Clean", "clean"),
            ),
        },
        "preview": {
            "input_type": "preview_actions",
            "prompt_text": "🎡 Carousel preview is ready! Should we keep it?",
            "options": PREVIEW_ACTIONS,
        },
    },
    "video-ai": {
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "👤 Please select a ready persona:",
            "allow_skip": False,
        },
        "collect_topic": {
            "input_type": "free_text",
            "field": "topic",
            "prompt_text": "🎬 What should the AI influencer talk about in this video?",
        },
    },
    "publish-manager": {
        "list_publish_queue": {
            "input_type": "automatic",
            "prompt_text": "",
        },
        "select_item": {
            "input_type": "content_selector",
            "field": "content_id",
            "prompt_text": "Choose a publish item to inspect.",
        },
        "publish_or_schedule": {
            "input_type": "content_actions",
            "prompt_text": "Inspect the selected publish item.",
            "options": PUBLISH_MANAGER_ACTIONS,
        },
    },
    "quota-inspector": {
        "choose_provider_or_summary": {
            "input_type": "inline_keyboard",
            "field": "provider",
            "prompt_text": "📊 Would you like a general summary, or view quota for a specific provider?",
            "options": _options(
                ("Summary", "__summary__"),
                ("fal_ai", "fal_ai"),
                ("google_tts", "google_tts"),
                ("heygen", "heygen"),
                ("postiz", "postiz"),
            ),
        },
    },
    "persona-inspector": {
        "list_personas": {
            "input_type": "automatic",
            "prompt_text": "",
        },
        "select_persona": {
            "input_type": "persona_selector",
            "field": "persona_id",
            "prompt_text": "🔍 Which persona would you like to inspect?",
            "allow_skip": False,
        },
    },
    "persona-creator": {
        "collect_persona_id": {
            "input_type": "free_text",
            "field": "persona_id",
            "prompt_text": "🆔 Please enter a unique ID for your new persona:",
        },
        "choose_language": {
            "input_type": "inline_keyboard",
            "field": "language",
            "prompt_text": "🌐 What language will your persona speak?",
            "options": _options(
                ("Vietnamese", "Vietnamese"),
                ("English", "English"),
            ),
        },
        "choose_voice": {
            "input_type": "inline_keyboard",
            "field": "voice",
            "prompt_text": "🗣️ Please select a voice for your persona:",
            "options": _options(
                ("Male Friendly", "male_friendly"),
                ("Female Warm", "female_warm"),
            ),
        },
        "collect_appearance": {
            "input_type": "free_text",
            "field": "appearance_prompt_or_photo",
            "prompt_text": "📸 Please describe the persona's appearance, or upload a photo reference:",
        },
    },
    "weekly-planner": {
        "collect_brand_config": {
            "input_type": "free_text",
            "field": "brand_config",
            "prompt_text": "📅 Let's plan! Please send your brand config JSON or preset object:",
        },
    },
}


def get_step_definition(skill_name: str, step_key: str) -> Dict[str, Any]:
    return STEP_CONFIG.get(skill_name, {}).get(step_key, {})


def get_menu(menu_key: str) -> Optional[Dict[str, Any]]:
    if menu_key == "menu_main":
        return MAIN_MENU
    return SUBMENUS.get(menu_key)
