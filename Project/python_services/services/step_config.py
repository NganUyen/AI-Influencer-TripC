"""Step metadata for Telegram/OpenClaw skill routing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _options(*items: tuple[str, str]) -> List[Dict[str, str]]:
    return [{"label": label, "value": value} for label, value in items]


MAIN_MENU: Dict[str, Any] = {
    "text": "TripC Media Studio",
    "description_lines": [
        "Build images, videos, content assets, and operator tasks from one menu.",
        "Choose a lane below.",
    ],
    "rows": [
        [("Images", "menu_image"), ("Video", "menu_video")],
        [("Content", "menu_content"), ("Manage", "menu_manage")],
    ],
}

SUBMENUS: Dict[str, Dict[str, Any]] = {
    "menu_image": {
        "text": "Create Image",
        "description_lines": [
            "Generate marketing posters, scene batches, or review avatar tools.",
        ],
        "rows": [
            [("Marketing Poster", "skill_image-poster"), ("Scene Batch", "skill_image-scene")],
            [("Avatar Studio (Beta)", "info::image-avatar")],
            [("Back", "menu_main")],
        ],
    },
    "menu_video": {
        "text": "Create Video",
        "description_lines": [
            "Launch the AI influencer lane or preview upcoming video modes.",
        ],
        "rows": [
            [("AI Influencer", "skill_video-ai"), ("Tutorial (Soon)", "info::video-tutorial")],
            [("Back", "menu_main")],
        ],
    },
    "menu_content": {
        "text": "Content Tools",
        "description_lines": [
            "Create publishing assets and inspect the current publish queue.",
        ],
        "rows": [
            [("Carousel", "skill_carousel"), ("Publish Queue", "skill_publish-manager")],
            [("Long Post (Soon)", "info::long-post")],
            [("Back", "menu_main")],
        ],
    },
    "menu_manage": {
        "text": "Manage",
        "description_lines": [
            "Work with personas, quota, planning, and operator utilities.",
        ],
        "rows": [
            [("Persona Studio", "menu_personas"), ("Quota", "skill_quota-inspector")],
            [("Weekly Plan", "skill_weekly-planner")],
            [("Back", "menu_main")],
        ],
    },
    "menu_personas": {
        "text": "Persona Studio",
        "description_lines": [
            "Create, inspect, and plan persona-related work from one place.",
        ],
        "rows": [
            [("Create Persona", "skill_persona-creator"), ("Inspect Personas", "skill_persona-inspector")],
            [("Avatar Flow (Beta)", "info::image-avatar")],
            [("Back", "menu_manage")],
        ],
    },
}

PREVIEW_ACTIONS = _options(
    ("Use", "use"),
    ("Regenerate", "regenerate"),
    ("Cancel", "cancel"),
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
            "prompt_text": "What scene image should be generated?",
        },
        "choose_style": {
            "input_type": "inline_keyboard",
            "field": "style",
            "prompt_text": "Choose a style.",
            "options": _options(
                ("Clean", "clean"),
                ("Cinematic", "cinematic"),
                ("Minimal", "minimal"),
            ),
        },
        "confirm_or_regenerate": {
            "input_type": "preview_actions",
            "prompt_text": "Choose what to do with this batch.",
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
            "prompt_text": "Choose a persona or skip.",
            "allow_skip": True,
        },
        "collect_topic": {
            "input_type": "free_text",
            "field": "topic",
            "prompt_text": "What should the carousel explain?",
        },
        "choose_platform": {
            "input_type": "inline_keyboard",
            "field": "platform",
            "prompt_text": "Choose a platform.",
            "options": _options(
                ("Instagram", "instagram"),
                ("LinkedIn", "linkedin"),
                ("Facebook", "facebook"),
            ),
        },
        "choose_slide_count": {
            "input_type": "inline_keyboard",
            "field": "num_slides",
            "prompt_text": "How many slides?",
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
            "prompt_text": "Choose a tone.",
            "options": _options(
                ("Educational", "educational"),
                ("Bold", "bold"),
                ("Clean", "clean"),
            ),
        },
        "preview": {
            "input_type": "preview_actions",
            "prompt_text": "Use this carousel?",
            "options": PREVIEW_ACTIONS,
        },
    },
    "video-ai": {
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "Choose a ready persona.",
            "allow_skip": False,
        },
        "collect_topic": {
            "input_type": "free_text",
            "field": "topic",
            "prompt_text": "What should the video be about?",
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
            "prompt_text": "View summary or one provider?",
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
            "prompt_text": "Choose a persona to inspect.",
            "allow_skip": False,
        },
    },
    "persona-creator": {
        "collect_persona_id": {
            "input_type": "free_text",
            "field": "persona_id",
            "prompt_text": "Enter a persona ID.",
        },
        "choose_language": {
            "input_type": "inline_keyboard",
            "field": "language",
            "prompt_text": "Choose a language.",
            "options": _options(
                ("Vietnamese", "Vietnamese"),
                ("English", "English"),
            ),
        },
        "choose_voice": {
            "input_type": "inline_keyboard",
            "field": "voice",
            "prompt_text": "Choose a voice.",
            "options": _options(
                ("male_friendly", "male_friendly"),
                ("female_warm", "female_warm"),
            ),
        },
        "collect_appearance": {
            "input_type": "free_text",
            "field": "appearance_prompt_or_photo",
            "prompt_text": "Describe the avatar or upload a photo reference.",
        },
    },
    "weekly-planner": {
        "collect_brand_config": {
            "input_type": "free_text",
            "field": "brand_config",
            "prompt_text": "Send brand config JSON or paste a preset object.",
        },
    },
}


def get_step_definition(skill_name: str, step_key: str) -> Dict[str, Any]:
    return STEP_CONFIG.get(skill_name, {}).get(step_key, {})


def get_menu(menu_key: str) -> Optional[Dict[str, Any]]:
    if menu_key == "menu_main":
        return MAIN_MENU
    return SUBMENUS.get(menu_key)
