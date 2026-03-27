"""
Persona API routes for reusable AI influencer records.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.security import require_internal_api_token
from services.errors import PersonaConfigurationError
from services.persona_registry_service import PersonaRegistryService

router = APIRouter(dependencies=[Depends(require_internal_api_token)])


class CreatePersonaRequest(BaseModel):
    persona_id: str
    display_name: str
    language: str
    tts_voice: str
    user_id: Optional[str] = None
    owner_key: Optional[str] = None
    avatar_prompt: Optional[str] = None
    tone_default: Optional[str] = None
    market_default: Optional[str] = None


class UpdatePersonaRequest(BaseModel):
    display_name: Optional[str] = None
    language: Optional[str] = None
    tts_voice: Optional[str] = None
    avatar_image_url: Optional[str] = None
    avatar_media_asset_id: Optional[str] = None
    avatar_source_type: Optional[str] = None
    avatar_prompt: Optional[str] = None
    heygen_avatar_id: Optional[str] = None
    status: Optional[str] = None
    video_count: Optional[int] = None
    tone_default: Optional[str] = None
    market_default: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_personas(
    status: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    owner_key: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    try:
        personas = await PersonaRegistryService.list_personas(
            status=status,
            user_id=user_id,
            owner_key=owner_key,
        )
    except PersonaConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "user_id": item.get("user_id"),
            "persona_id": item.get("persona_id"),
            "display_name": item.get("display_name"),
            "language": item.get("language"),
            "tts_voice": item.get("tts_voice"),
            "avatar_image_url": item.get("avatar_image_url"),
            "avatar_media_asset_id": item.get("avatar_media_asset_id"),
            "heygen_avatar_id": item.get("heygen_avatar_id"),
            "status": item.get("status"),
            "video_count": int(item.get("video_count") or 0),
            "created_at": item.get("created_at"),
        }
        for item in personas
    ]


@router.post("")
async def create_persona(payload: CreatePersonaRequest) -> Dict[str, Any]:
    try:
        return await PersonaRegistryService.create_persona(
            {
                "persona_id": payload.persona_id,
                "display_name": payload.display_name,
                "language": payload.language,
                "tts_voice": payload.tts_voice,
                "user_id": payload.user_id,
                "owner_key": payload.owner_key,
                "avatar_prompt": payload.avatar_prompt,
                "tone_default": payload.tone_default,
                "market_default": payload.market_default,
                "status": "draft",
            }
        )
    except PersonaConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{persona_id}")
async def get_persona(
    persona_id: str,
    user_id: Optional[str] = Query(default=None),
    owner_key: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    try:
        persona = await PersonaRegistryService.get_persona(
            persona_id,
            user_id=user_id,
            owner_key=owner_key,
        )
    except PersonaConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found.")
    return persona


@router.patch("/{persona_id}")
async def update_persona(
    persona_id: str,
    payload: UpdatePersonaRequest,
    user_id: Optional[str] = Query(default=None),
    owner_key: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    update_fields = {
        key: value for key, value in payload.model_dump().items() if value is not None
    }
    try:
        persona = await PersonaRegistryService.update_persona(
            persona_id,
            update_fields,
            user_id=user_id,
            owner_key=owner_key,
        )
    except PersonaConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found.")
    return persona


@router.get("/{persona_id}/readiness")
async def get_persona_readiness(
    persona_id: str,
    user_id: Optional[str] = Query(default=None),
    owner_key: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    try:
        return await PersonaRegistryService.get_readiness(
            persona_id,
            user_id=user_id,
            owner_key=owner_key,
        )
    except PersonaConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
