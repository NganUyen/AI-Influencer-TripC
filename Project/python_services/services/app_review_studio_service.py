"""
App-review studio helpers for persona selection, generation jobs, uploads, and TikTok publishing.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import timedelta
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
    VideoAudioPolicyContract,
    VideoReviewPlanContract,
    VideoWorkflowPersonaSnapshotContract,
    VideoWorkflowStartPayloadContract,
)
from services.website_review_service import WebsiteReviewService


_SYSTEM_PERSONA_USER_ID = "00000000-0000-0000-0000-000000000001"
_APP_REVIEW_JOB_TYPES = {"app_review_video", "app_review_upload"}


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


class AppReviewStudioService:
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
                "avatar_image_url": preview_url,
            }
        return payload

    @classmethod
    async def _get_temporal_client(cls, existing_client: Any | None) -> Client:
        if existing_client:
            return existing_client
        return await Client.connect(
            settings.TEMPORAL_ADDRESS,
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
        return {
            "persona_id": persona.get("persona_id"),
            "display_name": persona.get("display_name"),
            "language": persona.get("language") or "English",
            "region_label": persona.get("region_label")
            or str(persona.get("market_default") or "global").replace("_", " ").title(),
            "market_default": persona.get("market_default"),
            "tone_default": persona.get("tone_default"),
            "description": persona.get("description"),
            "image_url": selection_image_url,
            "selection_image_url": selection_image_url,
            "is_preset": bool(
                persona.get("is_preset_catalog")
                or persona.get("user_id") == _SYSTEM_PERSONA_USER_ID
            ),
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
        preset_personas = [
            cls._persona_option_payload(persona, tiktok_accounts=tiktok_accounts)
            for persona in cls.preset_persona_map().values()
        ]
        preset_ids = {item["persona_id"] for item in preset_personas}
        custom_personas = [
            cls._persona_option_payload(persona, tiktok_accounts=tiktok_accounts)
            for persona in personas
            if persona.get("persona_id") not in preset_ids
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
        page_review: Any,
        objective: str,
        publish_to_tiktok: bool,
        auto_publish_enabled: bool,
        content_title: str,
        caption_draft: str,
        campaign_id: Optional[str],
        temporal_client: Any | None,
        telegram_link: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        review_plan = VideoReviewPlanContract(
            objective=objective,
            target_url=page_review.normalized_url,
            language=str(persona.get("language") or "English"),
            persona_id=str(persona.get("persona_id")),
            execution_mode="autonomous_screen_recording",
            access_level=str(
                getattr(page_review, "access_level", "unknown") or "unknown"
            ),
            page_review=page_review,
            audio_policy=VideoAudioPolicyContract(),
            assumptions=list(getattr(page_review, "assumptions", []) or []),
            risks=list(getattr(page_review, "risks", []) or []),
            status="confirmed",
        )
        topic = f"{getattr(page_review, 'page_title', None) or 'App review'} - {objective}".strip()
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
            execution_mode="autonomous_screen_recording",
            audio_policy=VideoAudioPolicyContract(),
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
    async def create_jobs(
        cls,
        *,
        session: CustomerSession,
        payload: Dict[str, Any],
        temporal_client: Any | None,
    ) -> Dict[str, Any]:
        source_url = str(payload.get("source_url") or "").strip()
        objective = str(payload.get("objective") or "").strip() or "Product review"
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

        telegram_link = await TelegramLinkService.get_link_for_user(session.user_id)
        tiktok_accounts = await cls._list_tiktok_accounts(session.user_id)
        active_tiktok_accounts = [
            item
            for item in tiktok_accounts
            if item.get("connection_status") == "connected" and item.get("is_active")
        ]
        brand_profile = await BrandProfileService.get_for_user(session.user_id)
        page_review = await WebsiteReviewService.review_url(
            url=source_url,
            objective=objective,
            user_id=session.user_id,
        )
        script_service = ScriptService()
        warnings: List[Dict[str, Any]] = []
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

        jobs: List[Dict[str, Any]] = []
        for persona_id in target_personas:
            persona = await PersonaRegistryService.get_persona(
                persona_id,
                user_id=session.user_id,
            )
            if not persona:
                persona = cls.preset_persona_map().get(persona_id)
            if not persona:
                warnings.append(
                    {
                        "code": "persona_not_found",
                        "message": f"Persona '{persona_id}' was not found and was skipped.",
                    }
                )
                continue

            review_plan_payload = {
                "objective": objective,
                "target_url": page_review.normalized_url,
                "language": str(persona.get("language") or "English"),
                "persona_id": persona_id,
                "execution_mode": "autonomous_screen_recording",
                "page_review": page_review.model_dump(mode="json"),
                "status": "confirmed",
            }

            try:
                (
                    script_contract,
                    recording_script,
                ) = await script_service.generate_script_from_review_plan(
                    app_name=getattr(page_review, "page_title", None)
                    or page_review.normalized_url,
                    review_plan=review_plan_payload,
                    persona_config=persona,
                )
                script_payload = script_contract.model_dump()
                caption_draft = _caption_from_script(
                    objective=objective,
                    page_title=getattr(page_review, "page_title", None)
                    or page_review.normalized_url,
                    persona=persona,
                    script_payload=script_payload,
                )
            except Exception as script_err:
                # Log and add warning, then fall back to user_upload
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Script generation failed for persona {persona_id}: {script_err}. "
                    f"Falling back to user_upload mode."
                )
                warnings.append(
                    {
                        "code": "script_generation_failed",
                        "message": f"AI script generation failed for persona '{persona_id}'. Please try uploading a video manually or try again later.",
                    }
                )
                # Fall back to user_upload mode
                script_payload = None
                recording_script = None
                caption_draft = ""

            content_title = f"{getattr(page_review, 'page_title', None) or 'App Review'} · {persona.get('display_name')}"
            selected_mode = (
                "user_upload"
                if input_mode == "user_upload"
                or getattr(page_review, "login_required", False)
                else "ai_autonomous"
            )
            if selected_mode == "ai_autonomous" and script_payload is None:
                # If script generation failed, fallback to user_upload
                selected_mode = "user_upload"
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

            if selected_mode == "ai_autonomous":
                workflow_result = await cls._start_video_workflow(
                    session=session,
                    persona=persona,
                    page_review=page_review,
                    objective=objective,
                    publish_to_tiktok=publish_to_tiktok,
                    auto_publish_enabled=bool(
                        publish_to_tiktok and telegram_link and active_tiktok_accounts
                    ),
                    content_title=content_title,
                    caption_draft=caption_draft,
                    campaign_id=campaign_id,
                    temporal_client=temporal_client,
                    telegram_link=telegram_link,
                )
                workflow_id = workflow_result["workflow_id"]
                run_id = workflow_result["run_id"]
                current_step = "generation_queued"
                progress = 15
                workflow_type = "app_review_video"
            else:
                workflow_id = f"app-review-upload-{persona_id}-{uuid4().hex[:8]}"
                run_id = None
                current_step = "awaiting_upload"
                progress = 20
                workflow_type = "app_review_upload"
                workflow_result = {
                    "workflow_id": workflow_id,
                    "run_id": None,
                    "review_plan": review_plan_payload,
                }

            job_input = {
                "job_kind": "app_review",
                "source_url": source_url,
                "normalized_url": page_review.normalized_url,
                "page_title": getattr(page_review, "page_title", None),
                "objective": objective,
                "persona_id": persona_id,
                "persona_display_name": persona.get("display_name"),
                "persona_language": persona.get("language"),
                "persona_region": persona.get("region_label")
                or persona.get("market_default"),
                "persona_image_url": persona.get("selection_image_url")
                or persona.get("thumbnail_url")
                or persona.get("avatar_image_url"),
                "input_mode": selected_mode,
                "target_platform": "tiktok",
                "publish_requested": publish_to_tiktok,
                "telegram_linked": telegram_link is not None,
                "active_tiktok_channels": len(active_tiktok_accounts),
                "content_title": content_title,
                "editable_content": caption_draft,
                "caption_draft": caption_draft,
                "review_plan": workflow_result["review_plan"],
                "recording_script": recording_script.model_dump(mode="json")
                if recording_script
                else None,
                "script": script_payload,
                "campaign_id": campaign_id,
            }
            await cls._record_job_state(
                workflow_id=workflow_id,
                user_id=session.user_id,
                workflow_type=workflow_type,
                status="running",
                current_step=current_step,
                progress=progress,
                input_data=job_input,
            )

            jobs.append(
                {
                    "job_id": workflow_id,
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "persona_id": persona_id,
                    "persona": cls._persona_option_payload(
                        persona, tiktok_accounts=tiktok_accounts
                    ),
                    "campaign_id": campaign_id,
                    "script": script_payload,
                    "recording_script": recording_script.model_dump(mode="json")
                    if recording_script
                    else None,
                    "review_plan": workflow_result["review_plan"],
                    "caption_draft": caption_draft,
                    "editable_content": caption_draft,
                    "status": "running",
                    "current_step": current_step,
                    "progress": progress,
                    "publish": {
                        "requested": publish_to_tiktok,
                        "status": "ready_to_publish"
                        if publish_to_tiktok
                        and telegram_link
                        and active_tiktok_accounts
                        else "auth_required"
                        if publish_to_tiktok
                        else "not_requested",
                        "requires_tiktok_auth": not bool(active_tiktok_accounts),
                        "requires_telegram_auth": telegram_link is None,
                    },
                }
            )

        return {
            "status": "success",
            "jobs": jobs,
            "warnings": warnings,
        }

    @classmethod
    async def _list_job_rows(
        cls, *, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
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
            metadata = row.get("metadata") or {}
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
            metadata = row.get("metadata") or {}
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
        input_data = job_row.get("input_data") or {}
        output_data = job_row.get("output_data") or {}
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
            "job_id": workflow_id,
            "workflow_id": workflow_id,
            "type": job_row.get("type"),
            "status": job_row.get("status"),
            "current_step": job_row.get("current_step"),
            "progress": progress,
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
        rows = await cls._list_job_rows(user_id=user_id, limit=limit)
        rows = [
            await cls._refresh_live_status(
                temporal_client=temporal_client,
                job_row=row,
            )
            for row in rows
        ]
        workflow_ids = [str(row.get("workflow_id") or "") for row in rows]
        media_lookup = await cls._load_media_by_workflow(
            workflow_ids=workflow_ids,
            user_id=user_id,
        )
        content_lookup = await cls._load_content_by_workflow(
            workflow_ids=workflow_ids,
            user_id=user_id,
        )
        tiktok_accounts = await cls._list_tiktok_accounts(user_id)
        jobs = [
            cls._serialize_job(
                row,
                media_lookup=media_lookup,
                content_lookup=content_lookup,
                tiktok_accounts=tiktok_accounts,
            )
            for row in rows
        ]
        return {"jobs": jobs}

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
        job = await cls.get_job(
            user_id=session.user_id,
            job_id=job_id,
            temporal_client=None,
        )
        if not job:
            raise ValueError("App review job not found")
        if job["type"] != "app_review_upload":
            raise ValueError("Only user-upload jobs accept manual video uploads")
        upload = await MediaStorageService().upload_bytes(
            data=data,
            content_type=content_type,
            asset_type="VIDEO",
            asset_kind="video",
            asset_origin="uploaded",
            generation_prompt=job.get("objective") or "Manual upload",
            user_id=session.user_id,
            persona_id=job.get("persona", {}).get("persona_id"),
            metadata={
                "workflow_id": job_id,
                "job_kind": "app_review",
                "source_url": job.get("source_url"),
            },
            file_name_hint=file_name,
        )
        if not upload or not upload.get("access_url"):
            raise ValueError("Failed to upload review video")
        await cls._update_job_output(
            workflow_id=job_id,
            user_id=session.user_id,
            status="completed",
            current_step="final_product_ready",
            progress=100,
            output_data={
                "video_url": upload["access_url"],
                "final_video_url": upload["access_url"],
                "download_url": upload["access_url"],
                "media_asset_id": upload.get("media_asset_id"),
            },
        )
        updated = await cls.get_job(
            user_id=session.user_id,
            job_id=job_id,
            temporal_client=None,
        )
        if not updated:
            raise ValueError("App review job not found")
        if (
            updated.get("publish", {}).get("requested")
            and updated.get("publish", {}).get("status")
            in {"ready_to_publish", "not_requested"}
            and updated.get("production", {}).get("ready")
        ):
            try:
                return await cls.publish_job_to_tiktok(
                    session=session,
                    job_id=job_id,
                )
            except ValueError:
                return updated
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

        post_config = {
            "id": job_id,
            "user_id": session.user_id,
            "content": job["content"]["body"] or job["objective"] or "App review",
            "platform": "tiktok",
            "media": [{"storage_url": video_url}],
            "scheduled_time": schedule_time,
            "theme": job["page_title"] or job["objective"] or "App Review",
            "hashtags": ["AppReview", "TikTokReview"],
        }
        persisted = await ContentPersistenceService.persist_scheduled_post(
            workflow_id=job_id,
            post_config=post_config,
        )
        publisher = PublisherService()
        try:
            publish_result = await publisher.publish(post_config)
        except Exception as exc:
            await cls._update_job_output(
                workflow_id=job_id,
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
            workflow_id=job_id,
            post_config=post_config,
            publish_result=publish_result,
        )
        await cls._update_job_output(
            workflow_id=job_id,
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
