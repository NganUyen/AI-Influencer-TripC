"""
App-review studio helpers for persona selection, generation jobs, uploads, and TikTok publishing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import asyncio
from datetime import timedelta
from time import perf_counter
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from uuid import uuid4

from temporalio.client import Client

from config.settings import settings
from services.account_connection_service import AccountConnectionService
from services.brand_profile_service import BrandProfileService
from services.content_persistence_service import ContentPersistenceService
from services.customer_auth_service import CustomerSession
from services.customer_campaign_service import CustomerCampaignService
from services.database_service import DatabaseService
from services.media_storage_service import MediaStorageService
from services.persona_registry_service import PersonaRegistryService
from services.publisher_service import PublisherService
from services.script_service import ScriptService
from services.telegram_link_service import TelegramLinkService
from services.workflow_state_service import WorkflowStateService
from services.contracts import (
    SceneContract,
    ScriptContract,
    VideoAudioPolicyContract,
    VideoReviewPlanContract,
    VideoWorkflowPersonaSnapshotContract,
    VideoWorkflowStartPayloadContract,
    WebPageReviewContract,
)
from services.website_review_service import WebsiteReviewService
from services.video_planning_service import VideoPlanningService


_SYSTEM_PERSONA_USER_ID = "00000000-0000-0000-0000-000000000001"
_APP_REVIEW_JOB_TYPES = {"app_review_video", "app_review_upload"}
logger = logging.getLogger(__name__)

_MUSIC_MOOD_TO_BGM_PROFILE = {
    "none": "product_explainer",
    "upbeat": "upbeat_demo",
    "corporate": "product_explainer",
    "ambient": "calm_review",
    "cinematic": "cinematic_rise",
    "lo-fi": "lofi_focus",
    "lofi": "lofi_focus",
    "electronic": "electro_drive",
    "motivational": "motivational_lift",
    "focus": "focus_loop",
    "tropical": "tropical_pop",
}

_MOVEMENT_STYLE_TO_PROFILE = {
    "natural": "natural",
    "expressive": "expressive",
    "minimal": "minimal",
    "energetic": "energetic",
    "professional": "professional",
    "casual": "casual",
    "storytelling": "storytelling",
    "calm": "calm",
}
_DISABLED_MOVEMENT_TOKENS = {"", "none", "off", "disabled"}


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _slugify(value: str) -> str:
    normalized = "".join(
        ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip()
    )
    collapsed = "-".join(part for part in normalized.split("-") if part)
    return collapsed or "item"


def _data_svg_uri(
    *,
    title: str,
    subtitle: str,
    accent_a: str,
    accent_b: str,
    badge: str,
) -> str:
    svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="920" viewBox="0 0 720 920" fill="none">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{accent_a}"/>
      <stop offset="100%" stop-color="{accent_b}"/>
    </linearGradient>
  </defs>
  <rect width="720" height="920" rx="44" fill="url(#bg)"/>
  <rect x="42" y="42" width="636" height="836" rx="34" fill="rgba(8,12,20,0.18)" stroke="rgba(255,255,255,0.24)"/>
  <circle cx="360" cy="272" r="112" fill="rgba(255,255,255,0.16)"/>
  <circle cx="360" cy="240" r="54" fill="rgba(255,255,255,0.92)"/>
  <path d="M248 366c0-58 50-102 112-102s112 44 112 102v28H248z" fill="rgba(255,255,255,0.88)"/>
  <rect x="86" y="540" width="174" height="46" rx="23" fill="rgba(8,12,20,0.26)"/>
  <text x="173" y="571" text-anchor="middle" font-size="22" font-family="Tahoma, sans-serif" fill="#FFFFFF">{badge}</text>
  <text x="86" y="656" font-size="52" font-weight="700" font-family="Tahoma, sans-serif" fill="#FFFFFF">{title}</text>
  <text x="86" y="716" font-size="30" font-family="Tahoma, sans-serif" fill="rgba(255,255,255,0.92)">{subtitle}</text>
  <text x="86" y="812" font-size="24" font-family="Tahoma, sans-serif" fill="rgba(255,255,255,0.80)">AI Review Persona</text>
</svg>
""".strip()
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode(
        "ascii"
    )


def _caption_from_script(
    *,
    objective: str,
    page_title: str,
    persona: Dict[str, Any],
    script_payload: Dict[str, Any],
) -> str:
    script_text = str(script_payload.get("script") or "").strip()
    if len(script_text) > 220:
        script_text = script_text[:217].rstrip() + "..."
    market = str(persona.get("market_default") or "global").replace("_", " ").title()
    display_name = str(
        persona.get("display_name") or persona.get("persona_id") or "Host"
    )
    hashtags = [
        "#AppReview",
        "#TikTokReview",
        f"#{_slugify(page_title).replace('-', '')[:18] or 'app'}",
        f"#{_slugify(market).replace('-', '')[:18] or 'global'}",
    ]
    return (
        f"{display_name} reviews {page_title}.\n\n"
        f"{objective.strip() or 'AI-generated product review'}\n\n"
        f"{script_text}\n\n"
        f"{' '.join(dict.fromkeys(hashtags))}"
    ).strip()


def _build_master_contract_payload(script_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "language": "English",
        "script_text": str(script_payload.get("script") or "").strip(),
        "scenes_data": script_payload.get("scenes") or [],
        "duration_estimate": script_payload.get("duration_estimate") or 0,
    }


def _shared_contract_to_script_contract(shared_contract: Dict[str, Any]) -> ScriptContract:
    script_text = str(shared_contract.get("script_text") or "").strip()
    raw_scenes = shared_contract.get("scenes_data") or []
    scenes: List[SceneContract] = []
    current_second = 0.0
    for index, scene in enumerate(raw_scenes, start=1):
        if not isinstance(scene, dict):
            continue
        duration = float(
            scene.get("durationSeconds")
            or scene.get("duration_seconds")
            or scene.get("duration")
            or 6
        )
        description = str(
            scene.get("description")
            or scene.get("caption")
            or scene.get("scene_description")
            or scene.get("voiceover")
            or scene.get("script")
            or scene.get("text")
            or f"Scene {index}"
        ).strip()
        scenes.append(
            SceneContract(
                id=index,
                timestamp_start=current_second,
                timestamp_end=current_second + duration,
                caption=description[:80] or f"Scene {index}",
                narration_text=description,
                prompt=str(scene.get("prompt") or "Keep original visual prompt").strip() or "Keep original visual prompt",
                browser_action=str(scene.get("browser_action") or "Keep original browser action").strip() or "Keep original browser action",
                visual_success_criteria=str(scene.get("visual_success_criteria") or "Keep original visual success criteria").strip() or "Keep original visual success criteria",
                top_half_source_type=scene.get("top_half_source_type"),
                top_half_target=scene.get("top_half_target"),
                top_half_capture_hint=scene.get("top_half_capture_hint"),
                top_half_follow_links=bool(scene.get("top_half_follow_links", True)),
                top_half_max_capture_seconds=int(scene.get("top_half_max_capture_seconds") or max(5, min(120, round(duration)))),
                source_ref=scene.get("source_ref"),
            )
        )
        current_second += duration

    duration_estimate = float(shared_contract.get("duration_estimate") or current_second or 0)
    return ScriptContract(
        script=script_text,
        duration_estimate=duration_estimate,
        scenes=scenes,
    )


def _job_progress(status: str, current_step: Optional[str], has_video: bool) -> int:
    if has_video:
        return 100
    normalized_status = str(status or "").strip().lower()
    normalized_step = str(current_step or "").strip().lower()
    if normalized_status in {"completed", "save"}:
        return 100
    if normalized_status in {"failed", "discard", "rejected", "canceled", "cancelled"}:
        return 100
    step_map = {
        "generation_queued": 15,
        "awaiting_upload": 20,
        "generating_script": 30,
        "generating_top_half_and_audio": 50,
        "generating_talking_head": 65,
        "generating_top_half": 70,
        "assembling": 82,
        "waiting_final_decision": 92,
        "final_product_ready": 100,
    }
    return step_map.get(normalized_step, 10 if normalized_status == "running" else 0)


def _job_steps(
    status: str, current_step: Optional[str], has_video: bool
) -> List[Dict[str, Any]]:
    progress = _job_progress(status, current_step, has_video)
    if has_video:
        final_status = "completed"
    elif str(current_step or "").strip().lower() == "awaiting_upload":
        final_status = "pending"
    elif progress >= 80:
        final_status = "in_progress"
    else:
        final_status = "pending"
    return [
        {"key": "enter_url", "label": "Step 1: Enter URL", "status": "completed"},
        {
            "key": "choose_persona",
            "label": "Step 2: Choose Persona",
            "status": "completed",
        },
        {
            "key": "final_product",
            "label": "Step 3: Final Product",
            "status": final_status,
        },
    ]


def _merge_dict(
    base: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    merged = dict(base or {})
    merged.update(extra or {})
    return merged


def _coerce_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return {}
    return value if isinstance(value, dict) else {}


def _coerce_json_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    return value if isinstance(value, list) else []


def _audio_policy_from_creative_preferences(
    creative_preferences: Dict[str, Any],
) -> VideoAudioPolicyContract:
    payload = _coerce_json_dict(creative_preferences)
    music_mood = str(payload.get("music_mood") or "").strip().lower() or "none"
    requested_bgm_profile = str(payload.get("bgm_profile") or "").strip().lower()
    movement_style = str(payload.get("movement_style") or "").strip().lower()
    requested_movement_profile = (
        str(payload.get("movement_profile") or "").strip().lower()
    )

    bgm_profile = (
        requested_bgm_profile
        or _MUSIC_MOOD_TO_BGM_PROFILE.get(music_mood, "product_explainer")
    )
    bgm_enabled = music_mood != "none"

    movement_profile = "none"
    if requested_movement_profile in _MOVEMENT_STYLE_TO_PROFILE.values():
        movement_profile = requested_movement_profile
    elif movement_style in _MOVEMENT_STYLE_TO_PROFILE:
        movement_profile = _MOVEMENT_STYLE_TO_PROFILE[movement_style]
    elif (
        requested_movement_profile in _DISABLED_MOVEMENT_TOKENS
        or movement_style in _DISABLED_MOVEMENT_TOKENS
    ):
        movement_profile = "none"

    movement_enabled = movement_profile != "none"
    if movement_enabled:
        intensity = max(
            0.0,
            min(100.0, _coerce_float(payload.get("gesture_intensity"), 50.0)),
        )
        movement_overlay_volume = round(0.1 + ((intensity / 100.0) * 0.22), 3)
    else:
        movement_overlay_volume = 0.0

    return VideoAudioPolicyContract(
        voiceover_required=True,
        bgm_fallback_enabled=bgm_enabled,
        bgm_library_profile=bgm_profile,
        bgm_duck_under_voiceover=True,
        max_bgm_duration_seconds=60,
        movement_overlay_enabled=movement_enabled,
        movement_library_profile=movement_profile,
        movement_overlay_volume=movement_overlay_volume,
    )


def _plan_input_mode(plan: Dict[str, Any]) -> str:
    publish_settings = _coerce_json_dict(plan.get("publish_settings"))
    input_mode = str(publish_settings.get("input_mode") or "").strip().lower()
    if input_mode in {"ai_autonomous", "user_upload"}:
        return input_mode
    if str(plan.get("status") or "").strip().lower() == "upload_required":
        return "user_upload"
    return "ai_autonomous"


def _execution_mode_for_page_review(
    *,
    page_review_data: Dict[str, Any],
    input_mode: str,
) -> str:
    normalized_mode = str(input_mode or "ai_autonomous").strip().lower()
    if normalized_mode == "user_upload":
        return "manual_mobile_recording"
    access_level = str(page_review_data.get("access_level") or "unknown").strip()
    if bool(page_review_data.get("login_required")) or access_level in {
        "has_logged_in_access",
        "login_required_but_not_available",
    }:
        return "authenticated_pc_recording"
    return "autonomous_screen_recording"


def _coerce_page_review_contract(
    value: Any,
    *,
    fallback_url: str,
) -> Optional[WebPageReviewContract]:
    payload = _coerce_json_dict(value)
    if not payload:
        return None
    normalized_url = str(
        payload.get("normalized_url") or payload.get("target_url") or fallback_url
    ).strip()
    target_url = str(payload.get("target_url") or normalized_url or fallback_url).strip()
    if not normalized_url or not target_url:
        return None

    merged_payload = {
        **payload,
        "normalized_url": normalized_url,
        "target_url": target_url,
    }
    try:
        return WebPageReviewContract.model_validate(merged_payload)
    except Exception:
        logger.warning(
            "Invalid cached page review payload; falling back to live review",
            exc_info=True,
        )
        return None


class AppReviewStudioService:
    SYSTEM_PERSONA_USER_ID = _SYSTEM_PERSONA_USER_ID

    PREMADE_PERSONAS: List[Dict[str, Any]] = [
        {
            "persona_id": "basic-american-host",
            "display_name": "Ava Brooks",
            "language": "English",
            "tts_voice": "en-US-Standard-F",
            "tone_default": "confident",
            "market_default": "american",
            "description": "American product reviewer for U.S. consumer apps.",
            "region_label": "American",
            "accent_a": "#1E3A8A",
            "accent_b": "#22C55E",
        },
        {
            "persona_id": "basic-latin-host",
            "display_name": "Lucia Torres",
            "language": "Spanish",
            "tts_voice": "es-US-Standard-B",
            "tone_default": "warm",
            "market_default": "latin",
            "description": "Latin market reviewer for Spanish-speaking TikTok audiences.",
            "region_label": "Latin",
            "accent_a": "#C2410C",
            "accent_b": "#F97316",
        },
        {
            "persona_id": "basic-asian-host",
            "display_name": "Mina Park",
            "language": "English",
            "tts_voice": "en-US-Standard-C",
            "tone_default": "measured",
            "market_default": "asian",
            "description": "Pan-Asian English-speaking reviewer for modern app launches.",
            "region_label": "Asian",
            "accent_a": "#0F766E",
            "accent_b": "#14B8A6",
        },
        {
            "persona_id": "basic-indian-host",
            "display_name": "Arjun Mehta",
            "language": "English",
            "tts_voice": "en-IN-Standard-D",
            "tone_default": "upbeat",
            "market_default": "indian",
            "description": "Indian English reviewer for mobile products and utility apps.",
            "region_label": "Indian",
            "accent_a": "#7C2D12",
            "accent_b": "#EA580C",
        },
        {
            "persona_id": "basic-muslim-host",
            "display_name": "Layla Haddad",
            "language": "Arabic",
            "tts_voice": "ar-XA-Standard-C",
            "tone_default": "clear",
            "market_default": "muslim",
            "description": "Arabic-speaking reviewer for MENA-focused product storytelling.",
            "region_label": "Muslim",
            "accent_a": "#14532D",
            "accent_b": "#16A34A",
        },
        {
            "persona_id": "basic-african-host",
            "display_name": "Ama Okafor",
            "language": "English",
            "tts_voice": "en-GB-Standard-A",
            "tone_default": "direct",
            "market_default": "african",
            "description": "African English reviewer for utility, fintech, and lifestyle apps.",
            "region_label": "African",
            "accent_a": "#7E22CE",
            "accent_b": "#DB2777",
        },
        {
            "persona_id": "basic-european-host",
            "display_name": "Elena Fischer",
            "language": "English",
            "tts_voice": "en-GB-Standard-F",
            "tone_default": "polished",
            "market_default": "european",
            "description": "European reviewer for premium SaaS and productivity product demos.",
            "region_label": "European",
            "accent_a": "#1D4ED8",
            "accent_b": "#38BDF8",
        },
        {
            "persona_id": "basic-chinese-host",
            "display_name": "Wei Chen",
            "language": "Chinese",
            "tts_voice": "cmn-CN-Standard-B",
            "tone_default": "calm",
            "market_default": "chinese",
            "description": "Chinese-speaking reviewer for China-market app explainers.",
            "region_label": "Chinese",
            "accent_a": "#991B1B",
            "accent_b": "#EF4444",
        },
    ]

    @classmethod
    def is_system_persona(cls, persona: Optional[Dict[str, Any]]) -> bool:
        if not persona:
            return False
        persona_id = str(persona.get("persona_id") or "").strip()
        return bool(
            persona.get("is_preset_catalog")
            or persona.get("user_id") == _SYSTEM_PERSONA_USER_ID
            or persona_id.startswith("global-")
        )

    @classmethod
    def preset_persona_map(cls) -> Dict[str, Dict[str, Any]]:
        payload: Dict[str, Dict[str, Any]] = {}
        for item in cls.PREMADE_PERSONAS:
            preview_url = _data_svg_uri(
                title=item["display_name"],
                subtitle=item["region_label"],
                accent_a=item["accent_a"],
                accent_b=item["accent_b"],
                badge=item["language"].upper()[:12],
            )
            safe_avatar_url = "https://ui-avatars.com/api/?name=" + quote(item["display_name"]) + "&background=random"
            payload[item["persona_id"]] = {
                "user_id": _SYSTEM_PERSONA_USER_ID,
                "persona_id": item["persona_id"],
                "display_name": item["display_name"],
                "language": item["language"],
                "tts_voice": item["tts_voice"],
                "status": "ready",
                "video_count": 0,
                "tone_default": item["tone_default"],
                "market_default": item["market_default"],
                "description": item["description"],
                "region_label": item["region_label"],
                "is_preset_catalog": True,
                "demo_available": True,
                "thumbnail_url": preview_url,
                "selection_image_url": preview_url,
                "avatar_image_url": safe_avatar_url,
            }
        return payload

    @classmethod
    async def _get_temporal_client(cls, existing_client: Any | None) -> Client:
        if existing_client:
            return existing_client
        return await Client.connect(
            settings.temporal_connection_address,
            namespace=settings.TEMPORAL_NAMESPACE,
        )

    @classmethod
    async def _list_tiktok_accounts(cls, user_id: str) -> List[Dict[str, Any]]:
        accounts = await AccountConnectionService.list_accounts(user_id)
        return [
            item
            for item in accounts
            if str(item.get("platform") or "").strip().lower() == "tiktok"
        ]

    @classmethod
    def _persona_option_payload(
        cls,
        persona: Dict[str, Any],
        *,
        tiktok_accounts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        active_channels = [
            item
            for item in tiktok_accounts
            if item.get("connection_status") == "connected" and item.get("is_active")
        ]
        selection_image_url = (
            persona.get("selection_image_url")
            or persona.get("thumbnail_url")
            or persona.get("avatar_image_url")
        )
        is_preset_catalog = cls.is_system_persona(persona)
        return {
            "persona_id": persona.get("persona_id"),
            "display_name": persona.get("display_name"),
            "language": persona.get("language") or "English",
            "region_label": persona.get("region_label")
            or str(persona.get("market_default") or "global")
            .replace("_", " ")
            .title(),
            "market_default": persona.get("market_default"),
            "tone_default": persona.get("tone_default"),
            "description": persona.get("description"),
            "image_url": selection_image_url,
            "selection_image_url": selection_image_url,
            "is_preset": is_preset_catalog,
            "is_preset_catalog": is_preset_catalog,
            "demo": {
                "available": bool(persona.get("demo_available", True)),
                "label": f"{persona.get('display_name')} demo",
                "summary": "AI-generated app review demo with direct TikTok publishing support.",
            },
            "tiktok_integration": {
                "status": "active" if active_channels else "inactive",
                "active_channels": len(active_channels),
                "inactive_channels": max(
                    len(tiktok_accounts) - len(active_channels), 0
                ),
                "channels": [
                    {
                        "id": item.get("id"),
                        "display_name": item.get("display_name")
                        or item.get("account_name"),
                        "handle": item.get("account_handle"),
                        "status": "active"
                        if item.get("connection_status") == "connected"
                        and item.get("is_active")
                        else "inactive",
                    }
                    for item in tiktok_accounts[:10]
                ],
            },
        }

    @classmethod
    async def get_setup(cls, *, user_id: str) -> Dict[str, Any]:
        personas = await PersonaRegistryService.list_personas(user_id=user_id)
        tiktok_accounts = await cls._list_tiktok_accounts(user_id)
        telegram_link = await TelegramLinkService.get_link_for_user(user_id)
        system_source_personas = [
            persona
            for persona in personas
            if cls.is_system_persona(persona)
        ]
        if not system_source_personas:
            system_source_personas = list(cls.preset_persona_map().values())

        preset_personas = [
            cls._persona_option_payload(persona, tiktok_accounts=tiktok_accounts)
            for persona in system_source_personas
        ]
        custom_personas = [
            cls._persona_option_payload(persona, tiktok_accounts=tiktok_accounts)
            for persona in personas
            if not cls.is_system_persona(persona)
        ]
        return {
            "steps": [
                {"key": "enter_url", "label": "Step 1: Enter URL"},
                {
                    "key": "choose_persona",
                    "label": "Step 2: Choose an available persona",
                },
                {"key": "final_product", "label": "Step 3: Final product"},
            ],
            "supported_languages": ["English", "Chinese", "Spanish", "Arabic"],
            "persona_options": preset_personas,
            "custom_personas": custom_personas,
            "create_your_own": {
                "available": True,
                "label": "Create your own Persona",
            },
            "publishing_requirements": {
                "telegram_linked": telegram_link is not None,
                "tiktok_channels_active": any(
                    item.get("connection_status") == "connected"
                    and item.get("is_active")
                    for item in tiktok_accounts
                ),
                "tiktok_channels_total": len(tiktok_accounts),
            },
        }

    @classmethod
    async def _resolve_persona(
        cls,
        *,
        persona_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        persona = await PersonaRegistryService.get_persona(persona_id, user_id=user_id)
        if persona:
            return persona
        return cls.preset_persona_map().get(persona_id)

    @classmethod
    def _build_page_review_contract(
        cls,
        *,
        plan: Dict[str, Any],
    ) -> WebPageReviewContract:
        page_review_data = _coerce_json_dict(plan.get("page_review_data"))
        normalized_url = str(
            page_review_data.get("normalized_url")
            or page_review_data.get("target_url")
            or plan.get("source_url")
            or ""
        ).strip()
        target_url = str(
            page_review_data.get("target_url")
            or normalized_url
            or plan.get("source_url")
            or ""
        ).strip()
        payload = {
            "target_url": target_url,
            "normalized_url": normalized_url,
            "page_title": page_review_data.get("page_title")
            or _coerce_json_dict(plan.get("publish_settings")).get("page_title"),
            "product_summary": page_review_data.get("product_summary") or "",
            "page_fetch_method": page_review_data.get("page_fetch_method")
            or "manual_summary",
            "access_level": page_review_data.get("access_level") or "unknown",
            "login_required": bool(page_review_data.get("login_required")),
            "visible_features": _coerce_json_list(
                page_review_data.get("visible_features")
            ),
            "visible_flows": _coerce_json_list(page_review_data.get("visible_flows")),
            "recording_candidates": _coerce_json_list(
                page_review_data.get("recording_candidates")
            ),
            "risks": _coerce_json_list(page_review_data.get("risks")),
            "assumptions": _coerce_json_list(page_review_data.get("assumptions")),
            "suggested_objective": page_review_data.get("suggested_objective"),
        }
        return WebPageReviewContract.model_validate(payload)

    @classmethod
    def _build_review_plan(
        cls,
        *,
        plan: Dict[str, Any],
        persona: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        page_review = cls._build_page_review_contract(plan=plan)
        creative_preferences = _coerce_json_dict(plan.get("creative_preferences"))
        audio_policy = _audio_policy_from_creative_preferences(creative_preferences)
        input_mode = _plan_input_mode(plan)
        execution_mode = _execution_mode_for_page_review(
            page_review_data=page_review.model_dump(mode="json"),
            input_mode=input_mode,
        )
        review_plan = VideoReviewPlanContract(
            plan_id=str(plan.get("id")),
            objective=str(plan.get("objective") or "App review").strip() or "App review",
            target_url=page_review.normalized_url,
            language=str(persona.get("language") if persona else "English") or "English",
            persona_id=str(plan.get("persona_id") or ""),
            execution_mode=execution_mode,
            access_level=page_review.access_level,
            page_review=page_review,
            audio_policy=audio_policy,
            assumptions=list(page_review.assumptions or []),
            risks=list(page_review.risks or []),
            status="confirmed",
        )
        return review_plan.model_dump(mode="json")

    @classmethod
    def _build_plan_job_input(
        cls,
        *,
        plan: Dict[str, Any],
        persona: Optional[Dict[str, Any]],
        publish_settings: Dict[str, Any],
        review_plan: Dict[str, Any],
        active_tiktok_accounts: List[Dict[str, Any]],
        telegram_link: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        page_review_data = _coerce_json_dict(plan.get("page_review_data"))
        return {
            "job_kind": "app_review",
            "source_url": plan.get("source_url"),
            "normalized_url": page_review_data.get("normalized_url")
            or plan.get("source_url"),
            "page_title": page_review_data.get("page_title")
            or publish_settings.get("page_title")
            or publish_settings.get("content_title"),
            "objective": plan.get("objective"),
            "persona_id": str(plan.get("persona_id") or ""),
            "persona_display_name": persona.get("display_name") if persona else None,
            "persona_language": persona.get("language") if persona else "English",
            "persona_region": (
                persona.get("region_label") or persona.get("market_default")
            )
            if persona
            else None,
            "persona_image_url": (
                persona.get("selection_image_url")
                or persona.get("thumbnail_url")
                or persona.get("avatar_image_url")
            )
            if persona
            else None,
            "input_mode": _plan_input_mode(plan),
            "target_platform": "tiktok",
            "publish_requested": bool(publish_settings.get("publish_requested")),
            "telegram_linked": telegram_link is not None,
            "active_tiktok_channels": len(active_tiktok_accounts),
            "content_title": publish_settings.get("content_title"),
            "editable_content": publish_settings.get("caption_draft")
            or plan.get("script_text"),
            "caption_draft": publish_settings.get("caption_draft")
            or plan.get("script_text"),
            "review_plan": review_plan,
            "script": {
                "script": plan.get("script_text"),
                "scenes": plan.get("scenes_data") or [],
            },
            "campaign_id": plan.get("campaign_id"),
            "plan_id": str(plan.get("id") or ""),
            "publish_settings": publish_settings,
            "creative_preferences": _coerce_json_dict(
                plan.get("creative_preferences")
            ),
        }

    @classmethod
    def _serialize_plan_job(
        cls,
        plan: Dict[str, Any],
        *,
        persona: Optional[Dict[str, Any]],
        tiktok_accounts: List[Dict[str, Any]],
        workflow_row: Optional[Dict[str, Any]] = None,
        media_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
        content_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        publish_settings = _coerce_json_dict(plan.get("publish_settings"))
        creative_preferences = _coerce_json_dict(plan.get("creative_preferences"))
        review_plan = cls._build_review_plan(plan=plan, persona=persona)
        input_mode = _plan_input_mode(plan)
        job_type = (
            "app_review_upload" if input_mode == "user_upload" else "app_review_video"
        )
        page_review_data = _coerce_json_dict(plan.get("page_review_data"))
        page_title = (
            page_review_data.get("page_title")
            or publish_settings.get("page_title")
            or publish_settings.get("content_title")
            or "App Review"
        )
        caption_draft = str(
            publish_settings.get("caption_draft") or plan.get("script_text") or ""
        )

        if workflow_row:
            payload = cls._serialize_job(
                workflow_row,
                media_lookup=media_lookup or {},
                content_lookup=content_lookup or {},
                tiktok_accounts=tiktok_accounts,
            )
            payload["job_id"] = str(plan.get("id"))
            payload["plan_id"] = str(plan.get("id"))
            payload["workflow_id"] = workflow_row.get("workflow_id") or plan.get(
                "workflow_id"
            )
            payload["type"] = workflow_row.get("type") or job_type
            payload["source_url"] = (
                payload.get("source_url")
                or page_review_data.get("normalized_url")
                or plan.get("source_url")
            )
            payload["objective"] = payload.get("objective") or plan.get("objective")
            payload["page_title"] = payload.get("page_title") or page_title
            payload["input_mode"] = input_mode
            payload["script"] = payload.get("script") or {
                "script": plan.get("script_text"),
                "scenes": plan.get("scenes_data") or [],
            }
            payload["review_plan"] = payload.get("review_plan") or review_plan
            payload["campaign_id"] = payload.get("campaign_id") or plan.get(
                "campaign_id"
            )
            payload["persona_id"] = str(plan.get("persona_id") or "")
            payload["publish_settings"] = _merge_dict(
                publish_settings, payload.get("publish_settings")
            )
            payload["master_contract"] = (
                payload.get("master_contract")
                or payload.get("publish_settings", {}).get("shared_contract")
                or publish_settings.get("shared_contract")
            )
            payload["creative_preferences"] = creative_preferences
            payload["created_at"] = plan.get("created_at")
            payload["updated_at"] = payload.get("updated_at") or plan.get("updated_at")
            if plan.get("approved_at") and not payload.get("approved_at"):
                payload["approved_at"] = plan.get("approved_at")
            if plan.get("video_url") and not payload.get("production", {}).get(
                "playable_video_url"
            ):
                payload["production"] = {
                    **payload.get("production", {}),
                    "ready": True,
                    "playable_video_url": plan.get("video_url"),
                    "download_url": plan.get("video_url"),
                }
            return payload

        has_video = bool(plan.get("video_url"))
        status = str(plan.get("status") or "generated").strip().lower() or "generated"
        current_step = (
            "awaiting_upload"
            if status == "upload_required"
            else "final_product_ready"
            if has_video
            else status
        )
        progress = _job_progress(status, current_step, has_video)
        persona_payload = (
            cls._persona_option_payload(persona, tiktok_accounts=tiktok_accounts)
            if persona
            else {
                "persona_id": plan.get("persona_id"),
                "display_name": plan.get("persona_id"),
                "language": "English",
                "region_label": "Global",
                "selection_image_url": None,
                "image_url": None,
            }
        )
        publish_requested = bool(publish_settings.get("publish_requested"))
        publish_status = (
            "ready_to_publish" if publish_requested and has_video else "not_requested"
        )
        return {
            "job_id": str(plan.get("id")),
            "plan_id": str(plan.get("id")),
            "workflow_id": plan.get("workflow_id"),
            "type": job_type,
            "status": status,
            "current_step": current_step,
            "progress": progress,
            "input_mode": input_mode,
            "activity_feed": _job_steps(status, current_step, has_video=has_video),
            "source_url": page_review_data.get("normalized_url") or plan.get("source_url"),
            "objective": plan.get("objective"),
            "page_title": page_title,
            "persona": {
                "persona_id": persona_payload.get("persona_id"),
                "display_name": persona_payload.get("display_name"),
                "language": persona_payload.get("language"),
                "region_label": persona_payload.get("region_label"),
                "image_url": persona_payload.get("selection_image_url")
                or persona_payload.get("image_url"),
                "selection_image_url": persona_payload.get("selection_image_url")
                or persona_payload.get("image_url"),
                "tiktok_integration": persona_payload.get("tiktok_integration"),
            },
            "content": {
                "title": publish_settings.get("content_title") or page_title,
                "body": caption_draft,
                "content_id": None,
                "status": publish_status,
                "published": False,
            },
            "production": {
                "ready": has_video,
                "playable_video_url": plan.get("video_url"),
                "download_url": plan.get("video_url"),
                "media_asset_id": publish_settings.get("uploaded_media_asset_id"),
                "publish_enabled": bool(has_video),
            },
            "publish": {
                "requested": publish_requested,
                "status": publish_status,
                "published_at": None,
                "post_url": None,
                "publish_error": None,
            },
            "recording_script": None,
            "script": {
                "script": plan.get("script_text"),
                "scenes": plan.get("scenes_data") or [],
            },
            "editable_content": caption_draft,
            "review_plan": review_plan,
            "campaign_id": plan.get("campaign_id"),
            "persona_id": str(plan.get("persona_id") or ""),
            "target_platform": "tiktok",
            "publish_settings": publish_settings,
            "master_contract": publish_settings.get("shared_contract") or None,
            "creative_preferences": creative_preferences,
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at"),
            "approved_at": plan.get("approved_at"),
        }

    @classmethod
    async def _record_job_state(
        cls,
        *,
        workflow_id: str,
        user_id: str,
        workflow_type: str,
        status: str,
        current_step: str,
        progress: int,
        input_data: Dict[str, Any],
    ) -> None:
        await WorkflowStateService.record_started(
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_type=workflow_type,
            status=status,
            current_step=current_step,
            progress=progress,
            channel="web_app",
            input_data=input_data,
        )

    @classmethod
    async def _update_job_output(
        cls,
        *,
        workflow_id: str,
        user_id: str,
        status: Optional[str] = None,
        current_step: Optional[str] = None,
        progress: Optional[int] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        update_fields: List[str] = []
        args: List[Any] = [workflow_id, user_id]
        if status is not None:
            args.append(status)
            update_fields.append(f"status = ${len(args)}")
        if current_step is not None:
            args.append(current_step)
            update_fields.append(f"current_step = ${len(args)}")
        if progress is not None:
            args.append(int(progress))
            update_fields.append(f"progress = ${len(args)}")
        if output_data is not None:
            args.append(json.dumps(output_data, sort_keys=True))
            update_fields.append(
                f"output_data = COALESCE(output_data, '{{}}'::jsonb) || ${len(args)}::jsonb"
            )
        if error_message is not None:
            args.append(error_message)
            update_fields.append(f"error_message = ${len(args)}")
        terminal_status = status in {"completed", "failed", "canceled", "cancelled"}
        if terminal_status:
            update_fields.append("completed_at = NOW()")
        update_fields.append("updated_at = NOW()")
        if not update_fields:
            return await cls.get_job(
                user_id=user_id, job_id=workflow_id, temporal_client=None
            )
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE public.workflows
                SET {", ".join(update_fields)}
                WHERE workflow_id = $1
                  AND user_id = $2::uuid
                RETURNING *
                """,
                *args,
            )
        return dict(row) if row else None

    @classmethod
    async def _start_video_workflow(
        cls,
        *,
        session: CustomerSession,
        persona: Dict[str, Any],
        page_review: WebPageReviewContract,
        objective: str,
        execution_mode: str,
        publish_to_tiktok: bool,
        auto_publish_enabled: bool,
        content_title: str,
        caption_draft: str,
        audio_policy: VideoAudioPolicyContract,
        campaign_id: Optional[str],
        temporal_client: Any | None,
        telegram_link: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        review_plan = VideoReviewPlanContract(
            objective=objective,
            target_url=page_review.normalized_url,
            language=str(persona.get("language") or "English"),
            persona_id=str(persona.get("persona_id")),
            execution_mode=execution_mode,
            access_level=str(page_review.access_level or "unknown"),
            page_review=page_review,
            audio_policy=audio_policy,
            assumptions=list(page_review.assumptions or []),
            risks=list(page_review.risks or []),
            status="confirmed",
        )
        topic = f"{page_review.page_title or 'App review'} - {objective}".strip()
        start_payload = VideoWorkflowStartPayloadContract(
            persona_id=str(persona.get("persona_id")),
            topic=topic,
            tone=str(persona.get("tone_default") or "natural"),
            platform="tiktok",
            telegram_chat_id=str(telegram_link.get("chat_id"))
            if telegram_link
            else None,
            user_id=session.user_id,
            owner_key=None,
            talking_head_optional=True,
            review_plan=review_plan,
            execution_mode=execution_mode,
            audio_policy=audio_policy,
            persona_snapshot=VideoWorkflowPersonaSnapshotContract(
                persona_id=str(persona.get("persona_id")),
                display_name=str(
                    persona.get("display_name") or persona.get("persona_id")
                ),
                language=str(persona.get("language") or "English"),
                tts_voice=str(persona.get("tts_voice") or "en-US-Standard-F"),
                heygen_avatar_id=persona.get("heygen_avatar_id"),
                avatar_image_url=persona.get("avatar_image_url")
                or persona.get("selection_image_url")
                or persona.get("thumbnail_url"),
            ),
        )
        from workflows.short_video_workflow import ShortVideoWorkflow

        client = await cls._get_temporal_client(temporal_client)
        workflow_id = f"video-{persona.get('persona_id')}-{uuid4().hex[:8]}"
        handle = await client.start_workflow(
            ShortVideoWorkflow.run,
            args=[
                {
                    **start_payload.model_dump(mode="json"),
                    "workflow_id": workflow_id,
                    "campaign_id": campaign_id,
                    "publish_requested": publish_to_tiktok,
                    "auto_publish_enabled": auto_publish_enabled,
                    "content_title": content_title,
                    "caption_draft": caption_draft,
                }
            ],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(hours=2),
        )
        return {
            "workflow_id": workflow_id,
            "run_id": getattr(handle, "first_execution_run_id", None),
            "review_plan": review_plan.model_dump(mode="json"),
            "topic": topic,
            "publish_to_tiktok": publish_to_tiktok,
        }

    @classmethod
    async def _create_job_for_persona(
        cls,
        *,
        session: CustomerSession,
        persona_id: str,
        source_url: str,
        objective: str,
        input_mode: str,
        publish_to_tiktok: bool,
        creative_preferences: Dict[str, Any],
        page_review: WebPageReviewContract,
        page_review_payload: Dict[str, Any],
        master_script_payload: Optional[Dict[str, Any]],
        master_recording_script_payload: Optional[Dict[str, Any]],
        master_contract_payload: Optional[Dict[str, Any]],
        tiktok_accounts: List[Dict[str, Any]],
        brand_profile: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        persona_start = perf_counter()
        persona = await cls._resolve_persona(
            persona_id=persona_id,
            user_id=session.user_id,
        )
        if not persona:
            return {
                "warning": {
                    "code": "persona_not_found",
                    "message": f"Persona '{persona_id}' was not found and was skipped.",
                }
            }

        execution_mode = _execution_mode_for_page_review(
            page_review_data=page_review_payload,
            input_mode=input_mode,
        )
        review_plan_payload = {
            "objective": objective,
            "target_url": page_review.normalized_url,
            "language": str(persona.get("language") or "English"),
            "persona_id": persona_id,
            "execution_mode": execution_mode,
            "access_level": page_review.access_level,
            "page_review": page_review_payload,
            "audio_policy": _audio_policy_from_creative_preferences(
                creative_preferences
            ).model_dump(mode="json"),
            "assumptions": list(page_review.assumptions or []),
            "risks": list(page_review.risks or []),
            "status": "confirmed",
            "suggested_objective": getattr(page_review, "suggested_objective", None),
        }

        script_payload: Optional[Dict[str, Any]] = None
        recording_script_payload: Optional[Dict[str, Any]] = None
        caption_draft = ""
        selected_mode = input_mode

        try:
            script_started = perf_counter()
            if not master_script_payload:
                raise ValueError("Missing English master script payload")

            persona_language = str(persona.get("language") or "English").strip() or "English"
            if persona_language.lower() == "english":
                script_payload = dict(master_script_payload)
                recording_script_payload = master_recording_script_payload
            else:
                script_service = ScriptService()
                translated_contract = await script_service.translate_review_plan_script(
                    app_name=getattr(page_review, "page_title", None)
                    or page_review.normalized_url,
                    source_script=_shared_contract_to_script_contract(
                        _build_master_contract_payload(master_script_payload)
                    ),
                    target_language=persona_language,
                    persona_config=persona,
                )
                script_payload = translated_contract.model_dump(mode="json")
                recording_script_payload = master_recording_script_payload
            caption_draft = _caption_from_script(
                objective=objective,
                page_title=getattr(page_review, "page_title", None)
                or page_review.normalized_url,
                persona=persona,
                script_payload=script_payload,
            )
            logger.info(
                "Create jobs persona script completed | persona_id=%s | duration_ms=%d",
                persona_id,
                int((perf_counter() - script_started) * 1000),
            )
        except Exception:
            logger.warning(
                "Script generation failed for persona %s",
                persona_id,
                exc_info=True,
            )
            return {
                "error": {
                    "code": "script_generation_failed",
                    "persona_id": persona_id,
                    "message": (
                        f"AI script generation failed for persona '{persona_id}'. "
                        "No plan was created for this persona."
                    ),
                }
            }

        content_title = (
            f"{getattr(page_review, 'page_title', None) or 'App Review'}"
            f" · {persona.get('display_name')}"
        )
        campaign_id = None
        if brand_profile is not None:
            campaign_payload = {
                "name": content_title,
                "description": objective,
                "content_pillars": ["App Review"],
                "target_platforms": ["tiktok"],
            }
            created_campaign = await CustomerCampaignService.create_campaign(
                session=session,
                payload=campaign_payload,
            )
            campaign_id = created_campaign["id"]

        plan = await VideoPlanningService.create_plan(
            {
                "user_id": session.user_id,
                "campaign_id": campaign_id,
                "persona_id": persona_id,
                "source_url": source_url,
                "objective": objective,
                "script_text": (script_payload or {}).get("script", ""),
                "scenes_data": (script_payload or {}).get("scenes", []),
                "duration_estimate": (script_payload or {}).get(
                    "duration_estimate", 0
                ),
                "status": "upload_required"
                if selected_mode == "user_upload"
                else "generated",
                "publish_settings": {
                    "caption_draft": caption_draft,
                    "publish_requested": publish_to_tiktok,
                    "content_title": content_title,
                    "page_title": getattr(page_review, "page_title", None),
                    "input_mode": selected_mode,
                    "shared_contract": master_contract_payload or {},
                },
                "creative_preferences": creative_preferences,
                "page_review_data": page_review_payload,
            }
        )

        job_payload = cls._serialize_plan_job(
            plan,
            persona=persona,
            tiktok_accounts=tiktok_accounts,
        )
        job_payload["recording_script"] = recording_script_payload
        job_payload["review_plan"] = review_plan_payload
        logger.info(
            "Create jobs persona completed | persona_id=%s | duration_ms=%d",
            persona_id,
            int((perf_counter() - persona_start) * 1000),
        )
        return {"job": job_payload}

    @classmethod
    async def localize_shared_contract(
        cls,
        *,
        app_name: str,
        shared_contract: Dict[str, Any],
        persona: Dict[str, Any],
    ) -> Dict[str, Any]:
        script_service = ScriptService()
        source_script = _shared_contract_to_script_contract(shared_contract)
        target_language = str(persona.get("language") or "English").strip() or "English"
        translated = await script_service.translate_review_plan_script(
            app_name=app_name,
            source_script=source_script,
            target_language=target_language,
            persona_config=persona,
        )
        return translated.model_dump(mode="json")

    @classmethod
    async def create_jobs(
        cls,
        *,
        session: CustomerSession,
        payload: Dict[str, Any],
        temporal_client: Any | None,
    ) -> Dict[str, Any]:
        source_url = str(payload.get("source_url") or "").strip()
        objective = str(payload.get("objective") or "").strip() or "Product review"
        creative_preferences = _coerce_json_dict(payload.get("creative_preferences"))
        target_personas = [
            str(item).strip()
            for item in (payload.get("target_personas") or [])
            if str(item).strip()
        ]
        input_mode = str(payload.get("input_mode") or "ai_autonomous").strip().lower()
        publish_to_tiktok = bool(payload.get("publish_to_tiktok"))
        if not source_url:
            raise ValueError("source_url is required")
        if not target_personas:
            raise ValueError("At least one persona must be selected")
        if input_mode not in {"ai_autonomous", "user_upload"}:
            raise ValueError("input_mode must be ai_autonomous or user_upload")

        request_started = perf_counter()
        cached_page_review = _coerce_page_review_contract(
            payload.get("page_review_data"),
            fallback_url=source_url,
        )
        dependency_tasks = [
            TelegramLinkService.get_link_for_user(session.user_id),
            cls._list_tiktok_accounts(session.user_id),
            BrandProfileService.get_for_user(session.user_id),
        ]
        if cached_page_review is None:
            dependency_tasks.append(
                WebsiteReviewService.review_url(
                    url=source_url,
                    objective=objective,
                    user_id=session.user_id,
                )
            )

        dependency_results = await asyncio.gather(*dependency_tasks)
        telegram_link = dependency_results[0]
        tiktok_accounts = dependency_results[1]
        brand_profile = dependency_results[2]
        active_tiktok_accounts = [
            item
            for item in tiktok_accounts
            if item.get("connection_status") == "connected" and item.get("is_active")
        ]
        page_review = (
            cached_page_review
            if cached_page_review is not None
            else dependency_results[3]
        )
        source_url = page_review.normalized_url
        logger.info(
            "Create jobs prerequisites resolved | cached_page_review=%s | duration_ms=%d | personas=%d",
            cached_page_review is not None,
            int((perf_counter() - request_started) * 1000),
            len(target_personas),
        )

        if (not str(payload.get("objective") or "").strip()) and getattr(
            page_review, "suggested_objective", None
        ):
            objective = page_review.suggested_objective

        page_review_payload = page_review.model_dump(mode="json")
        master_script_payload: Optional[Dict[str, Any]] = None
        master_recording_script_payload: Optional[Dict[str, Any]] = None
        master_contract_payload: Optional[Dict[str, Any]] = None
        master_generation_started = perf_counter()
        master_review_plan_payload = {
            "objective": objective,
            "target_url": page_review.normalized_url,
            "language": "English",
            "persona_id": "shared-master",
            "execution_mode": _execution_mode_for_page_review(
                page_review_data=page_review_payload,
                input_mode=input_mode,
            ),
            "access_level": page_review.access_level,
            "page_review": page_review_payload,
            "audio_policy": _audio_policy_from_creative_preferences(
                creative_preferences
            ).model_dump(mode="json"),
            "assumptions": list(page_review.assumptions or []),
            "risks": list(page_review.risks or []),
            "status": "confirmed",
            "suggested_objective": getattr(page_review, "suggested_objective", None),
        }
        script_service = ScriptService()
        try:
            master_contract, master_recording_script = await script_service.generate_script_from_review_plan(
                app_name=getattr(page_review, "page_title", None)
                or page_review.normalized_url,
                review_plan=master_review_plan_payload,
                persona_config={
                    "persona_id": "shared-master",
                    "display_name": "Shared Master",
                    "language": "English",
                    "tts_voice": "en-US-Standard-F",
                },
            )
        except Exception:
            logger.warning("English master script generation failed", exc_info=True)
            raise
        master_script_payload = master_contract.model_dump(mode="json")
        master_recording_script_payload = (
            master_recording_script.model_dump(mode="json")
            if master_recording_script
            else None
        )
        master_contract_payload = _build_master_contract_payload(master_script_payload)
        logger.info(
            "Create jobs English master completed | duration_ms=%d",
            int((perf_counter() - master_generation_started) * 1000),
        )
        warnings: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        if brand_profile is None:
            warnings.append(
                {
                    "code": "brand_onboarding_incomplete",
                    "message": "Generated app review jobs without campaign drafts. Complete brand onboarding to attach campaign metadata.",
                }
            )
        if publish_to_tiktok and not telegram_link:
            warnings.append(
                {
                    "code": "telegram_auth_required",
                    "message": "TikTok publishing requires a linked Telegram account for approval and delivery prompts.",
                }
            )
        if publish_to_tiktok and not active_tiktok_accounts:
            warnings.append(
                {
                    "code": "tiktok_auth_required",
                    "message": "TikTok publishing requires at least one active TikTok channel integration.",
                }
            )
        if getattr(page_review, "login_required", False):
            warnings.append(
                {
                    "code": "login_required_user_upload_recommended",
                    "message": "The target URL appears to require login. User upload mode is recommended for final capture.",
                }
            )

        persona_results = await asyncio.gather(
            *[
                cls._create_job_for_persona(
                    session=session,
                    persona_id=persona_id,
                    source_url=source_url,
                    objective=objective,
                    input_mode=input_mode,
                    publish_to_tiktok=publish_to_tiktok,
                    creative_preferences=creative_preferences,
                    page_review=page_review,
                    page_review_payload=page_review_payload,
                    master_script_payload=master_script_payload,
                    master_recording_script_payload=master_recording_script_payload,
                    master_contract_payload=master_contract_payload,
                    tiktok_accounts=tiktok_accounts,
                    brand_profile=brand_profile,
                )
                for persona_id in target_personas
            ]
        )

        jobs: List[Dict[str, Any]] = []
        for result in persona_results:
            if result.get("warning"):
                warnings.append(result["warning"])
                continue
            if result.get("error"):
                errors.append(result["error"])
                continue
            if result.get("job"):
                jobs.append(result["job"])

        if not jobs and errors:
            raise ValueError(errors[0]["message"])

        logger.info(
            "Create jobs completed | duration_ms=%d | jobs=%d | warnings=%d | errors=%d",
            int((perf_counter() - request_started) * 1000),
            len(jobs),
            len(warnings),
            len(errors),
        )

        response = {
            "status": "success",
            "jobs": jobs,
            "warnings": warnings,
            "master_contract": master_contract_payload,
        }
        if errors:
            response["errors"] = errors
        return response

    @classmethod
    async def start_workflow_from_plan(
        cls,
        *,
        session: CustomerSession,
        plan_id: str,
        temporal_client: Any | None,
    ) -> Dict[str, Any]:
        plan = await VideoPlanningService.get_plan(plan_id, session.user_id)
        if not plan:
            raise ValueError("Plan not found")
        if plan.get("workflow_id"):
            return {"status": "already_started", "workflow_id": plan["workflow_id"]}

        persona = await cls._resolve_persona(
            persona_id=str(plan.get("persona_id") or ""),
            user_id=session.user_id,
        )
        if not persona:
            raise ValueError("Persona not found for plan")

        telegram_link = await TelegramLinkService.get_link_for_user(session.user_id)
        tiktok_accounts = await cls._list_tiktok_accounts(session.user_id)
        active_tiktok_accounts = [
            item
            for item in tiktok_accounts
            if item.get("connection_status") == "connected" and item.get("is_active")
        ]

        publish_settings = _coerce_json_dict(plan.get("publish_settings"))
        creative_preferences = _coerce_json_dict(plan.get("creative_preferences"))
        audio_policy = _audio_policy_from_creative_preferences(creative_preferences)
        publish_to_tiktok = bool(publish_settings.get("publish_requested"))
        content_title = str(publish_settings.get("content_title") or "App Review")
        caption_draft = str(
            publish_settings.get("caption_draft") or plan.get("script_text") or ""
        )
        review_plan = cls._build_review_plan(plan=plan, persona=persona)
        execution_mode = str(review_plan.get("execution_mode") or "").strip()
        job_input = cls._build_plan_job_input(
            plan=plan,
            persona=persona,
            publish_settings=publish_settings,
            review_plan=review_plan,
            active_tiktok_accounts=active_tiktok_accounts,
            telegram_link=telegram_link,
        )

        if execution_mode == "manual_mobile_recording":
            if not plan.get("video_url"):
                raise ValueError("Upload final video before approving this plan")
            workflow_id = f"review-upload-{plan_id[:8]}-{uuid4().hex[:6]}"
            await cls._record_job_state(
                workflow_id=workflow_id,
                user_id=session.user_id,
                workflow_type="app_review_upload",
                status="completed",
                current_step="final_product_ready",
                progress=100,
                input_data=job_input,
            )
            await cls._update_job_output(
                workflow_id=workflow_id,
                user_id=session.user_id,
                status="completed",
                current_step="final_product_ready",
                progress=100,
                output_data={
                    "video_url": plan.get("video_url"),
                    "final_video_url": plan.get("video_url"),
                    "download_url": plan.get("video_url"),
                    "media_asset_id": publish_settings.get("uploaded_media_asset_id"),
                },
            )
            await VideoPlanningService.update_plan(
                plan_id,
                session.user_id,
                {"workflow_id": workflow_id},
            )
            return {
                "status": "started",
                "workflow_id": workflow_id,
                "review_plan": review_plan,
            }

        page_review = cls._build_page_review_contract(plan=plan)
        workflow_result = await cls._start_video_workflow(
            session=session,
            persona=persona,
            page_review=page_review,
            objective=plan.get("objective") or "App Review",
            execution_mode=execution_mode or "autonomous_screen_recording",
            publish_to_tiktok=publish_to_tiktok,
            auto_publish_enabled=bool(
                publish_to_tiktok and telegram_link and active_tiktok_accounts
            ),
            content_title=content_title,
            caption_draft=caption_draft,
            audio_policy=audio_policy,
            campaign_id=plan.get("campaign_id") and str(plan.get("campaign_id")),
            temporal_client=temporal_client,
            telegram_link=telegram_link,
        )
        workflow_id = workflow_result["workflow_id"]
        await VideoPlanningService.update_plan(
            plan_id,
            session.user_id,
            {"workflow_id": workflow_id},
        )
        job_input["review_plan"] = workflow_result["review_plan"]
        await cls._record_job_state(
            workflow_id=workflow_id,
            user_id=session.user_id,
            workflow_type="app_review_video",
            status="running",
            current_step="generation_queued",
            progress=15,
            input_data=job_input,
        )
        return {
            "status": "started",
            "workflow_id": workflow_id,
            "review_plan": workflow_result["review_plan"],
        }

    @classmethod
    async def _list_job_rows(cls, *, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM public.workflows
                WHERE user_id = $1::uuid
                  AND type = ANY($2::text[])
                ORDER BY updated_at DESC NULLS LAST, started_at DESC NULLS LAST
                LIMIT $3
                """,
                user_id,
                list(_APP_REVIEW_JOB_TYPES),
                max(1, min(int(limit or 50), 100)),
            )
        return [dict(row) for row in rows]

    @classmethod
    async def _load_media_by_workflow(
        cls,
        *,
        workflow_ids: List[str],
        user_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        if not workflow_ids:
            return {}
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, url, metadata, persona_id, created_at
                FROM public.media_assets
                WHERE user_id = $1::uuid
                  AND metadata->>'workflow_id' = ANY($2::text[])
                ORDER BY created_at DESC
                """,
                user_id,
                workflow_ids,
            )
        payload: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            metadata = _coerce_json_dict(row.get("metadata"))
            workflow_id = str(metadata.get("workflow_id") or "").strip()
            if not workflow_id or workflow_id in payload:
                continue
            payload[workflow_id] = {
                "media_asset_id": str(row["id"]),
                "video_url": row["url"],
                "persona_id": row["persona_id"],
                "metadata": metadata,
            }
        return payload

    @classmethod
    async def _load_content_by_workflow(
        cls,
        *,
        workflow_ids: List[str],
        user_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        if not workflow_ids:
            return {}
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, status, published_at, metadata, updated_at
                FROM public.content
                WHERE user_id = $1::uuid
                  AND metadata->>'workflow_id' = ANY($2::text[])
                ORDER BY updated_at DESC NULLS LAST, created_at DESC
                """,
                user_id,
                workflow_ids,
            )
        payload: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            metadata = _coerce_json_dict(row.get("metadata"))
            workflow_id = str(metadata.get("workflow_id") or "").strip()
            if not workflow_id or workflow_id in payload:
                continue
            payload[workflow_id] = {
                "content_id": str(row["id"]),
                "title": row["title"],
                "content": row["content"],
                "status": row["status"],
                "published_at": row["published_at"].isoformat()
                if row["published_at"]
                else None,
                "metadata": metadata,
            }
        return payload

    @classmethod
    async def _refresh_live_status(
        cls,
        *,
        temporal_client: Any | None,
        job_row: Dict[str, Any],
    ) -> Dict[str, Any]:
        def _normalize_execution_status(status_value: Any) -> Optional[str]:
            try:
                raw_name = str(
                    getattr(status_value, "name", status_value) or ""
                ).strip()
            except Exception:
                raw_name = ""
            if not raw_name:
                return None
            normalized = raw_name.replace("WORKFLOW_EXECUTION_STATUS_", "").lower()
            return normalized or None

        workflow_id = str(job_row.get("workflow_id") or "").strip()
        if not workflow_id.startswith("video-"):
            return job_row
        handle = None
        try:
            client = await cls._get_temporal_client(temporal_client)
            handle = client.get_workflow_handle(workflow_id)
            payload = await handle.query("get_workflow_status")
            job_row["status"] = payload.get("status", job_row.get("status"))
            job_row["current_step"] = payload.get(
                "current_step", job_row.get("current_step")
            )
        except Exception:
            if handle is None:
                return job_row
            try:
                description = await handle.describe()
                execution_status = _normalize_execution_status(
                    getattr(
                        getattr(
                            getattr(description, "raw_description", None),
                            "workflow_execution_info",
                            None,
                        ),
                        "status",
                        None,
                    )
                    or getattr(description, "status", None)
                )
            except Exception:
                execution_status = None

            if execution_status in {"running"}:
                job_row["status"] = execution_status
                job_row["current_step"] = (
                    job_row.get("current_step") or execution_status
                )
                return job_row

            try:
                terminal_result = await handle.result()
            except Exception:
                return job_row

            if isinstance(terminal_result, dict):
                job_row["status"] = (
                    terminal_result.get("status")
                    or execution_status
                    or job_row.get("status")
                )
                if terminal_result.get("status") in {
                    "completed",
                    "discarded",
                    "expired",
                }:
                    job_row["current_step"] = terminal_result.get("status")
                job_row["_temporal_result"] = terminal_result
        return job_row

    @classmethod
    def _serialize_job(
        cls,
        job_row: Dict[str, Any],
        *,
        media_lookup: Dict[str, Dict[str, Any]],
        content_lookup: Dict[str, Dict[str, Any]],
        tiktok_accounts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        workflow_id = str(job_row.get("workflow_id") or "")
        input_data = _coerce_json_dict(job_row.get("input_data"))
        output_data = _coerce_json_dict(job_row.get("output_data"))
        publish_settings = _coerce_json_dict(input_data.get("publish_settings"))
        temporal_result = job_row.get("_temporal_result") or {}
        temporal_metadata = temporal_result.get("metadata") or {}
        temporal_publish = temporal_metadata.get("publish_result") or {}
        media = media_lookup.get(workflow_id) or {}
        content = content_lookup.get(workflow_id) or {}
        has_video = bool(
            output_data.get("final_video_url")
            or temporal_result.get("video_url")
            or output_data.get("video_url")
            or media.get("video_url")
        )
        video_url = (
            output_data.get("final_video_url")
            or temporal_result.get("video_url")
            or output_data.get("video_url")
            or media.get("video_url")
        )
        publish_status = (
            output_data.get("publish_status")
            or content.get("status")
            or temporal_publish.get("status")
            or (
                "ready_to_publish"
                if has_video and input_data.get("publish_requested")
                else "not_requested"
            )
        )
        progress = _job_progress(
            str(job_row.get("status") or "running"),
            job_row.get("current_step"),
            has_video=has_video,
        )
        persona_payload = {
            "persona_id": input_data.get("persona_id"),
            "display_name": input_data.get("persona_display_name"),
            "language": input_data.get("persona_language"),
            "region_label": input_data.get("persona_region"),
            "image_url": input_data.get("persona_image_url"),
            "tiktok_integration": {
                "status": "active"
                if any(
                    item.get("connection_status") == "connected"
                    and item.get("is_active")
                    for item in tiktok_accounts
                )
                else "inactive",
                "channels": [
                    {
                        "id": item.get("id"),
                        "display_name": item.get("display_name")
                        or item.get("account_name"),
                        "handle": item.get("account_handle"),
                    }
                    for item in tiktok_accounts[:10]
                ],
            },
        }
        return {
            "job_id": input_data.get("plan_id") or workflow_id,
            "plan_id": input_data.get("plan_id"),
            "workflow_id": workflow_id,
            "type": job_row.get("type"),
            "status": job_row.get("status"),
            "current_step": job_row.get("current_step"),
            "progress": progress,
            "input_mode": input_data.get("input_mode")
            or publish_settings.get("input_mode"),
            "activity_feed": _job_steps(
                str(job_row.get("status") or "running"),
                job_row.get("current_step"),
                has_video=has_video,
            ),
            "source_url": input_data.get("normalized_url")
            or input_data.get("source_url"),
            "objective": input_data.get("objective"),
            "page_title": input_data.get("page_title"),
            "persona": persona_payload,
            "content": {
                "title": output_data.get("content_title")
                or input_data.get("content_title"),
                "body": output_data.get("editable_content")
                or output_data.get("caption_draft")
                or content.get("content")
                or input_data.get("editable_content"),
                "content_id": output_data.get("content_record_id")
                or content.get("content_id"),
                "status": content.get("status") or publish_status,
                "published": publish_status in {"published", "scheduled"},
            },
            "production": {
                "ready": has_video,
                "playable_video_url": video_url,
                "download_url": video_url,
                "media_asset_id": output_data.get("media_asset_id")
                or media.get("media_asset_id"),
                "publish_enabled": bool(has_video),
            },
            "publish": {
                "requested": bool(input_data.get("publish_requested")),
                "status": publish_status,
                "published_at": output_data.get("published_at")
                or temporal_publish.get("published_at")
                or content.get("published_at"),
                "post_url": output_data.get("post_url")
                or temporal_publish.get("post_url")
                or content.get("metadata", {}).get("post_url"),
                "publish_error": output_data.get("publish_error")
                or temporal_publish.get("error")
                or content.get("metadata", {}).get("publish_error"),
            },
            "recording_script": input_data.get("recording_script"),
            "script": input_data.get("script"),
            "review_plan": input_data.get("review_plan"),
            "campaign_id": input_data.get("campaign_id"),
            "persona_id": input_data.get("persona_id"),
            "target_platform": input_data.get("target_platform"),
            "publish_settings": _merge_dict(
                publish_settings,
                {
                    "caption_draft": output_data.get("caption_draft")
                    or output_data.get("editable_content")
                    or publish_settings.get("caption_draft"),
                    "content_title": output_data.get("content_title")
                    or publish_settings.get("content_title")
                    or input_data.get("content_title"),
                },
            ),
            "creative_preferences": _coerce_json_dict(
                input_data.get("creative_preferences")
            ),
            "updated_at": job_row.get("updated_at").isoformat()
            if getattr(job_row.get("updated_at"), "isoformat", None)
            else job_row.get("updated_at"),
            "started_at": job_row.get("started_at").isoformat()
            if getattr(job_row.get("started_at"), "isoformat", None)
            else job_row.get("started_at"),
        }

    @classmethod
    async def list_jobs(
        cls,
        *,
        user_id: str,
        temporal_client: Any | None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        workflow_rows = await cls._list_job_rows(user_id=user_id, limit=limit)
        workflow_rows = [
            await cls._refresh_live_status(
                temporal_client=temporal_client,
                job_row=row,
            )
            for row in workflow_rows
        ]
        plans = await VideoPlanningService.list_plans(user_id, limit=limit)
        workflow_ids = [str(row.get("workflow_id") or "") for row in workflow_rows]
        media_lookup = await cls._load_media_by_workflow(
            workflow_ids=workflow_ids,
            user_id=user_id,
        )
        content_lookup = await cls._load_content_by_workflow(
            workflow_ids=workflow_ids,
            user_id=user_id,
        )
        tiktok_accounts = await cls._list_tiktok_accounts(user_id)
        workflow_by_plan_id: Dict[str, Dict[str, Any]] = {}
        workflow_by_id: Dict[str, Dict[str, Any]] = {}
        for row in workflow_rows:
            workflow_id = str(row.get("workflow_id") or "").strip()
            if workflow_id:
                workflow_by_id[workflow_id] = row
            input_data = _coerce_json_dict(row.get("input_data"))
            plan_ref = str(input_data.get("plan_id") or "").strip()
            if plan_ref and plan_ref not in workflow_by_plan_id:
                workflow_by_plan_id[plan_ref] = row

        merged_workflow_ids: set[str] = set()
        jobs: List[Dict[str, Any]] = []
        for plan in plans:
            plan_id = str(plan.get("id") or "").strip()
            workflow_row = workflow_by_plan_id.get(plan_id)
            if workflow_row is None and plan.get("workflow_id"):
                workflow_row = workflow_by_id.get(str(plan.get("workflow_id")))
            if workflow_row and workflow_row.get("workflow_id"):
                merged_workflow_ids.add(str(workflow_row["workflow_id"]))
            persona = await cls._resolve_persona(
                persona_id=str(plan.get("persona_id") or ""),
                user_id=user_id,
            )
            jobs.append(
                cls._serialize_plan_job(
                    plan,
                    persona=persona,
                    tiktok_accounts=tiktok_accounts,
                    workflow_row=workflow_row,
                    media_lookup=media_lookup,
                    content_lookup=content_lookup,
                )
            )

        for row in workflow_rows:
            workflow_id = str(row.get("workflow_id") or "").strip()
            if workflow_id in merged_workflow_ids:
                continue
            jobs.append(
                cls._serialize_job(
                    row,
                    media_lookup=media_lookup,
                    content_lookup=content_lookup,
                    tiktok_accounts=tiktok_accounts,
                )
            )

        jobs.sort(
            key=lambda item: (
                item.get("updated_at")
                or item.get("started_at")
                or item.get("created_at")
                or ""
            ),
            reverse=True,
        )
        return {"jobs": jobs[: max(1, min(int(limit or 50), 100))]}

    @classmethod
    async def get_job(
        cls,
        *,
        user_id: str,
        job_id: str,
        temporal_client: Any | None,
    ) -> Optional[Dict[str, Any]]:
        payload = await cls.list_jobs(
            user_id=user_id,
            temporal_client=temporal_client,
            limit=100,
        )
        for item in payload["jobs"]:
            if item["job_id"] == job_id:
                return item
        return None

    @classmethod
    async def update_job_content(
        cls,
        *,
        user_id: str,
        job_id: str,
        title: Optional[str],
        content: Optional[str],
    ) -> Dict[str, Any]:
        output_payload = {}
        if title is not None:
            output_payload["content_title"] = title
        if content is not None:
            output_payload["editable_content"] = content
            output_payload["caption_draft"] = content
        if not output_payload:
            job = await cls.get_job(
                user_id=user_id, job_id=job_id, temporal_client=None
            )
            if not job:
                raise ValueError("App review job not found")
            return job
        plan = await VideoPlanningService.find_plan_for_job(job_id, user_id)
        if plan:
            publish_settings = _coerce_json_dict(plan.get("publish_settings"))
            if title is not None:
                publish_settings["content_title"] = title
            if content is not None:
                publish_settings["caption_draft"] = content
            updated_plan = await VideoPlanningService.update_plan(
                str(plan.get("id")),
                user_id,
                {
                    "publish_settings": publish_settings,
                    "script_text": content
                    if content is not None and plan.get("workflow_id") is None
                    else plan.get("script_text"),
                },
            )
            if updated_plan and plan.get("workflow_id"):
                await cls._update_job_output(
                    workflow_id=str(plan.get("workflow_id")),
                    user_id=user_id,
                    output_data=output_payload,
                )
        else:
            updated = await cls._update_job_output(
                workflow_id=job_id,
                user_id=user_id,
                output_data=output_payload,
            )
            if updated is None:
                raise ValueError("App review job not found")
        job = await cls.get_job(user_id=user_id, job_id=job_id, temporal_client=None)
        if not job:
            raise ValueError("App review job not found")
        return job

    @classmethod
    async def upload_manual_video(
        cls,
        *,
        session: CustomerSession,
        job_id: str,
        file_name: str,
        content_type: str,
        data: bytes,
    ) -> Dict[str, Any]:
        plan = await VideoPlanningService.find_plan_for_job(job_id, session.user_id)
        if not plan:
            raise ValueError("App review job not found")
        if _plan_input_mode(plan) != "user_upload":
            raise ValueError("Only user-upload jobs accept manual video uploads")
        upload = await MediaStorageService().upload_bytes(
            data=data,
            content_type=content_type,
            asset_type="VIDEO",
            asset_kind="video",
            asset_origin="uploaded",
            generation_prompt=plan.get("objective") or "Manual upload",
            user_id=session.user_id,
            persona_id=plan.get("persona_id"),
            metadata={
                "plan_id": str(plan.get("id")),
                "job_kind": "app_review",
                "source_url": plan.get("source_url"),
            },
            file_name_hint=file_name,
        )
        if not upload or not upload.get("access_url"):
            raise ValueError("Failed to upload review video")
        publish_settings = _coerce_json_dict(plan.get("publish_settings"))
        publish_settings["uploaded_media_asset_id"] = upload.get("media_asset_id")
        publish_settings["uploaded_file_name"] = file_name
        publish_settings["uploaded_content_type"] = content_type
        await VideoPlanningService.update_plan(
            str(plan.get("id")),
            session.user_id,
            {
                "status": "generated",
                "video_url": upload["access_url"],
                "publish_settings": publish_settings,
            },
        )
        updated = await cls.get_job(
            user_id=session.user_id,
            job_id=str(plan.get("id")),
            temporal_client=None,
        )
        if not updated:
            raise ValueError("App review job not found")
        return updated

    @classmethod
    async def publish_job_to_tiktok(
        cls,
        *,
        session: CustomerSession,
        job_id: str,
        schedule_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        job = await cls.get_job(
            user_id=session.user_id,
            job_id=job_id,
            temporal_client=None,
        )
        if not job:
            raise ValueError("App review job not found")
        video_url = job["production"].get("playable_video_url")
        if not video_url:
            raise ValueError("Final product is not ready for TikTok publishing yet")
        telegram_link = await TelegramLinkService.get_link_for_user(session.user_id)
        if not telegram_link:
            raise ValueError("Link Telegram before publishing to TikTok")
        tiktok_accounts = await cls._list_tiktok_accounts(session.user_id)
        active_tiktok_accounts = [
            item
            for item in tiktok_accounts
            if item.get("connection_status") == "connected" and item.get("is_active")
        ]
        if not active_tiktok_accounts:
            raise ValueError(
                "Connect at least one active TikTok channel before publishing"
            )
        workflow_link_id = job.get("workflow_id") or job.get("plan_id") or job_id

        post_config = {
            "id": workflow_link_id,
            "user_id": session.user_id,
            "content": job["content"]["body"] or job["objective"] or "App review",
            "platform": "tiktok",
            "media": [{"storage_url": video_url}],
            "scheduled_time": schedule_time,
            "theme": job["page_title"] or job["objective"] or "App Review",
            "hashtags": ["AppReview", "TikTokReview"],
        }
        persisted = await ContentPersistenceService.persist_scheduled_post(
            workflow_id=workflow_link_id,
            post_config=post_config,
        )
        publisher = PublisherService()
        try:
            publish_result = await publisher.publish(post_config)
        except Exception as exc:
            if job.get("workflow_id"):
                await cls._update_job_output(
                    workflow_id=str(job["workflow_id"]),
                    user_id=session.user_id,
                    output_data={
                        "content_record_id": persisted["content_record_id"],
                        "publish_status": "failed",
                        "publish_error": str(exc),
                    },
                )
            raise
        finally:
            await publisher.close()
        post_config["content_record_id"] = persisted["content_record_id"]
        await ContentPersistenceService.update_publish_result(
            workflow_id=workflow_link_id,
            post_config=post_config,
            publish_result=publish_result,
        )
        if job.get("workflow_id"):
            await cls._update_job_output(
                workflow_id=str(job["workflow_id"]),
                user_id=session.user_id,
                output_data={
                    "content_record_id": persisted["content_record_id"],
                    "publish_status": publish_result.get("status"),
                    "published_at": publish_result.get("published_at"),
                    "post_url": publish_result.get("post_url"),
                    "publish_error": publish_result.get("error"),
                    "publish_method": publish_result.get("method"),
                },
            )
        updated = await cls.get_job(
            user_id=session.user_id,
            job_id=job_id,
            temporal_client=None,
        )
        if not updated:
            raise ValueError("App review job not found")
        return updated
