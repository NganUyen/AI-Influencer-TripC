"""
Telegram customer auth and token-completion API.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from services.database_service import DatabaseService
from services.supabase_auth_bridge_service import (
    SupabaseAuthBridgeCollisionError,
    SupabaseAuthBridgeError,
    SupabaseAuthBridgeService,
)
from services.telegram_identity_service import TelegramIdentity, TelegramIdentityService
from services.telegram_link_service import TelegramLinkError, TelegramLinkService
from utils import jwt_compat as jwt

router = APIRouter()


class TelegramLoginRequest(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class AnonymousLinkStartRequest(BaseModel):
    expires_in_minutes: int = 15


class TelegramLinkCompleteRequest(BaseModel):
    start_token: str


class TelegramAuthUser(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class TelegramLinkCompleteResponse(BaseModel):
    status: Literal["pending", "authenticated", "expired"]
    expires_at: Optional[str] = None
    authenticated_at: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    user: Optional[TelegramAuthUser] = None


def verify_telegram_hash(data: Dict[str, Any], bot_token: str) -> bool:
    data_copy = data.copy()
    check_hash = data_copy.pop("hash")
    items = sorted([f"{k}={v}" for k, v in data_copy.items() if v is not None])
    data_check_string = "\n".join(items)

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_v = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hash_v == check_hash


def generate_supabase_jwt(
    user_id: str,
    email: str,
    *,
    display_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    expires_in: int = 3600 * 24 * 7,
    mock_session: bool = False,
) -> str:
    """Generate a development-only JWT compatible with the current customer session model."""
    now = int(time.time())
    user_metadata: Dict[str, Any] = {}
    if display_name:
        user_metadata["name"] = display_name
        user_metadata["full_name"] = display_name
    if avatar_url:
        user_metadata["avatar_url"] = avatar_url

    payload = {
        "aud": "authenticated",
        "exp": now + expires_in,
        "iat": now,
        "iss": settings.SUPABASE_URL,
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "app_metadata": {
            "provider": "telegram_dev_mock" if mock_session else "telegram",
            "providers": ["telegram_dev_mock"] if mock_session else ["telegram"],
        },
        "user_metadata": user_metadata,
    }
    if mock_session:
        payload["mock_telegram_login"] = True
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def _display_name_from_payload(payload: TelegramLoginRequest) -> str:
    return payload.first_name + (f" {payload.last_name}" if payload.last_name else "")


def _validate_telegram_login_payload(payload: TelegramLoginRequest) -> None:
    is_mock = _is_mock_telegram_login(payload)
    if not is_mock and not verify_telegram_hash(
        payload.model_dump(),
        settings.TELEGRAM_BOT_TOKEN,
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram hash")

    if time.time() - payload.auth_date > 86400:
        raise HTTPException(status_code=401, detail="Telegram login session expired")


def _is_mock_telegram_login(payload: TelegramLoginRequest) -> bool:
    return payload.hash == "__MOCK_DEV_LOGIN__"


def _build_auth_response(
    identity: TelegramIdentity,
    *,
    access_token: str,
    refresh_token: Optional[str] = None,
    token_type: str = "bearer",
    expires_in: Optional[int] = None,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "access_token": access_token,
        "token_type": token_type,
        "user": {
            "id": identity.user_id,
            "email": identity.email,
            "name": identity.display_name,
            "avatar_url": identity.avatar_url,
        },
    }
    if refresh_token:
        response["refresh_token"] = refresh_token
    if expires_in is not None:
        response["expires_in"] = expires_in
    return response


def _build_mock_auth_response(identity: TelegramIdentity) -> Dict[str, Any]:
    access_token = generate_supabase_jwt(
        identity.user_id,
        identity.email,
        display_name=identity.display_name,
        avatar_url=identity.avatar_url,
        mock_session=True,
    )
    return _build_auth_response(identity, access_token=access_token)


async def _build_supabase_auth_response(identity: TelegramIdentity) -> Dict[str, Any]:
    try:
        session = await SupabaseAuthBridgeService.provision_identity_session(identity)
    except SupabaseAuthBridgeCollisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SupabaseAuthBridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return _build_auth_response(
        identity,
        access_token=session.access_token,
        refresh_token=session.refresh_token,
        token_type=session.token_type,
        expires_in=session.expires_in,
    )


@router.post("/login")
async def telegram_login(payload: TelegramLoginRequest):
    _validate_telegram_login_payload(payload)
    is_mock = _is_mock_telegram_login(payload)

    pool = await DatabaseService.get_pool()
    async with pool.acquire() as conn:
        identity = await TelegramIdentityService.resolve_or_create_identity(
            conn,
            chat_id=payload.id,
            telegram_username=payload.username,
            display_name=_display_name_from_payload(payload),
            avatar_url=payload.photo_url,
        )
        await TelegramIdentityService.upsert_telegram_link(
            conn,
            chat_id=payload.id,
            user_id=identity.user_id,
            telegram_username=payload.username,
        )

    if is_mock:
        return _build_mock_auth_response(identity)

    return await _build_supabase_auth_response(identity)


@router.post("/link/start")
async def start_anonymous_telegram_link(payload: AnonymousLinkStartRequest):
    ttl_minutes = max(1, min(payload.expires_in_minutes, 60))
    return await TelegramLinkService.create_link_token(
        user_id=None,
        expires_in_minutes=ttl_minutes,
    )


@router.post("/link/complete", response_model=TelegramLinkCompleteResponse)
async def complete_anonymous_telegram_link(payload: TelegramLinkCompleteRequest):
    try:
        completion = await TelegramLinkService.get_link_token_completion(
            payload.start_token
        )
    except TelegramLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status = completion["status"]
    if status != "authenticated":
        return completion

    pool = await DatabaseService.get_pool()
    async with pool.acquire() as conn:
        identity = await TelegramIdentityService.get_identity_for_user_id(
            conn,
            user_id=completion["user_id"],
        )

    if identity is None:
        raise HTTPException(
            status_code=409,
            detail="Linked Telegram user could not be resolved for sign-in.",
        )

    return {
        "status": "authenticated",
        "expires_at": completion.get("expires_at"),
        "authenticated_at": completion.get("authenticated_at"),
        **(await _build_supabase_auth_response(identity)),
    }
