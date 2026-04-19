"""Step metadata for Telegram/OpenClaw skill routing."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _options(*items: tuple[str, str]) -> List[Dict[str, str]]:
    return [{"label": label, "value": value} for label, value in items]


MAIN_MENU: Dict[str, Any] = {
    "text": "🎨 Welcome to the TripC Media Studio!\n\nWhat would you like to create today? Please select an option below:",
    "rows": [
        [("📖 Daily Story", "skill_daily-story")],
        [("🖼️ Create Image", "menu_image"), ("🎬 Create Video", "skill_video-ai")],
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
        "text": "⚙️ Manage Your Content:",
        "rows": [
            [("➕ Create Persona", "skill_persona-creator")],
            [("📋 Inspect Personas", "skill_persona-inspector")],
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
        "choose_ratio": {
            "input_type": "inline_keyboard",
            "field": "aspect_ratio",
            "prompt_text": "Choose the poster aspect ratio.",
            "options": _options(
                ("4:5", "4:5"),
                ("1:1", "1:1"),
                ("9:16", "9:16"),
                ("16:9", "16:9"),
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
            "prompt_text": '🌅 Describe the scene you want to generate.\n\nExample: "A futuristic city at night" or "A sunrise over mountain peaks"',
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
        "collect_objective": {
            "input_type": "free_text",
            "field": "objective",
            "prompt_text": "What is your objective for this video?\n\nExample: Explain the product quickly, record a walkthrough, or create a short review that drives signups.",
        },
        "collect_target_url": {
            "input_type": "free_text",
            "field": "target_url",
            "prompt_text": "Send the target URL to review.\n\nExample: https://tripc.ai",
        },
        "website_review": {
            "input_type": "automatic",
            "prompt_text": "",
        },
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "Select a ready persona for this video concept.",
            "allow_skip": False,
        },
        "choose_execution_mode": {
            "input_type": "inline_keyboard",
            "field": "execution_mode",
            "prompt_text": "Choose how this video should be executed.\n\n"
            "🤖 Autonomous Screen Recording\n"
            "Best for full end-to-end automation. The system navigates the product, captures the screen, and assembles the production flow for you.\n\n"
            "🔐 Authenticated PC Recording\n"
            "Best for login-required or protected product flows. You complete a secure PC handoff first, then recording continues inside the authenticated session.\n\n"
            "📱 Manual Mobile Recording\n"
            "Best for mobile-first apps or when you already have raw footage. You record the demo on your phone and upload it for production.",
            "options": _options(
                ("🤖 Auto Record", "autonomous_screen_recording"),
                ("🔐 Auth PC", "authenticated_pc_recording"),
                ("📱 Mobile Demo", "manual_mobile_recording"),
            ),
        },
        "confirm_plan": {
            "input_type": "inline_keyboard",
            "field": "plan_decision",
            "prompt_text": "Review the video plan below, then confirm it or revise one part.",
            "options": _options(
                ("Confirm Plan", "confirm"),
                ("Change Objective", "revise_objective"),
                ("Change URL", "revise_url"),
                ("Change Persona", "revise_persona"),
                ("Change Mode", "revise_mode"),
            ),
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
        "collect_reference_url": {
            "input_type": "free_text",
            "field": "reference_url",
            "prompt_text": "🔗 Send the product or app URL this video should be grounded on.\n\n"
            "Example: https://tripc.ai or https://yourapp.com",
        },
        # V3.1 new steps
        "collect_user_video_thesis": {
            "input_type": "free_text",
            "field": "user_video_thesis",
            "prompt_text": "📝 In one sentence, what does this video demonstrate?\n\n"
            "Example: 'Shows how to create and share a group trip itinerary'",
        },
        "choose_content_scope": {
            "input_type": "inline_keyboard",
            "field": "content_scope",
            "prompt_text": "🎯 What type of content is this video?\n\n"
            "This helps me understand what to focus on:",
            "options": _options(
                ("🔍 Single Feature", "single_feature"),
                ("📋 Single Flow/Journey", "single_flow"),
                ("🌐 Product Overview", "product_overview"),
            ),
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
            "prompt_text": (
                "🎬 What type of video do you want to create?\n\n"
                "📱 Feature Spotlight — Highlight one key feature in detail\n"
                "📚 Step-by-Step Guide — Explain how to use something from start to finish\n"
                "🚀 Drive Action — Push viewers to sign up, try, or buy now"
            ),
            "options": _options(
                ("📱 Feature Spotlight", "feature_demo"),
                ("📚 Step-by-Step Guide", "walkthrough"),
                ("🚀 Drive Action", "conversion"),
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
        "collect_official_name_hint": {
            "input_type": "free_text",
            "field": "official_name_hint",
            "prompt_text": "🏷️ (Optional) Official feature name if different from what appears on screen.\n\n"
            "Send /skip if the detected name is correct.",
        },
        "collect_must_not_say": {
            "input_type": "free_text",
            "field": "must_not_say",
            "prompt_text": "🚫 (Optional) Any terms or claims to avoid in the video?\n\n"
            "Send /skip if no restrictions.",
        },
        "choose_access_level": {
            "input_type": "inline_keyboard",
            "field": "access_level",
            "prompt_text": "What access do you have for that source?",
            "options": _options(
                ("Public Page Only", "public_page_only"),
                ("Has Logged-in Access", "has_logged_in_access"),
                ("Login Needed But Not Available", "login_required_but_not_available"),
                ("Not Sure", "unknown"),
            ),
        },
        # Phase 5: Demo video preview confirmation step (V3.1 updated)
        # Analysis + Grounding + IdeaResolver runs before this step
        "demo_preview_confirm": {
            "input_type": "inline_keyboard",
            "field": "demo_preview_action",
            "prompt_text": "📋 *Proposed Main Idea*\n\n"
            "Please review what I've resolved from your demo video.\n"
            "You can approve to proceed, pick another focus, rewrite the idea, or re-upload.",
            "options": _options(
                ("✅ Approve", "approve"),
                ("🔄 Pick another focus", "pick_alternate"),
                ("✏️ Rewrite", "rewrite"),
                ("📹 Re-upload", "reupload"),
            ),
            "timeout_sec": 900,  # 15 minutes
            "timeout_action": "abort",  # Abort on timeout, don't auto-confirm
        },
        # V3.1 new steps for preview actions
        "demo_pick_alternate_focus": {
            "input_type": "inline_keyboard",
            "field": "alternate_feature_focus",
            "prompt_text": "🔄 Choose an alternate feature to focus on:\n\n"
            "These are other features detected in your video, ranked by relevance.",
            "options": [],  # Dynamically populated from grounded_features
        },
        "demo_rewrite_main_idea": {
            "input_type": "free_text",
            "field": "rewritten_main_idea",
            "prompt_text": "✏️ Rewrite the main idea you want this video to convey:\n\n"
            "Describe in one clear sentence what viewers should understand.",
        },
        "collect_desired_takeaway": {
            "input_type": "free_text",
            "field": "desired_takeaway",
            "prompt_text": "💡 (Optional) What should viewers remember after watching?\n\n"
            "Send /skip to let me determine this from the analysis.",
        },
        # Phase 5: Feature correction step (if user chooses "correct") - kept for compatibility
        "demo_correct_features": {
            "input_type": "free_text",
            "field": "feature_correction",
            "prompt_text": "✏️ What should I correct about the detected features?\n\n"
            "Tell me which features are wrong or what I missed.",
        },
        # Phase 5: Feature re-emphasis step (if user chooses "reemphasize")
        "demo_reemphasize_features": {
            "input_type": "free_text",
            "field": "feature_reemphasis",
            "prompt_text": "🎯 Which features should I focus on?\n\n"
            "List the features that matter most for this video.",
        },
        "confirm_concept": {
            "input_type": "preview_actions",
            "prompt_text": "Review the concept brief before continuing.",
            "options": PREPRO_APPROVAL_ACTIONS,
        },
        "confirm_beats": {
            "input_type": "preview_actions",
            "prompt_text": "Review the beat plan before packaging the concept.",
            "options": PREPRO_APPROVAL_ACTIONS,
        },
    },
    "video-planner": {
        "collect_objective": {
            "input_type": "free_text",
            "field": "objective",
            "prompt_text": "What is your objective for this video?\n\nExample: Explain the product quickly, record a walkthrough, or create a short review that drives signups.",
        },
        "collect_target_url": {
            "input_type": "free_text",
            "field": "target_url",
            "prompt_text": "Send the target URL to review.\n\nExample: https://tripc.ai",
        },
        "choose_language": {
            "input_type": "free_text",
            "field": "language",
            "prompt_text": "What language should be used?\n\nExample: English or Vietnamese.",
        },
        "pick_persona": {
            "input_type": "persona_picker",
            "field": "persona_id",
            "prompt_text": "Which persona should be applied to this video plan?",
            "allow_skip": False,
        },
        "choose_execution_mode": {
            "input_type": "inline_keyboard",
            "field": "execution_mode",
            "prompt_text": "Choose how this video should be executed.\n\n"
            "🤖 Autonomous Screen Recording\n"
            "Best for full end-to-end automation. The system navigates the product, captures the screen, and assembles the production flow for you.\n\n"
            "🔐 Authenticated PC Recording\n"
            "Best for login-required or protected product flows. You complete a secure PC handoff first, then recording continues inside the authenticated session.\n\n"
            "📱 Manual Mobile Recording\n"
            "Best for mobile-first apps or when you already have raw footage. You record the demo on your phone and upload it for production.",
            "options": _options(
                ("🤖 Auto Record", "autonomous_screen_recording"),
                ("🔐 Auth PC", "authenticated_pc_recording"),
                ("📱 Mobile Demo", "manual_mobile_recording"),
            ),
        },
        "confirm_plan": {
            "input_type": "inline_keyboard",
            "field": "plan_decision",
            "prompt_text": "Review the video plan below, then confirm it or revise one part.",
            "options": _options(
                ("Confirm Plan", "confirm"),
                ("Change Objective", "revise_objective"),
                ("Change URL", "revise_url"),
                ("Change Persona", "revise_persona"),
                ("Change Mode", "revise_mode"),
            ),
        },
        "upload_manual_video": {
            "input_type": "free_text",
            "field": "manual_upload_note",
            "prompt_text": "Upload the mobile-recorded demo video now. Keep the footage in the current vertical format so the final output stays on the existing 9:16 canvas.",
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
        "choose_creation_mode": {
            "input_type": "inline_keyboard",
            "field": "creation_mode",
            "prompt_text": "🎨 *How would you like to build your persona?*",
            "options": _options(
                ("✍️ Create Manually", "manual"),
                ("✨ Dream up with AI", "dream"),
            ),
        },
        "collect_nationality": {
            "input_type": "free_text",
            "field": "nationality",
            "prompt_text": "🏳️ *Step 1: Nationality*\n\nWhich nationality should this persona represent?\nExamples: 'American', 'Italian', 'Japanese'\\.",
        },
        "choose_voice": {
            "input_type": "inline_keyboard",
            "field": "voice",
            "prompt_text": "🗣️ *Step 2: Voice*\n\nPlease select a voice preset for your persona:",
            "options": _options(
                ("Male Friendly", "male_friendly"),
                ("Female Warm", "female_warm"),
                ("Male Professional", "male_professional"),
                ("Female Clear", "female_clear"),
            ),
        },
        "collect_dream_brief": {
            "input_type": "free_text",
            "field": "dream_brief",
            "prompt_text": "👤 *Step 3: Description*\n\nNow, describe who you want to create in a few words\\.\nExample: 'young woman in a Paris café' or 'fitness coach in an urban gym'\\.",
        },
        "confirm_dream": {
            "input_type": "preview_actions",
            "field": "dream_confirmed",
            "prompt_text": "✨ *Identity Suggestions Ready\\!* Review the localized name and ID below:",
            "options": _options(
                ("✅ Use & Continue", "confirm"),
                ("🔄 Retry", "retry"),
                ("❌ Cancel", "cancel"),
            ),
        },
        "collect_persona_id": {
            "input_type": "free_text",
            "field": "persona_id",
            "prompt_text": "🆔 Send a unique ID for the new persona.\nExample: ray-aus",
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
                ("Male Professional", "male_professional"),
                ("Female Clear", "female_clear"),
            ),
        },
        "collect_appearance": {
            "input_type": "free_text",
            "field": "appearance_prompt_or_photo",
            "prompt_text": "📸 Describe the persona's appearance, or upload a reference photo.\nTip: include style, outfit, age range, and setting.",
        },
        "preview": {
            "input_type": "preview_actions",
            "field": "preview_command",
            "prompt_text": "✨ *Persona Profile Ready\\!*",
            "options": _options(
                ("✏️ Edit Name", "edit_p_name"),
                ("🎭 Edit Appearance", "edit_appearance"),
                ("🗣️ Change Voice", "choose_voice"),
                ("🔄 Rebuild Avatar", "rebuild_avatar"),
                ("✅ Ready / Finish", "ready"),
                ("❌ Cancel", "cancel"),
            ),
        },
        "edit_p_name": {
            "input_type": "free_text",
            "field": "display_name",
            "prompt_text": "✏️ *Update Persona Name*\n\nPlease send the new name for this persona:",
        },
        "edit_appearance": {
            "input_type": "free_text",
            "field": "appearance_prompt_or_photo",
            "prompt_text": "🎭 *Update Appearance*\n\nDescribe the new visual style or upload a reference photo:",
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
