"""
OpenClaw Telegram skill catalog.

This module defines the menu-driven Telegram/OpenClaw skill surface for the
future `/media` bot entrypoint.

Important:
- this file defines the skill catalog first
- it does NOT mean the Telegram router is already implemented
- it does NOT mean every API entrypoint already exists
- menu-driven collection is the default UX, but creative leaf skills may still
  accept optional freeform user text to refine the output without replacing
  required structured fields

This is a design registry for skill-first planning before Telegram integration.
"""

from __future__ import annotations

from typing import Any, Dict, List


OPENCLAW_TELEGRAM_SKILL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "media": {
        "name": "MediaHub",
        "command": "/media",
        "role": "Top-level Telegram media menu",
        "description": (
            "Act as the main Telegram entrypoint. Present the operator with the"
            " top-level menu for image creation, video creation, carousel,"
            " long-form post, and management utilities."
        ),
        "status": "defined_only",
        "kind": "entrypoint",
        "parent": None,
        "menu_options": [
            {"skill": "image-menu", "label": "Create Image", "emoji": "🖼️"},
            {"skill": "video-menu", "label": "Create Video", "emoji": "🎬"},
            {"skill": "carousel", "label": "Carousel", "emoji": "🎠"},
            {"skill": "long-post", "label": "Long Post", "emoji": "📝"},
            {"skill": "manage-menu", "label": "Manage", "emoji": "⚙️"},
        ],
        "required_params": [],
        "optional_params": [],
        "internal_skills": [],
        "api_call": None,
        "output": "Telegram menu selection",
        "implementation_priority": 0,
        "integration_note": (
            "Define the skill first. Integrate with Telegram command routing later."
        ),
    },
    "image-menu": {
        "name": "ImageMenu",
        "command": "/media",
        "role": "Image submenu",
        "description": (
            "Present image creation choices for marketing posters, scene images,"
            " and avatar images."
        ),
        "status": "defined_only",
        "kind": "menu",
        "parent": "media",
        "menu_options": [
            {"skill": "image-poster", "label": "Marketing Poster", "emoji": "🎨"},
            {"skill": "image-scene", "label": "Scene/Slideshow", "emoji": "🖼️"},
            {"skill": "image-avatar", "label": "Avatar", "emoji": "👤"},
        ],
        "required_params": [],
        "optional_params": [],
        "internal_skills": [],
        "api_call": None,
        "output": "Telegram submenu selection",
        "implementation_priority": 0,
        "integration_note": "Menu layer only. No direct backend execution.",
    },
    "image-poster": {
        "name": "ImagePoster",
        "command": "/media",
        "role": "Generate marketing poster images",
        "description": (
            "Generate a premium marketing poster image using a template-aware"
            " poster prompt flow."
        ),
        "status": "defined_with_backing_gap",
        "kind": "leaf",
        "parent": "image-menu",
        "menu_options": [],
        "required_params": ["topic_or_brief"],
        "optional_params": [
            "style",
            "tone",
            "cta_text",
            "app_name",
            "aspect_ratio",
            "freeform_brief",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["freeform_brief", "creative_notes"],
            "note": (
                "Menu fields define the guardrails. Freeform text refines the"
                " poster output but does not replace required structured inputs."
            ),
        },
        "internal_skills": [
            "image",
            "r2-storage",
        ],
        "api_call": {
            "target": "POST /api/media/generate/image",
            "current_repo_support": True,
            "note": (
                "Can reuse the existing image endpoint. Poster-specific prompting"
                " and template policy still need to be implemented in the bot/router layer."
            ),
        },
        "output": "Poster image URL returned to Telegram",
        "implementation_priority": 1,
        "integration_note": "Skill is defined first. Telegram integration comes later.",
        "steps": [
            "collect_brief",
            "choose_style",
            "choose_tone",
            "generate_preview",
            "confirm_or_regenerate",
            "store_asset",
        ],
        "session_shape": {
            "step_key": "collect_brief",
            "collected": {
                "topic_or_brief": None,
                "style": None,
                "tone": None,
                "cta_text": None,
                "app_name": None,
                "aspect_ratio": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "preview_image_url": None,
                "final_image_url": None,
                "storage_key": None,
            },
        },
    },
    "image-scene": {
        "name": "ImageScene",
        "command": "/media",
        "role": "Generate scene or slideshow images",
        "description": (
            "Generate scene images for slideshow or media lanes using scene-aware"
            " prompt shaping."
        ),
        "status": "implemented_backing",
        "kind": "leaf",
        "parent": "image-menu",
        "menu_options": [],
        "required_params": ["topic_or_prompt"],
        "optional_params": [
            "style",
            "tone",
            "persona_id",
            "aspect_ratio",
            "scene_type",
            "freeform_brief",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["freeform_brief", "creative_notes"],
            "note": (
                "Scene generation keeps menu-driven scope, but the operator can"
                " still add extra visual direction in plain text."
            ),
        },
        "internal_skills": [
            "image",
            "r2-storage",
        ],
        "api_call": {
            "target": "POST /api/media/generate/image",
            "current_repo_support": True,
        },
        "output": "Scene image URL returned to Telegram",
        "implementation_priority": 1,
        "integration_note": "Backend exists. Menu/router still needs to be built.",
        "steps": [
            "collect_prompt",
            "choose_style",
            "choose_tone",
            "generate_preview",
            "confirm_or_regenerate",
            "store_asset",
        ],
        "session_shape": {
            "step_key": "collect_prompt",
            "collected": {
                "topic_or_prompt": None,
                "style": None,
                "tone": None,
                "persona_id": None,
                "aspect_ratio": None,
                "scene_type": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "preview_image_url": None,
                "final_image_url": None,
                "storage_key": None,
            },
        },
    },
    "image-avatar": {
        "name": "ImageAvatar",
        "command": "/media",
        "role": "Generate avatar images for personas",
        "description": (
            "Generate or regenerate avatar still images for persona bootstrap."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "image-menu",
        "menu_options": [],
        "required_params": ["persona_id_or_new_id"],
        "optional_params": [
            "appearance_prompt",
            "photo_upload",
            "style",
            "identity_notes",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["appearance_prompt", "identity_notes", "creative_notes"],
            "note": (
                "Avatar generation stays anchored to persona identity fields, but"
                " still allows open text notes for look-and-feel refinement."
            ),
        },
        "internal_skills": [
            "image",
            "r2-storage",
            "persona-setup",
        ],
        "api_call": {
            "target": "POST /api/media/generate/image",
            "current_repo_support": True,
            "note": (
                "Image generation exists, but a complete persona-avatar bot flow"
                " and DB-backed registry do not yet exist."
            ),
        },
        "output": "Avatar preview URL returned to Telegram",
        "implementation_priority": 2,
        "integration_note": "Use later inside persona setup and video persona flows.",
        "steps": [
            "collect_persona_reference",
            "collect_appearance",
            "generate_preview",
            "confirm_or_regenerate",
            "store_asset",
        ],
        "session_shape": {
            "step_key": "collect_persona_reference",
            "collected": {
                "persona_id_or_new_id": None,
                "appearance_prompt": None,
                "photo_upload": None,
                "style": None,
                "identity_notes": None,
                "creative_notes": None,
            },
            "artifacts": {
                "preview_image_url": None,
                "final_image_url": None,
                "storage_key": None,
            },
        },
    },
    "video-menu": {
        "name": "VideoMenu",
        "command": "/media",
        "role": "Video submenu",
        "description": (
            "Present video creation choices for AI influencer and tutorial videos."
        ),
        "status": "defined_only",
        "kind": "menu",
        "parent": "media",
        "menu_options": [
            {"skill": "video-ai", "label": "AI Influencer", "emoji": "🎭"},
            {"skill": "video-tutorial", "label": "Tutorial", "emoji": "📱"},
        ],
        "required_params": [],
        "optional_params": [],
        "internal_skills": [],
        "api_call": None,
        "output": "Telegram submenu selection",
        "implementation_priority": 0,
        "integration_note": "Menu layer only. No direct backend execution.",
    },
    "video-ai": {
        "name": "VideoAI",
        "command": "/media",
        "role": "Generate AI influencer videos",
        "description": (
            "Run the full AI influencer video lane after collecting persona,"
            " topic, tone, and platform."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "video-menu",
        "menu_options": [],
        "required_params": ["persona_id", "topic", "tone"],
        "optional_params": [
            "platform",
            "duration_target",
            "hook_idea",
            "freeform_brief",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["hook_idea", "freeform_brief", "creative_notes"],
            "note": (
                "Persona, topic, and tone stay structured. The operator may still"
                " add hook ideas or extra prompt notes before script generation."
            ),
        },
        "internal_skills": [
            "persona-picker",
            "script-gen",
            "google-tts",
            "image",
            "heygen-video",
            "ffmpeg-assembly",
            "r2-storage",
            "telegram-approval",
            "postiz-publish",
        ],
        "api_call": {
            "target": "POST /api/workflows/start-video",
            "current_repo_support": False,
            "note": (
                "This is the desired workflow entrypoint. The repo does not yet"
                " expose a dedicated start-video endpoint."
            ),
        },
        "output": "Final video URL returned to Telegram",
        "implementation_priority": 5,
        "integration_note": "Highest complexity. Define first, integrate last.",
        "steps": [
            "pick_persona",
            "collect_topic",
            "choose_tone",
            "choose_platform",
            "generate_script",
            "approve_script",
            "generate_media",
            "assemble_video",
            "approve_video",
            "publish_or_finish",
        ],
        "session_shape": {
            "step_key": "pick_persona",
            "collected": {
                "persona_id": None,
                "topic": None,
                "tone": None,
                "platform": None,
                "duration_target": None,
                "hook_idea": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "script_id": None,
                "script_preview": None,
                "audio_url": None,
                "scene_image_urls": [],
                "heygen_video_url": None,
                "final_video_url": None,
                "storage_key": None,
            },
        },
    },
    "video-tutorial": {
        "name": "VideoTutorial",
        "command": "/media",
        "role": "Generate tutorial videos",
        "description": (
            "Build tutorial scenes, generate supporting media, and return a final"
            " tutorial video."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "video-menu",
        "menu_options": [],
        "required_params": ["topic"],
        "optional_params": [
            "persona_id",
            "tone",
            "platform",
            "freeform_brief",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["freeform_brief", "creative_notes"],
            "note": (
                "Tutorial flow still collects structured topic and platform data,"
                " but allows extra free text for tutorial angle or constraints."
            ),
        },
        "internal_skills": [
            "persona-picker",
            "scene-builder",
            "google-tts",
            "image",
            "heygen-video",
            "ffmpeg-assembly",
            "r2-storage",
            "telegram-approval",
            "postiz-publish",
        ],
        "api_call": {
            "target": "POST /api/workflows/start-tutorial",
            "current_repo_support": False,
            "note": (
                "This is the desired workflow entrypoint. The repo does not yet"
                " expose a dedicated start-tutorial endpoint."
            ),
        },
        "output": "Final tutorial video URL returned to Telegram",
        "implementation_priority": 4,
        "integration_note": "Define now. Integrate after simpler media skills.",
        "steps": [
            "pick_persona",
            "collect_topic",
            "choose_tone",
            "choose_platform",
            "build_scenes",
            "generate_media",
            "assemble_video",
            "approve_video",
            "publish_or_finish",
        ],
        "session_shape": {
            "step_key": "collect_topic",
            "collected": {
                "persona_id": None,
                "topic": None,
                "tone": None,
                "platform": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "scene_bundle_id": None,
                "audio_url": None,
                "scene_image_urls": [],
                "heygen_video_url": None,
                "final_video_url": None,
                "storage_key": None,
            },
        },
    },
    "carousel": {
        "name": "Carousel",
        "command": "/media",
        "role": "Generate carousel content",
        "description": (
            "Generate slide planning JSON plus matching images for a carousel flow."
        ),
        "status": "implemented_backing",
        "kind": "leaf",
        "parent": "media",
        "menu_options": [],
        "required_params": ["topic", "platform"],
        "optional_params": [
            "persona_id",
            "tone",
            "num_slides",
            "freeform_brief",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["freeform_brief", "creative_notes"],
            "note": (
                "Carousel uses structured persona/topic/platform fields first, but"
                " still allows extra positioning or message notes from the user."
            ),
        },
        "internal_skills": [
            "persona-picker",
            "carousel-plan",
            "image",
            "r2-storage",
            "telegram-approval",
            "postiz-publish",
        ],
        "api_call": {
            "target": "POST /api/media/carousel",
            "current_repo_support": False,
            "note": (
                "The planning activity exists, but the repo does not yet expose a"
                " dedicated carousel endpoint."
            ),
        },
        "output": "Slides JSON plus image URLs for Telegram or Postiz",
        "implementation_priority": 2,
        "integration_note": "One of the earliest OpenClaw Telegram skills to build.",
        "steps": [
            "pick_persona",
            "collect_topic",
            "choose_platform",
            "choose_slide_count",
            "choose_tone",
            "generate_plan",
            "generate_images",
            "preview",
            "publish_or_finish",
        ],
        "session_shape": {
            "step_key": "pick_persona",
            "collected": {
                "persona_id": None,
                "topic": None,
                "platform": None,
                "tone": None,
                "num_slides": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "slides_json": None,
                "image_urls": [],
                "storage_keys": [],
            },
        },
    },
    "long-post": {
        "name": "LongPost",
        "command": "/media",
        "role": "Generate long-form post content",
        "description": (
            "Generate long-form content JSON plus a hero image for downstream"
            " review and publishing."
        ),
        "status": "implemented_backing",
        "kind": "leaf",
        "parent": "media",
        "menu_options": [],
        "required_params": ["topic", "platform"],
        "optional_params": [
            "persona_id",
            "tone",
            "freeform_brief",
            "creative_notes",
        ],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["freeform_brief", "creative_notes"],
            "note": (
                "Long-post generation stays scoped by platform and topic, but may"
                " still use extra user notes to refine the angle or message."
            ),
        },
        "internal_skills": [
            "persona-picker",
            "long-post-plan",
            "image",
            "r2-storage",
            "telegram-approval",
            "postiz-publish",
        ],
        "api_call": {
            "target": "POST /api/media/long-post",
            "current_repo_support": False,
            "note": (
                "The long-post planning activity exists, but the repo does not yet"
                " expose a dedicated long-post endpoint."
            ),
        },
        "output": "Content JSON plus hero image URL for Telegram or Postiz",
        "implementation_priority": 3,
        "integration_note": "Medium complexity. Build after carousel.",
        "steps": [
            "pick_persona",
            "collect_topic",
            "choose_platform",
            "choose_tone",
            "generate_content",
            "generate_hero_image",
            "preview",
            "publish_or_finish",
        ],
        "session_shape": {
            "step_key": "pick_persona",
            "collected": {
                "persona_id": None,
                "topic": None,
                "platform": None,
                "tone": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "content_json": None,
                "hero_image_url": None,
                "storage_key": None,
            },
        },
    },
    "manage-menu": {
        "name": "ManageMenu",
        "command": "/media",
        "role": "Management submenu",
        "description": (
            "Present management utilities for personas, quota, weekly planning,"
            " and publish queue."
        ),
        "status": "defined_only",
        "kind": "menu",
        "parent": "media",
        "menu_options": [
            {"skill": "persona-manager", "label": "Personas", "emoji": "👤"},
            {"skill": "quota-inspector", "label": "Quota", "emoji": "📊"},
            {"skill": "weekly-planner", "label": "Weekly Plan", "emoji": "📅"},
            {"skill": "publish-manager", "label": "Publish Queue", "emoji": "📤"},
        ],
        "required_params": [],
        "optional_params": [],
        "internal_skills": [],
        "api_call": None,
        "output": "Telegram submenu selection",
        "implementation_priority": 0,
        "integration_note": "Menu layer only. Define now, integrate later.",
    },
    "persona-picker": {
        "name": "PersonaPicker",
        "command": None,
        "role": "Reusable persona selection helper",
        "description": (
            "Provide a shared, status-aware persona picker used by video,"
            " carousel, long-post, and persona management flows."
        ),
        "status": "defined_only",
        "kind": "helper",
        "parent": None,
        "menu_options": [],
        "required_params": [],
        "optional_params": ["ready_only", "allow_create_new"],
        "internal_skills": [
            "persona-setup",
        ],
        "api_call": {
            "target": "DB query: personas registry",
            "current_repo_support": False,
            "note": "The repo does not yet have a shared DB-backed Telegram persona picker.",
        },
        "output": "Selected persona ID and summary card",
        "implementation_priority": 2,
        "integration_note": "Helper skill. Reuse across multiple menu flows.",
    },
    "persona-manager": {
        "name": "PersonaManager",
        "command": "/media",
        "role": "Persona management submenu",
        "description": (
            "Present persona management actions such as creating a new persona or"
            " inspecting and rebuilding existing personas."
        ),
        "status": "defined_only",
        "kind": "menu",
        "parent": "manage-menu",
        "menu_options": [
            {"skill": "persona-creator", "label": "Create Persona", "emoji": "➕"},
            {"skill": "persona-inspector", "label": "Inspect Personas", "emoji": "📋"},
        ],
        "required_params": [],
        "optional_params": ["persona_id"],
        "internal_skills": [],
        "api_call": None,
        "output": "Persona management submenu selection",
        "implementation_priority": 2,
        "integration_note": "Define first. Route into creator or inspector later.",
    },
    "persona-creator": {
        "name": "PersonaCreator",
        "command": "/media",
        "role": "Create a new persona step by step",
        "description": (
            "Collect persona identity, language, voice, appearance prompt or photo,"
            " generate an avatar preview, then register and save the persona."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "persona-manager",
        "menu_options": [],
        "required_params": [
            "persona_id",
            "language",
            "voice",
            "appearance_prompt_or_photo",
        ],
        "optional_params": ["identity_notes", "creative_notes"],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": [
                "appearance_prompt_or_photo",
                "identity_notes",
                "creative_notes",
            ],
            "note": (
                "Persona creation keeps language and voice structured, but still"
                " accepts open text to describe identity or visual nuances."
            ),
        },
        "internal_skills": [
            "image",
            "heygen-video",
            "r2-storage",
            "persona-setup",
        ],
        "api_call": {
            "target": "Future persona registry endpoints",
            "current_repo_support": False,
            "note": (
                "The setup/check scripts exist, but the repo does not yet expose"
                " a full DB-backed persona creation API."
            ),
        },
        "output": "Ready persona record plus reusable avatar identifiers",
        "implementation_priority": 3,
        "integration_note": "Define now. Integrate after persona registry endpoints exist.",
        "steps": [
            "collect_persona_id",
            "choose_language",
            "choose_voice",
            "collect_appearance",
            "preview_avatar",
            "register_heygen",
            "save_db",
        ],
        "session_shape": {
            "step_key": "collect_persona_id",
            "collected": {
                "persona_id": None,
                "language": None,
                "voice": None,
                "appearance_prompt_or_photo": None,
                "identity_notes": None,
                "creative_notes": None,
            },
            "artifacts": {
                "preview_image_url": None,
                "avatar_image_url": None,
                "heygen_avatar_id": None,
            },
        },
    },
    "persona-inspector": {
        "name": "PersonaInspector",
        "command": "/media",
        "role": "List, inspect, and rebuild existing personas",
        "description": (
            "Show status-aware persona cards and allow inspect, use, or rebuild actions."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "persona-manager",
        "menu_options": [],
        "required_params": [],
        "optional_params": ["persona_id"],
        "internal_skills": [
            "persona-picker",
            "persona-setup",
            "image",
            "heygen-video",
            "r2-storage",
        ],
        "api_call": {
            "target": "Future persona registry endpoints",
            "current_repo_support": False,
            "note": "Current repo only has setup/check scripts, not a full persona registry API.",
        },
        "output": "Persona status cards and persona actions",
        "implementation_priority": 2,
        "integration_note": "Needs DB-backed persona layer before Telegram integration.",
        "steps": [
            "list_personas",
            "select_persona",
            "view_details_or_rebuild",
        ],
        "session_shape": {
            "step_key": "list_personas",
            "collected": {
                "persona_id": None,
            },
            "artifacts": {
                "persona_summary": None,
                "available_personas": [],
            },
        },
    },
    "quota-inspector": {
        "name": "QuotaInspector",
        "command": "/media",
        "role": "Inspect provider usage and readiness",
        "description": (
            "Show quota state and use it to gate expensive actions before execution."
        ),
        "status": "implemented_backing",
        "kind": "leaf",
        "parent": "manage-menu",
        "menu_options": [],
        "required_params": [],
        "optional_params": ["provider"],
        "internal_skills": [
            "quota-monitor",
        ],
        "api_call": {
            "target": "GET /api/quota/*",
            "current_repo_support": True,
        },
        "output": "Quota summary or provider detail view in Telegram",
        "implementation_priority": 1,
        "integration_note": "Good early management skill to wire first.",
        "steps": [
            "choose_provider_or_summary",
            "fetch_quota",
            "render_quota_view",
        ],
        "session_shape": {
            "step_key": "choose_provider_or_summary",
            "collected": {
                "provider": None,
            },
            "artifacts": {
                "quota_summary": None,
                "quota_detail": None,
            },
        },
    },
    "weekly-planner": {
        "name": "WeeklyPlanner",
        "command": "/media",
        "role": "Create weekly content strategy",
        "description": (
            "Generate a weekly plan and route it through approval and publishing lanes."
        ),
        "status": "implemented_backing",
        "kind": "leaf",
        "parent": "manage-menu",
        "menu_options": [],
        "required_params": ["brand_config"],
        "optional_params": ["user_id", "freeform_brief"],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["freeform_brief"],
            "note": (
                "Weekly planning is anchored on brand config, but the operator may"
                " still add a short planning brief or campaign note."
            ),
        },
        "internal_skills": [
            "weekly-plan",
            "telegram-approval",
            "postiz-publish",
        ],
        "api_call": {
            "target": "POST /api/workflows/start-weekly",
            "current_repo_support": True,
        },
        "output": "Workflow start confirmation and weekly plan approval path",
        "implementation_priority": 2,
        "integration_note": "Already has a backing workflow API.",
        "steps": [
            "collect_brand_config",
            "start_workflow",
            "await_approval",
        ],
        "session_shape": {
            "step_key": "collect_brand_config",
            "collected": {
                "brand_config": None,
                "user_id": None,
                "freeform_brief": None,
            },
            "artifacts": {
                "workflow_id": None,
                "run_id": None,
            },
        },
    },
    "publish-manager": {
        "name": "PublishManager",
        "command": "/media",
        "role": "Inspect or manage publish queue",
        "description": (
            "Inspect pending publish items and trigger publish or schedule actions."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "manage-menu",
        "menu_options": [],
        "required_params": [],
        "optional_params": ["content_id"],
        "internal_skills": [
            "postiz-publish",
        ],
        "api_call": {
            "target": "Future publish queue endpoints",
            "current_repo_support": False,
            "note": (
                "Publish capabilities exist, but a dedicated Telegram-facing queue"
                " management endpoint is not yet defined."
            ),
        },
        "output": "Publish queue cards and publish actions",
        "implementation_priority": 3,
        "integration_note": "Define now. Integrate after queue/list endpoints exist.",
        "steps": [
            "list_publish_queue",
            "select_item",
            "publish_or_schedule",
        ],
        "session_shape": {
            "step_key": "list_publish_queue",
            "collected": {
                "content_id": None,
            },
            "artifacts": {
                "queue_items": [],
                "publish_result": None,
            },
        },
    },
}


def get_openclaw_telegram_skill(skill_name: str) -> Dict[str, Any]:
    """Return a Telegram/OpenClaw skill definition by key."""
    return OPENCLAW_TELEGRAM_SKILL_REGISTRY.get(skill_name, {})


def list_openclaw_telegram_skills() -> List[str]:
    """List all available Telegram/OpenClaw skill keys."""
    return list(OPENCLAW_TELEGRAM_SKILL_REGISTRY.keys())
