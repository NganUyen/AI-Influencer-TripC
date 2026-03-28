"""
Telegram Web Login API.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
import uuid

import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from services.database_service import DatabaseService
from services.telegram_link_service import TelegramLinkService

router = APIRouter()


class TelegramLoginRequest(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


def verify_telegram_hash(data: Dict[str, Any], bot_token: str) -> bool:
    data_copy = data.copy()
    check_hash = data_copy.pop("hash")
    # All fields except hash, sorted alphabetically, key=value format
    items = sorted([f"{k}={v}" for k, v in data_copy.items() if v is not None])
    data_check_string = "\n".join(items)

    # Secret key is SHA256 of bot token
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_v = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hash_v == check_hash


def generate_supabase_jwt(
    user_id: str, email: str, expires_in: int = 3600 * 24 * 7
) -> str:
    """Generate a JWT compatible with Supabase's auth structure."""
    now = int(time.time())
    payload = {
        "aud": "authenticated",
        "exp": now + expires_in,
        "iat": now,
        "iss": settings.SUPABASE_URL,
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "app_metadata": {"provider": "telegram", "providers": ["telegram"]},
        "user_metadata": {},
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


@router.post("/login")
async def telegram_login(payload: TelegramLoginRequest):
    # 1. Verify hash
    if not verify_telegram_hash(payload.model_dump(), settings.TELEGRAM_BOT_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid Telegram hash")

    # 2. Check for stale login (expired if older than 24h)
    if time.time() - payload.auth_date > 86400:
        raise HTTPException(status_code=401, detail="Telegram login session expired")

    chat_id = payload.id
    display_name = payload.first_name + (
        f" {payload.last_name}" if payload.last_name else ""
    )
    email = f"tg_{chat_id}@ai-influencer.invalid"

    pool = await DatabaseService.get_pool()
    async with pool.acquire() as conn:
        # Check if already linked
        row = await conn.fetchrow(
            "SELECT user_id FROM public.telegram_user_links WHERE chat_id = $1 AND revoked_at IS NULL",
            chat_id,
        )

        if row:
            user_id = str(row["user_id"])
        else:
            # Create a new user record if not exists
            # We use a deterministic UUID based on chat_id to keep it stable
            user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"telegram:{chat_id}"))

            async with conn.transaction():
                # Ensure user exists in public.users
                await conn.execute(
                    """
                    INSERT INTO public.users (id, email, name, avatar_url)
                    VALUES ($1::uuid, $2, $3, $4)
                    ON CONFLICT (id) DO UPDATE
                    SET email = EXCLUDED.email,
                        name = COALESCE(EXCLUDED.name, public.users.name),
                        avatar_url = COALESCE(EXCLUDED.avatar_url, public.users.avatar_url)
                    """,
                    user_id,
                    email,
                    display_name,
                    payload.photo_url,
                )

                # Link Telegram account
                await conn.execute(
                    """
                    INSERT INTO public.telegram_user_links (
                        chat_id,
                        user_id,
                        telegram_username,
                        linked_at,
                        last_verified_at
                    )
                    VALUES ($1, $2::uuid, $3, NOW(), NOW())
                    ON CONFLICT (chat_id) DO UPDATE
                    SET user_id = EXCLUDED.user_id,
                        telegram_username = EXCLUDED.telegram_username,
                        last_verified_at = NOW(),
                        revoked_at = NULL
                    """,
                    chat_id,
                    user_id,
                    payload.username,
                )

    # Generate the access token
    access_token = generate_supabase_jwt(user_id, email)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": email,
            "name": display_name,
            "avatar_url": payload.photo_url,
        },
    }
