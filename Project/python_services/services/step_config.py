"""Step metadata for Telegram/OpenClaw skill routing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _options(*items: tuple[str, str]) -> List[Dict[str, str]]:
    return [{"label": label, "value": value} for label, value in items]


MAIN_MENU: Dict[str, Any] = {
    "text": "🎨 Welcome to the TripC Media Studio!\n\nWhat would you like to create today? Please select an option below:",
    "rows": [
        [("📖 Daily Story", "skill_daily-story")],
        [("🖼️ Create Image", "menu_image"), ("🎬 Create Video", "menu_video")],
        [
            ("➕ Create Persona", "skill_persona-creator"),
            ("🔍 Inspect Persona", "skill_persona-inspector"),
        ],
        [("📝 Content", "menu_content"), ("🎠 Carousel", "skill_carousel")],
        [("⚙️ Manage", "menu_manage")],
    ],
}

SUBMENUS: Dict[str, Dict[str, Any]] = {
    "menu_image": {
        "text": "🖼️ Select Image Creation Mode:",
        "rows": [
            [("🎨 Marketing Poster", "skill_image-poster")],
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
    "menu_content": {
        "text": "📝 Select Content Creation Mode:",
        "rows": [
            [("📝 Long Post", "skill_long-post")],
            [("🔙 Back", "menu_main")],
        ],
    },
    "menu_manage": {
        "text": "⚙️ Manage & Monitor:",
        "rows": [
            [
                ("📊 Quota", "skill_quota-inspector"),
                ("📅 Weekly Plan", "skill_weekly-planner"),
            ],
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
    ("Inspect Provider", "inspect_provider_wiring"),
    ("Check Engagement", "check_engagement"),
    ("Boost Engagement", "boost_engagement"),
    ("Retry Publish", "retry_publish"),
    ("Refresh Queue", "refresh_queue"),
    ("Back to Queue", "back_to_queue"),
    ("Cancel", "cancel"),
)

PREPRO_APPROVAL_ACTIONS = _options(
    ("Approve", "approve"),
    ("Edit", "edit"),
    ("Regenerate", "regenerate"),
    ("Cancel", "cancel"),
)


STEP_CONFIG: Dict[str, Dict[str, Dict[str, Any]]] = {
    "image-poster": {
        "collect_brief": {
            "input_type": "free_text",
            "field": "topic_or_brief",
            "prompt_text": "🖼️ What should this poster promote?\n\nInclude the key message, product, or event you want to highlight.",
        },
        "choose_style": {
            "input_type": "inline_keyboard",
            "field": "style",
            "prompt_text": "🎨 Choose a visual style for the poster.",
            "options": _options(
                ("Bold", "bold"),
                ("Clean", "clean"),
                ("Editorial", "editorial"),
            ),
        },
        "choose_tone": {
            "input_type": "inline_keyboard",
            "field": "tone",
            "prompt_text": "🎭 Choose the tone that best fits your audience.",
            "options": _options(
                ("Premium", "premium"),
                ("Friendly", "friendly"),
                ("Urgent", "urgent"),
            ),
        },
        "choose_ratio": {
            "input_type": "inline_keyboard",
            "field": "aspect_ratio",
            "prompt_text": "📐 Choose the aspect ratio for this poster.",
            "options": _options(
                ("4:5", "4:5"),
                ("1:1", "1:1"),
                ("9:16", "9:16"),
                ("16:9", "16:9"),
            ),
        },
        "confirm_or_regenerate": {
            "input_type": "preview_actions",
            "prompt_text": "✅ Poster preview is ready. Use it, regenerate with the same inputs, or cancel.",
            "options": PREVIEW_ACTIONS,
        },
    },
    "image-scene": {
        "collect_prompt": {
            "input_type": "free_text",
            "field": "topic_or_prompt",
            "prompt_text": '🌅 Describe the scene you want to generate.\n\nExample: "A futuristic city at night" or "A sunrise over mountain peaks"',
        },
        "choose_style": {
            "input_type": "inline_keyboard",
            "field": "style",
            "prompt_text": "🎨 Choose an artistic style for this scene.",
            "options": _options(
                ("Clean", "clean"),
                ("Cinematic", "cinematic"),
                ("Minimal", "minimal"),
            ),
        },
        "choose_ratio": {
            "input_type": "inline_keyboard",
            "field": "aspect_ratio",
            "prompt_text": "📐 Select the aspect ratio for this image.",
            "options": _options(
                ("16:9", "16:9"),
                ("9:16", "9:16"),
                ("1:1", "1:1"),
                ("4:3", "4:3"),
            ),
        },
        "confirm_or_regenerate": {
            "input_type": "preview_actions",
            "prompt_text": "✅ Scene preview is ready. Use it, regenerate, or cancel.",
            "options": IMAGE_SCENE_BATCH_ACTIONS,
        },
        "selecting_images": {
            "input_type": "image_multi_select",
            "prompt_text": "Select one or more images from the batch, then submit.",
        },
    },
    "carousel": {
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "👤 Choose a persona for this carousel, or skip.",
            "allow_skip": True,
        },
        "collect_topic": {
            "input_type": "free_text",
            "field": "topic",
            "prompt_text": '📝 What topic should this carousel cover?\n\nExample: "Top 5 hidden beaches in Da Nang" or "How to book a group trip"',
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
            "prompt_text": "🎭 Choose the content tone for this carousel.",
            "options": _options(
                ("Educational", "educational"),
                ("Bold", "bold"),
                ("Clean", "clean"),
            ),
        },
        "preview": {
            "input_type": "preview_actions",
            "prompt_text": "✅ Carousel preview is ready. Approve it, regenerate, or cancel.",
            "options": PREVIEW_ACTIONS,
        },
    },
    "video-ai": {
        "select_mode": {
            "input_type": "inline_keyboard",
            "field": "creative_input_mode",
            "prompt_text": "🎬 How would you like to create your video?\n\n"
            "Choose your input method:",
            "options": _options(
                ("💡 Idea Brief", "idea_brief"),
                ("📹 Recorded Demo Video", "recorded_demo_video"),
            ),
        },
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "👤 Select a ready persona for this video.",
            "allow_skip": False,
        },
        "upload_demo_video": {
            "input_type": "video_upload",
            "field": "demo_video_telegram_file_id",
            "prompt_text": "📹 Please upload your demo video.\n\n"
            "Requirements:\n"
            "• Duration: 30 seconds to 3 minutes\n"
            "• Resolution: 720p or higher recommended\n"
            "• Format: MP4, MOV, or WebM",
        },
        "collect_idea_brief": {
            "input_type": "free_text",
            "field": "idea_brief",
            "prompt_text": '🎬 What is the core idea for this video?\n\nExample: "Showcasing the itinerary booking flow for first-time users"',
        },
        "collect_feature_focus": {
            "input_type": "free_text",
            "field": "feature_focus",
            "prompt_text": '🔍 Which specific feature or product angle should this video focus on?\n\nExample: "Group trip planning" or "One-click hotel booking"',
        },
        "collect_feature_emphasis": {
            "input_type": "free_text",
            "field": "feature_emphasis",
            "prompt_text": "🔍 (Optional) Any specific features you'd like to emphasize in the video?\n\n"
            "Send /skip if you want the system to decide automatically based on the uploaded video.",
        },
        "choose_video_goal": {
            "input_type": "inline_keyboard",
            "field": "video_goal",
            "prompt_text": "🎯 What is the main goal of this video?",
            "options": _options(
                ("Feature Demo", "feature_demo"),
                ("Conversion", "conversion"),
                ("Awareness", "awareness"),
                ("Walkthrough", "walkthrough"),
            ),
        },
        "collect_audience": {
            "input_type": "free_text",
            "field": "audience",
            "prompt_text": '👥 Who is the target audience for this video?\n\nExample: "Young Vietnamese travelers aged 20–35"',
        },
        "collect_cta": {
            "input_type": "free_text",
            "field": "cta",
            "prompt_text": '📣 What call-to-action should the video end with?\n\nExample: "Book your trip at tripc.vn" or "Download the app now"',
        },
        "collect_reference_url": {
            "input_type": "free_text",
            "field": "reference_url",
            "prompt_text": "🔗 Send a URL this video should reference.\n\nExample: a product page, landing page, or feature walkthrough.",
        },
        "choose_access_level": {
            "input_type": "inline_keyboard",
            "field": "access_level",
            "prompt_text": "🔐 What level of access do you have for that source?",
            "options": _options(
                ("Public Page Only", "public_page_only"),
                ("Has Logged-in Access", "has_logged_in_access"),
                ("Login Needed But Not Available", "login_required_but_not_available"),
                ("Not Sure", "unknown"),
            ),
        },
        "confirm_concept": {
            "input_type": "preview_actions",
            "prompt_text": "📋 Review the concept brief before continuing.",
            "options": PREPRO_APPROVAL_ACTIONS,
        },
        "confirm_beats": {
            "input_type": "preview_actions",
            "prompt_text": "📋 Review the beat plan before packaging the concept.",
            "options": PREPRO_APPROVAL_ACTIONS,
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
            "prompt_text": "📊 View a usage summary across all providers, or check quota for a specific one.",
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
            "prompt_text": "🔍 Select a persona to inspect.",
            "allow_skip": False,
        },
    },
    "persona-creator": {
        "choose_creation_mode": {
            "input_type": "inline_keyboard",
            "field": "creation_mode",
            "prompt_text": "🎨 *How would you like to create this persona?*",
            "options": _options(
                ("✍️ Create Manually", "manual"),
                ("✨ Dream up with AI", "dream"),
            ),
        },
        "collect_dream_brief": {
            "input_type": "free_text",
            "field": "dream_brief",
            "prompt_text": "✨ *Describe the type of persona you'd like to create\\.*\n\nExample: 'Jamaican woman, travel influencer' or 'Swedish male baker in his 50s'\\.",
        },
        "confirm_dream": {
            "input_type": "preview_actions",
            "prompt_text": "✨ *AI Dream Ready\\!* How does this identity look to you?",
            "options": _options(
                ("✅ Use & Continue", "use"),
                ("✏️ Edit ID", "edit_id"),
                ("🎭 Edit Appearance", "edit_appearance"),
                ("🔄 Dream Again", "regenerate"),
                ("❌ Cancel", "cancel"),
            ),
        },
        "collect_persona_id": {
            "input_type": "free_text",
            "field": "persona_id",
            "prompt_text": "🆔 Set a unique ID for this persona.\n\nExample: ray-aus, linh-hcm",
        },
        "choose_language": {
            "input_type": "inline_keyboard",
            "field": "language",
            "prompt_text": "🌐 What language will this persona communicate in?",
            "options": _options(
                ("Vietnamese", "Vietnamese"),
                ("English", "English"),
            ),
        },
        "choose_voice": {
            "input_type": "inline_keyboard",
            "field": "voice",
            "prompt_text": "🗣️ Select a voice type for this persona.",
            "options": _options(
                ("Male Friendly", "male_friendly"),
                ("Female Warm", "female_warm"),
                ("Male Professional", "male_professional"),
                ("Female Clear", "female_clear"),
            ),
        },
        "collect_appearance": {
            "input_type": "free_text",
            "field": "appearance_prompt_or_photo",
            "prompt_text": "📸 Describe the persona's appearance or upload a reference photo.\n\nInclude: age range, style, outfit, and setting.",
        },
    },
    "weekly-planner": {
        "collect_brand_config": {
            "input_type": "free_text",
            "field": "brand_config",
            "prompt_text": "📅 Let's plan! Please send your brand config JSON or preset object:",
        },
    },
    "daily-story": {
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "👤 Who is narrating this story? Choose a persona:",
            "allow_skip": False,
        },
        "collect_content": {
            "input_type": "free_text",
            "field": "topic",
            "prompt_text": "📝 What kind of content do you want for today's story?",
        },
        "collect_feedback": {
            "input_type": "free_text",
            "field": "feedback",
            "prompt_text": "🔄 What should be improved? (e.g. 'Make it funnier, talk more about food')",
        },
        "choose_media_action": {
            "input_type": "inline_keyboard",
            "field": "media_action",
            "prompt_text": "Story draft is ready! What would you like to do next?",
            "options": _options(
                ("🔄 Regenerate Story", "regenerate_story"),
                ("🖼️ Create Image", "forward_image"),
                ("🎬 Create Video", "forward_video"),
                ("🎠 Create Carousel", "forward_carousel"),
                ("❌ Cancel", "cancel"),
            ),
        },
    },
}


def get_step_definition(skill_name: str, step_key: str) -> Dict[str, Any]:
    return STEP_CONFIG.get(skill_name, {}).get(step_key, {})


def get_menu(menu_key: str) -> Optional[Dict[str, Any]]:
    if menu_key == "menu_main":
        return MAIN_MENU
    return SUBMENUS.get(menu_key)
