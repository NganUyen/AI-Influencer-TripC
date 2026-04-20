"""
OpenClaw Telegram skill catalog.

This module defines the menu-driven Telegram/OpenClaw skill surface for the
future `/media` bot entrypoint.

Important:
- this file defines the skill catalog first
- it does NOT mean the Telegram router is already implemented
- some API entrypoints already exist and should be used as the canonical
  backend contracts for future Telegram/OpenClaw integration
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
    "daily-story": {
        "name": "DailyStory",
        "command": "/media",
        "role": "Generate daily story draft and transition to media",
        "description": "Interactive flow to generate a daily story draft and select the media format.",
        "status": "implemented_backing",
        "kind": "leaf",
        "parent": "media",
        "menu_options": [],
        "required_params": ["persona_id", "topic"],
        "optional_params": ["app_name", "feedback", "media_action"],
        "input_contract": {
            "mode": "structured_with_optional_freeform",
            "freeform_fields": ["feedback"],
            "note": "Collects topic and optional feedback to regenerate the text.",
        },
        "internal_skills": ["persona-picker"],
        "api_call": {
            "target": "Direct AIService Prompt",
            "current_repo_support": True,
        },
        "output": "A generated story draft and a transition action",
        "implementation_priority": 1,
        "integration_note": "A custom flow added to bridge the Daily Story with the other media modes.",
        "steps": [
            "pick_persona",
            "collect_content",
            "generate_draft",
            "choose_media_action",
        ],
        "session_shape": {
            "step_key": "pick_persona",
            "collected": {
                "persona_id": None,
                "topic": None,
                "feedback": None,
                "media_action": None,
            },
            "artifacts": {"story_draft": None, "story_body": None},
        },
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
        "status": "implemented_backing",
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
        "integration_note": "Backend and Telegram poster flow are wired for the studio menu.",
        "steps": [
            "collect_brief",
            "choose_style",
            "choose_tone",
            "choose_ratio",
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
        "required_params": ["topic_or_prompt", "style", "aspect_ratio"],
        "optional_params": [
            "persona_id",
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
        "integration_note": "Backend and Telegram batch-selection flow are wired.",
        "steps": [
            "collect_prompt",
            "choose_style",
            "choose_ratio",
            "generating_candidates",
            "confirm_or_regenerate",
            "selecting_images",
        ],
        "session_shape": {
            "step_key": "collect_prompt",
            "collected": {
                "topic_or_prompt": None,
                "style": None,
                "persona_id": None,
                "aspect_ratio": None,
                "scene_type": None,
                "freeform_brief": None,
                "creative_notes": None,
            },
            "artifacts": {
                "image_candidates": [],
                "selected_candidate_index": None,
                "selected_candidate_indexes": [],
                "preview_image_url": None,
                "final_image_url": None,
                "final_image_urls": [],
                "storage_key": None,
                "final_storage_keys": [],
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
            "freeform_fields": [
                "appearance_prompt",
                "identity_notes",
                "creative_notes",
            ],
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
                "Image generation exists. Persona registry APIs also exist, but"
                " the Telegram persona setup flow is not fully wired yet."
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
        "role": "Prepare AI influencer video concepts before production",
        "description": (
            "Collect a video idea brief OR upload a recorded demo video, normalize it into an approved concept,"
            " generate an approved beat sheet, and hand the approved package"
            " into the production workflow from Telegram."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "video-menu",
        "menu_options": [],
        "required_params": [
            "persona_id",
            "video_goal",
            "audience",
            "cta",
            "reference_url",
            "access_level",
        ],
        "optional_params": [
            "platform",
            "creative_input_mode",
            "idea_brief",
            "feature_focus",
            "demo_video_telegram_file_id",
            "demo_video_asset_url",
            "feature_emphasis",
        ],
        "input_contract": {
            "mode": "structured_idea_brief_or_demo_video",
            "freeform_fields": [
                "idea_brief",
                "feature_focus",
                "feature_emphasis",
                "audience",
                "cta",
            ],
            "note": (
                "The Telegram flow supports two input modes: idea_brief (original) and recorded_demo_video (new)."
                " In idea_brief mode: idea_brief and feature_focus are required."
                " In recorded_demo_video mode: demo_video_telegram_file_id is required, feature_focus becomes optional feature_emphasis."
                " OpenClaw is used to normalize the collected brief into a ConceptBrief and BeatSheet after required fields are collected."
            ),
        },
        "internal_skills": [
            "persona-picker",
            "creative-director",
        ],
        "api_call": {
            "target": "Internal CreativeDirectorService + POST /api/workflows/start-video",
            "current_repo_support": True,
            "note": (
                "The Telegram flow stores the approved package, then starts the"
                " short-video production workflow and keeps the session attached"
                " for cancel/status actions."
            ),
        },
        "output": "Approved production package plus active production workflow session",
        "implementation_priority": 3,
        "integration_note": "Pre-production review now hands off directly into the live production workflow. Phase 2 adds recorded_demo_video mode.",
        "steps": [
            "collect_objective",
            "collect_target_url",
            "website_review",
            "pick_persona",
            "choose_execution_mode",
            "confirm_plan",
            "upload_demo_video",
            "collect_reference_url",
            "collect_user_video_thesis",
            "choose_content_scope",
            "collect_idea_brief",
            "collect_feature_focus",
            "collect_feature_emphasis",
            "choose_video_goal",
            "collect_audience",
            "collect_cta",
            "collect_official_name_hint",
            "collect_must_not_say",
            "choose_access_level",
            "demo_preview_confirm",
            "demo_pick_alternate_focus",
            "demo_rewrite_main_idea",
            "collect_desired_takeaway",
            "confirm_concept",
            "confirm_beats",
        ],
        "session_shape": {
            "step_key": "collect_objective",
            "collected": {
                "objective": None,
                "target_url": None,
                "creative_input_mode": None,
                "persona_id": None,
                "execution_mode": None,
                "plan_decision": None,
                "demo_video_telegram_file_id": None,
                "demo_video_asset_url": None,
                "reference_url": None,
                "user_video_thesis": None,
                "content_scope": None,
                "idea_brief": None,
                "feature_focus": None,
                "feature_emphasis": None,
                "video_goal": None,
                "audience": None,
                "cta": None,
                "official_name_hint": None,
                "must_not_say": None,
                "access_level": None,
                "demo_preview_action": None,
                "alternate_feature_focus": None,
                "rewritten_main_idea": None,
                "desired_takeaway": None,
                "user_confirmed_main_idea": None,
                "platform": "tiktok",
            },
            "artifacts": {
                "persona_snapshot": None,
                "page_review": None,
                "video_review_plan": None,
                "credential_handoff": None,
                "plan_confirmed": False,
                "demo_evidence": None,
                "demo_preview_summary": None,
                "concept_brief": None,
                "beat_sheet": None,
                "approved_production_package": None,
                "concept_approved": False,
                "beat_sheet_approved": False,
            },
        },
    },
    "video-planner": {
        "name": "VideoPlanner",
        "command": "/start",
        "role": "Planning-first Telegram entrypoint for video execution",
        "description": (
            "Collect the user's objective, target URL, language, persona, and execution mode, "
            "then produce a reviewable video plan before any production workflow starts."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": None,
        "menu_options": [],
        "required_params": [
            "objective",
            "target_url",
            "language",
            "persona_id",
            "execution_mode",
        ],
        "optional_params": ["plan_decision"],
        "input_contract": {
            "mode": "structured_conversational_planner",
            "freeform_fields": ["objective", "target_url", "language"],
            "note": (
                "This planner is the new plain /start experience. It captures planning inputs first and waits for explicit confirmation before execution."
            ),
        },
        "internal_skills": ["persona-picker", "creative-director"],
        "api_call": {
            "target": "Internal Telegram planner state machine",
            "current_repo_support": True,
            "note": (
                "Step 2 only collects and stores the review plan. URL fetching and workflow execution land in later implementation steps."
            ),
        },
        "output": "Confirmed video review plan",
        "implementation_priority": 1,
        "integration_note": "Designed to replace menu-only /start with a planning-first Telegram flow.",
        "steps": [
            "collect_objective",
            "collect_target_url",
            "choose_language",
            "pick_persona",
            "choose_execution_mode",
            "confirm_plan",
        ],
        "session_shape": {
            "step_key": "collect_objective",
            "collected": {
                "objective": None,
                "target_url": None,
                "language": None,
                "persona_id": None,
                "execution_mode": None,
                "plan_decision": None,
            },
            "artifacts": {
                "page_review": None,
                "video_review_plan": None,
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
        "status": "deferred",
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
                "Deferred for now. This overlaps heavily with the existing"
                " short-video lane, and the repo does not expose a dedicated"
                " start-tutorial endpoint."
            ),
        },
        "output": "Final tutorial video URL returned to Telegram",
        "implementation_priority": 4,
        "integration_note": (
            "Deferred. Keep documented, but do not implement during the current"
            " OpenClaw integration phase."
        ),
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
            "current_repo_support": True,
            "note": (
                "Canonical carousel entrypoint. It generates slide strategy,"
                " renders slide images, overlays text, and uploads the final"
                " carousel artifact to storage."
            ),
        },
        "output": "Slides JSON plus rendered image URLs for Telegram or Postiz",
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
        "status": "deferred",
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
                "Deferred for now. The planning activity exists, but the repo"
                " does not yet expose a dedicated long-post endpoint."
            ),
        },
        "output": "Content JSON plus hero image URL for Telegram or Postiz",
        "implementation_priority": 3,
        "integration_note": (
            "Deferred. Keep documented, but do not implement during the current"
            " OpenClaw integration phase."
        ),
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
            "current_repo_support": True,
            "note": (
                "Use the persona API surface as the canonical backing contract:"
                " GET /api/personas and GET /api/personas/{persona_id}/readiness."
                " A Telegram picker UI still needs to be built."
            ),
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
                "preview_command",
            ],
            "note": (
                "Persona creation keeps language and voice structured, but still"
                " accepts open text to describe identity or visual nuances. "
                "The preview_command field allows jumping to edit steps."
            ),
        },
        "internal_skills": [
            "image",
            "heygen-video",
            "r2-storage",
            "persona-setup",
        ],
        "api_call": {
            "target": (
                "POST /api/personas + PATCH /api/personas/{persona_id} +"
                " GET /api/personas/{persona_id}/readiness"
            ),
            "current_repo_support": True,
            "note": (
                "Persona CRUD/readiness APIs exist. Full avatar upload/HeyGen"
                " registration orchestration is still only partially exposed at"
                " the Telegram skill layer."
            ),
        },
        "output": "Ready persona record plus reusable avatar identifiers",
        "implementation_priority": 3,
        "integration_note": "Define now. Integrate after persona registry endpoints exist.",
        "steps": [
            "choose_creation_mode",
            "collect_nationality",
            "choose_voice",
            "collect_dream_brief",
            "confirm_dream",
            "collect_persona_id",
            "choose_language",
            "collect_appearance",
            "preview_avatar",
            "register_heygen",
            "save_db",
        ],
        "session_shape": {
            "step_key": "choose_creation_mode",
            "collected": {
                "creation_mode": None,
                "nationality": None,
                "dream_brief": None,
                "persona_id": None,
                "language": "English",
                "voice": None,
                "appearance_prompt_or_photo": None,
                "identity_notes": None,
                "creative_notes": None,
                "preview_command": None,
            },
            "artifacts": {
                "dream_ready": False,
                "dream_summary": None,
                "preview_image_url": None,
                "avatar_image_url": None,
                "heygen_avatar_id": None,
                "voice_search_feedback": None,
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
            "target": (
                "GET /api/personas + GET /api/personas/{persona_id} +"
                " GET /api/personas/{persona_id}/readiness +"
                " PATCH /api/personas/{persona_id}"
            ),
            "current_repo_support": True,
            "note": (
                "Persona registry and readiness APIs exist. Telegram-facing"
                " inspect/rebuild UX still needs to be built on top."
            ),
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
            "Inspect Postiz wiring, retry failed publishes, and manage GrowChief engagement actions."
        ),
        "status": "partial",
        "kind": "leaf",
        "parent": "manage-menu",
        "menu_options": [],
        "required_params": [],
        "optional_params": ["content_id"],
        "internal_skills": [
            "postiz-publish",
            "growchief-engagement",
        ],
        "api_call": {
            "target": (
                "GET /api/content/list + GET /api/content/providers/{content_id} + "
                "POST /api/content/retry/{content_id} + "
                "GET /api/content/engagement/{content_id} + "
                "POST /api/content/engagement/{content_id}/trigger"
            ),
            "current_repo_support": True,
            "note": (
                "Queue inspection, provider wiring checks, retry, and manual"
                " engagement controls are available through content APIs."
            ),
        },
        "output": "Publish queue cards and publish actions",
        "implementation_priority": 3,
        "integration_note": "Telegram queue inspection is wired; deeper publish controls can come later.",
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
