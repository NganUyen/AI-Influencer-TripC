"""
Customer-facing authenticated API surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from config.settings import settings
from services.account_connection_service import (
    AccountConnectionService,
    OAuthConfigurationError,
    OAuthExchangeError,
)
from services.assistant_service import AssistantService
from services.brand_profile_service import BrandProfileService
from services.customer_ai_backbone_service import CustomerAIBackboneService
from services.customer_auth_service import (
    CustomerAuthError,
    CustomerAuthService,
    CustomerSession,
)
from services.customer_campaign_service import CustomerCampaignService
from services.customer_media_service import CustomerMediaService
from services.workspace_service import WorkspaceService
from services.telegram_link_service import TelegramLinkService
from services.video_capture_handoff_service import (
    VideoCaptureHandoffError,
    VideoCaptureHandoffService,
)
from services.video_planner_handoff_service import VideoPlannerHandoffService
from services.persona_registry_service import PersonaRegistryService
from fastapi import Request

router = APIRouter()


async def require_customer_session(
    authorization: Optional[str] = Header(default=None),
) -> CustomerSession:
    try:
        return await CustomerAuthService.resolve_session(authorization)
    except CustomerAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


class BrandProfileRequest(BaseModel):
    product_name: str
    website_url: Optional[str] = None
    audience: Optional[str] = None
    offer_summary: Optional[str] = None
    tone_voice: Optional[str] = None
    campaign_goals: List[str] = []
    asset_urls: List[str] = []
    timezone: str = "UTC"
    posting_cadence: Dict[str, Any] = {}
    approval_preferences: Dict[str, Any] = {"mode": "review_first"}
    telegram_contact: Optional[str] = None
    onboarding_status: str = "completed"


class AssistantThreadRequest(BaseModel):
    title: Optional[str] = None


class AssistantMessageRequest(BaseModel):
    content: str


class CampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    target_platforms: List[str] = []
    connected_account_ids: List[str] = []
    content_pillars: List[str] = []
    cta_rules: Dict[str, Any] = {}
    execution_windows: Dict[str, Any] = {}
    source_thread_id: Optional[str] = None
    source_artifact_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    approved: bool
    feedback: str = ""


class AIBackboneSettingsRequest(BaseModel):
    access_mode: str
    openclaw_api_url: Optional[str] = None
    api_key: Optional[str] = None
    clear_api_key: bool = False


class ChatGPTOAuthLinkRequest(BaseModel):
    chatgpt_subject: str
    display_name: Optional[str] = None
    subscription_tier: str = "plus"


class TelegramLinkStartRequest(BaseModel):
    expires_in_minutes: int = 15


class VideoCaptureHandoffInspectRequest(BaseModel):
    token: str


class VideoCaptureHandoffCompleteRequest(BaseModel):
    token: str
    method: str
    notes: str = ""


class RecentMediaAssetResponse(BaseModel):
    asset_id: str
    persona_id: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    filename: Optional[str] = None
    title: Optional[str] = None
    access_url: Optional[str] = None
    created_at: Optional[str] = None


class PersonaStudioSessionRequest(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None


class PersonaStudioMessageRequest(BaseModel):
    content: str


class PersonaStudioCommitRequest(BaseModel):
    display_name: Optional[str] = None
    notes: str = ""


class ReviewEngineSourceValidateRequest(BaseModel):
    source_url: str


class ReviewEngineJobRequest(BaseModel):
    source_url: str
    objective: str
    target_personas: List[str]


class UpdatePersonaRequest(BaseModel):
    display_name: Optional[str] = None
    tts_voice: Optional[str] = None
    appearance_prompt_or_photo: Optional[str] = None
    language: Optional[str] = None


class RebuildAvatarRequest(BaseModel):
    appearance_prompt_or_photo: str


@router.get("/brand")
async def get_brand_profile(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    brand = await BrandProfileService.get_for_user(session.user_id)
    return {
        "brand_profile": brand,
        "customer": {
            "user_id": session.user_id,
            "email": session.email,
            "display_name": session.display_name,
        },
    }


@router.get("/workspace")
async def get_customer_workspace(
    request: Request,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    temporal_client = getattr(request.app.state, "temporal_client", None)
    return await WorkspaceService.get_workspace(
        user_id=session.user_id,
        customer={
            "user_id": session.user_id,
            "email": session.email,
            "display_name": session.display_name,
        },
        temporal_client=temporal_client,
    )


@router.put("/brand")
async def put_brand_profile(
    payload: BrandProfileRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    brand = await BrandProfileService.upsert_for_session(
        session,
        payload.model_dump(),
    )
    return {"brand_profile": brand}


@router.get("/telegram/link")
async def get_telegram_link_status(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    link = await TelegramLinkService.get_link_for_user(session.user_id)
    return {
        "linked": link is not None,
        "link": link,
    }


@router.post("/telegram/link/start")
async def start_telegram_link(
    payload: TelegramLinkStartRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    token = await TelegramLinkService.create_link_token(
        user_id=session.user_id,
        expires_in_minutes=payload.expires_in_minutes,
    )
    return token


@router.post("/video-capture/handoff/inspect")
async def inspect_video_capture_handoff(
    payload: VideoCaptureHandoffInspectRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        handoff = VideoCaptureHandoffService.inspect_token(
            payload.token,
            expected_user_id=session.user_id,
        )
    except VideoCaptureHandoffError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "handoff": {
            **handoff,
            "secure_collection_required": True,
            "allowed_methods": [
                "workspace_session_capture",
                "temporary_username_password",
                "guided_manual_login",
            ],
            "next_step": (
                "Collect credentials only inside the authenticated workspace UI. "
                "Do not send credentials in Telegram chat."
            ),
        }
    }


@router.post("/video-capture/handoff/complete")
async def complete_video_capture_handoff(
    payload: VideoCaptureHandoffCompleteRequest,
    request: Request,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    allowed_methods = {
        "workspace_session_capture",
        "temporary_username_password",
        "guided_manual_login",
    }
    if payload.method not in allowed_methods:
        raise HTTPException(
            status_code=400, detail="Unsupported handoff completion method."
        )

    try:
        handoff = VideoCaptureHandoffService.inspect_token(
            payload.token,
            expected_user_id=session.user_id,
        )
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://backend",
        ) as client:
            result = await VideoPlannerHandoffService.complete_authenticated_handoff(
                handoff_payload=handoff,
                method=payload.method,
                notes=payload.notes,
                backend_url="http://backend",
                http_client=client,
            )
    except VideoCaptureHandoffError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": result.get("status", "handoff_completed"),
        "message": result.get("message")
        or "Authenticated PC capture handoff completed. Return to Telegram and retry start.",
        "workflow_id": result.get("workflow_id"),
        "execution_mode": result.get("execution_mode"),
        "credential_handoff": result.get("credential_handoff"),
        "video_review_plan": result.get("video_review_plan"),
    }


@router.get("/media/{asset_id}/access-url")
async def get_media_access_url(
    asset_id: str,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        return await CustomerMediaService.get_access_url(
            user_id=session.user_id,
            asset_id=asset_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/social-accounts")
async def list_social_accounts(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    accounts = await AccountConnectionService.list_accounts(session.user_id)
    return {"accounts": accounts}


@router.post("/social-accounts/{platform}/oauth/start")
async def start_social_oauth(
    platform: str,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        return await AccountConnectionService.start_oauth(session, platform)
    except OAuthConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/social-accounts/{platform}/oauth/callback")
async def oauth_callback(
    platform: str,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> RedirectResponse:
    dashboard_url = (settings.FRONTEND_PUBLIC_URL or "http://localhost:3000").rstrip(
        "/"
    )
    if error:
        return RedirectResponse(
            url=(
                f"{dashboard_url}/dashboard?oauth_status=error"
                f"&platform={quote(platform)}&reason={quote(error)}"
            ),
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            url=(
                f"{dashboard_url}/dashboard?oauth_status=error"
                f"&platform={quote(platform)}&reason=missing_code_or_state"
            ),
            status_code=302,
        )
    try:
        await AccountConnectionService.complete_oauth(platform, code, state)
    except (OAuthConfigurationError, OAuthExchangeError) as exc:
        return RedirectResponse(
            url=(
                f"{dashboard_url}/dashboard?oauth_status=error"
                f"&platform={quote(platform)}&reason={quote(str(exc))}"
            ),
            status_code=302,
        )
    return RedirectResponse(
        url=f"{dashboard_url}/dashboard?oauth_status=success&platform={quote(platform)}",
        status_code=302,
    )


@router.post("/social-accounts/{social_account_id}/disconnect")
async def disconnect_social_account(
    social_account_id: str,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    await AccountConnectionService.disconnect_account(
        user_id=session.user_id,
        social_account_id=social_account_id,
    )
    return {"status": "disconnected", "social_account_id": social_account_id}


@router.get("/assistant/threads")
async def get_assistant_threads(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return {"threads": await AssistantService.list_threads(session.user_id)}


@router.post("/assistant/threads")
async def create_assistant_thread(
    payload: AssistantThreadRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    thread = await AssistantService.create_thread(session, title=payload.title)
    return {"thread": thread}


@router.get("/assistant/threads/{thread_id}/messages")
async def list_assistant_messages(
    thread_id: str,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    messages = await AssistantService.list_messages(session.user_id, thread_id)
    artifacts = await AssistantService.list_artifacts(session.user_id, thread_id)
    return {"messages": messages, "artifacts": artifacts}


@router.post("/assistant/threads/{thread_id}/messages")
async def post_assistant_message(
    thread_id: str,
    payload: AssistantMessageRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        result = await AssistantService.append_message(
            session,
            thread_id=thread_id,
            content=payload.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    messages = await AssistantService.list_messages(session.user_id, thread_id)
    artifacts = await AssistantService.list_artifacts(session.user_id, thread_id)
    return {
        **result,
        "messages": messages,
        "artifacts": artifacts,
    }


@router.get("/ai-backbone")
async def get_ai_backbone_settings(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return {"settings": await CustomerAIBackboneService.get_for_user(session.user_id)}


@router.put("/ai-backbone")
async def put_ai_backbone_settings(
    payload: AIBackboneSettingsRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        settings_payload = await CustomerAIBackboneService.upsert_for_session(
            session,
            payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"settings": settings_payload}


@router.post("/ai-backbone/chatgpt/oauth/link")
async def link_chatgpt_oauth(
    payload: ChatGPTOAuthLinkRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        settings_payload = await CustomerAIBackboneService.link_chatgpt_oauth(
            session,
            chatgpt_subject=payload.chatgpt_subject,
            display_name=payload.display_name,
            subscription_tier=payload.subscription_tier,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"settings": settings_payload}


@router.post("/ai-backbone/chatgpt/oauth/disconnect")
async def disconnect_chatgpt_oauth(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return {
        "settings": await CustomerAIBackboneService.disconnect_chatgpt_oauth(session)
    }


@router.get("/campaigns")
async def list_campaigns(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return {"campaigns": await CustomerCampaignService.list_campaigns(session.user_id)}


@router.post("/campaigns")
async def create_campaign(
    payload: CampaignRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        campaign = await CustomerCampaignService.create_campaign(
            session,
            payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"campaign": campaign}


@router.post("/campaigns/{campaign_id}/approve")
async def approve_campaign(
    campaign_id: str,
    payload: ApprovalRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        campaign = await CustomerCampaignService.approve_campaign(
            session,
            campaign_id=campaign_id,
            approved=payload.approved,
            feedback=payload.feedback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"campaign": campaign}


@router.post("/campaigns/{campaign_id}/launch")
async def launch_campaign(
    campaign_id: str,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        return await CustomerCampaignService.launch_campaign(session, campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/content")
async def list_customer_content(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return {"items": await WorkspaceService.list_content(session.user_id)}


@router.get("/approvals")
async def list_customer_approvals(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return {
        "approvals": await CustomerCampaignService.list_pending_approvals(
            session.user_id
        )
    }


@router.get("/personas")
async def list_customer_personas(
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    # This ensures personas are strictly filtered by the authenticated user's ID
    personas = await PersonaRegistryService.list_personas(user_id=session.user_id)
    return {
        "personas": [
            {
                "persona_id": item.get("persona_id"),
                "display_name": item.get("display_name"),
                "language": item.get("language"),
                "tts_voice": item.get("tts_voice"),
                "appearance_prompt_or_photo": item.get("appearance_prompt_or_photo"),
                "avatar_image_url": item.get("avatar_image_url"),
                "status": item.get("status"),
                "video_count": int(item.get("video_count") or 0),
                "created_at": item.get("created_at"),
            }
            for item in personas
        ]
    }


@router.get("/personas/{persona_id}/readiness")
async def get_customer_persona_readiness(
    persona_id: str,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return await PersonaRegistryService.get_readiness(
        persona_id,
        user_id=session.user_id,
    )


@router.patch("/personas/{persona_id}")
async def update_customer_persona(
    persona_id: str,
    payload: UpdatePersonaRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    fields_to_update = {
        k: v for k, v in payload.model_dump().items() if v is not None
    }
    if not fields_to_update:
        return {"status": "no_changes"}

    updated_persona = await PersonaRegistryService.update_persona(
        persona_id,
        fields_to_update,
        user_id=session.user_id,
    )
    if not updated_persona:
        raise HTTPException(status_code=404, detail="Persona not found or unauthorized")
        
    return {"persona": updated_persona}


@router.post("/personas/{persona_id}/rebuild-avatar")
async def rebuild_customer_persona_avatar(
    persona_id: str,
    payload: RebuildAvatarRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    from services.image_generation_service import ImageGenerationService
    from services.heygen_service import HeyGenService
    
    # 1. Update the prompt first
    await PersonaRegistryService.update_persona(
        persona_id,
        {"appearance_prompt_or_photo": payload.appearance_prompt_or_photo},
        user_id=session.user_id,
    )
    
    # 2. Generate Image
    image_service = ImageGenerationService(provider="replicate")
    try:
        images = await image_service.generate_images(
            f"A clear, uncropped, front-facing portrait of {payload.appearance_prompt_or_photo}. High quality, photorealistic, even studio lighting. Direct gaze.",
            count=1,
            user_id=session.user_id,
        )
    finally:
        await image_service.close()
        
    if not images:
        raise HTTPException(status_code=500, detail="Failed to generate avatar image")
        
    avatar_url = images[0]
    
    # 3. Create HeyGen Avatar
    heygen_service = HeyGenService()
    try:
        avatar_name = f"{persona_id}-avatar"
        heygen_avatar_id = await heygen_service.create_avatar(
            avatar_url,
            avatar_name=avatar_name,
            user_id=session.user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create HeyGen Avatar: {exc}")
        
    # 4. Save and return
    updated_persona = await PersonaRegistryService.update_persona(
        persona_id,
        {
            "avatar_image_url": avatar_url,
            "heygen_avatar_id": heygen_avatar_id,
            "avatar_source_type": "generated",
            "status": "ready"
        },
        user_id=session.user_id,
    )
    
    return {"persona": updated_persona}


@router.get("/system/summary")
async def get_system_summary(
    request: Request,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    return await WorkspaceService.get_system_summary(
        user_id=session.user_id,
        temporal_client=getattr(request.app.state, "temporal_client", None),
    )


@router.get("/media/recent")
async def list_recent_customer_media(
    session: CustomerSession = Depends(require_customer_session),
    asset_type: Optional[str] = Query(default="video"),
    limit: int = Query(default=10, ge=1, le=20),
) -> Dict[str, Any]:
    assets = await CustomerMediaService.list_recent_assets(
        user_id=session.user_id,
        asset_type=asset_type,
        limit=limit,
    )
    return {
        "assets": [RecentMediaAssetResponse(**asset).model_dump() for asset in assets]
    }


@router.get("/system/workflows")
async def list_system_workflows(
    request: Request,
    session: CustomerSession = Depends(require_customer_session),
    limit: int = 20,
) -> Dict[str, Any]:
    return await WorkspaceService.get_workflow_summary(
        user_id=session.user_id,
        temporal_client=getattr(request.app.state, "temporal_client", None),
        limit=limit,
    )


@router.post("/persona-studio/sessions")
async def create_persona_studio_session(
    _payload: PersonaStudioSessionRequest,
    _session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=501,
        detail="Persona Studio write APIs are reserved for Phase 2.",
    )


@router.post("/persona-studio/sessions/{session_id}/messages")
async def append_persona_studio_message(
    session_id: str,
    _payload: PersonaStudioMessageRequest,
    _session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=501,
        detail=f"Persona Studio session '{session_id}' is reserved for Phase 2.",
    )


@router.post("/persona-studio/sessions/{session_id}/commit")
async def commit_persona_studio_session(
    session_id: str,
    _payload: PersonaStudioCommitRequest,
    _session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=501,
        detail=f"Persona Studio session '{session_id}' commit is reserved for Phase 2.",
    )


@router.post("/review-engine/source/validate")
async def validate_review_engine_source(
    payload: ReviewEngineSourceValidateRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        from services.website_review_service import WebsiteReviewService
        result = await WebsiteReviewService.review_url(
            url=payload.source_url,
            user_id=session.user_id,
        )
        return {
            "normalized_url": result.normalized_url,
            "page_title": result.page_title,
            "visible_features": [f.model_dump() for f in result.visible_features] if result.visible_features else []
        }
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Source validation failed with exception:", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Source validation failed: {exc}",
        )


@router.post("/review-engine/jobs")
async def create_review_engine_job(
    payload: ReviewEngineJobRequest,
    session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    try:
        from services.website_review_service import WebsiteReviewService
        from services.script_service import ScriptService
        from services.customer_campaign_service import CustomerCampaignService
        from services.persona_registry_service import PersonaRegistryService
        from services.contracts import VideoReviewPlanContract
        
        script_service = ScriptService()
        
        page_review_contract = await WebsiteReviewService.review_url(
            url=payload.source_url,
            objective=payload.objective,
            user_id=session.user_id,
        )
        page_review_payload = page_review_contract.model_dump(mode="json")
        
        results = []
        for persona_id in payload.target_personas:
            persona = await PersonaRegistryService.get_persona(persona_id, session.user_id)
            if not persona:
                continue
                
            review_plan = {
                "objective": payload.objective,
                "target_url": payload.source_url,
                "language": persona.get("language") or "English",
                "persona_id": persona_id,
                "execution_mode": "autonomous_screen_recording",
                "page_review": page_review_payload
            }
            
            script_contract, _ = await script_service.generate_script_from_review_plan(
                app_name=page_review_contract.page_title or payload.source_url,
                review_plan=review_plan,
                persona_config=persona
            )
            
            campaign_payload = {
                "name": f"Review of {page_review_contract.page_title or payload.source_url} - {persona.get('display_name', persona_id)}",
                "description": payload.objective,
                "content_pillars": ["Review"],
                "target_platforms": ["tiktok"]
            }
            campaign = await CustomerCampaignService.create_campaign(
                session=session,
                payload=campaign_payload
            )
            
            results.append({
                "persona_id": persona_id,
                "campaign_id": campaign["id"],
                "script": script_contract.model_dump()
            })
            
        return {
            "status": "success",
            "jobs": results
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Job creation failed: {exc}"
        )


@router.get("/review-engine/jobs/{job_id}")
async def get_review_engine_job(
    job_id: str,
    _session: CustomerSession = Depends(require_customer_session),
) -> Dict[str, Any]:
    raise HTTPException(
        status_code=501,
        detail=f"Review Engine job '{job_id}' is reserved for Phase 2.",
    )
