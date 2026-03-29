"""
Bridge verified Telegram identities into real Supabase Auth users and sessions.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from config.settings import settings
from services.telegram_identity_service import TelegramIdentity


@dataclass(frozen=True)
class SupabaseAuthSession:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass(frozen=True)
class SupabaseAuthProvisionResult:
    user_id: str
    email: str
    status: str


class SupabaseAuthBridgeError(RuntimeError):
    pass


class SupabaseAuthBridgeCollisionError(SupabaseAuthBridgeError):
    pass


class SupabaseAuthBridgeService:
    ADMIN_TIMEOUT = 15.0
    TOKEN_TIMEOUT = 15.0

    @classmethod
    def _bridge_secret(cls) -> str:
        secret = (settings.TELEGRAM_AUTH_BRIDGE_SECRET or "").strip()
        if not secret or settings.is_placeholder_secret(secret):
            raise SupabaseAuthBridgeError(
                "TELEGRAM_AUTH_BRIDGE_SECRET is not configured."
            )
        return secret

    @classmethod
    def deterministic_password_for_user_id(cls, user_id: str) -> str:
        digest = hmac.new(
            cls._bridge_secret().encode("utf-8"),
            str(user_id).encode("utf-8"),
            hashlib.sha256,
        ).digest()
        encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"tg-bridge-{encoded}"

    @staticmethod
    def _admin_headers() -> Dict[str, str]:
        return {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _token_headers() -> Dict[str, str]:
        public_key = (settings.SUPABASE_KEY or "").strip() or settings.SUPABASE_SERVICE_ROLE_KEY
        return {
            "apikey": public_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _user_url(user_id: str) -> str:
        return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_id}"

    @staticmethod
    def _create_user_url() -> str:
        return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"

    @staticmethod
    def _token_url() -> str:
        return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"

    @classmethod
    def _metadata_for_identity(cls, identity: TelegramIdentity) -> tuple[Dict[str, Any], Dict[str, Any]]:
        user_metadata: Dict[str, Any] = {
            "provider": "telegram",
        }
        if identity.display_name:
            user_metadata["name"] = identity.display_name
            user_metadata["full_name"] = identity.display_name
        if identity.avatar_url:
            user_metadata["avatar_url"] = identity.avatar_url
        if identity.chat_id is not None:
            user_metadata["telegram_chat_id"] = str(identity.chat_id)
        if identity.telegram_username:
            user_metadata["telegram_username"] = identity.telegram_username

        app_metadata: Dict[str, Any] = {
            "provider": "telegram",
            "providers": ["telegram"],
        }
        if identity.chat_id is not None:
            app_metadata["telegram_chat_id"] = str(identity.chat_id)
        if identity.telegram_username:
            app_metadata["telegram_username"] = identity.telegram_username

        return user_metadata, app_metadata

    @classmethod
    def _admin_payload(cls, identity: TelegramIdentity) -> Dict[str, Any]:
        user_metadata, app_metadata = cls._metadata_for_identity(identity)
        return {
            "email": identity.email,
            "password": cls.deterministic_password_for_user_id(identity.user_id),
            "email_confirm": True,
            "user_metadata": user_metadata,
            "app_metadata": app_metadata,
            "role": "authenticated",
        }

    @classmethod
    def _raise_for_response(
        cls,
        response: httpx.Response,
        *,
        collision_user_id: Optional[str] = None,
        collision_email: Optional[str] = None,
    ) -> None:
        if response.status_code < 400:
            return

        try:
            payload = response.json()
        except ValueError:
            payload = {}
        detail = (
            payload.get("msg")
            or payload.get("message")
            or payload.get("error_description")
            or payload.get("error")
            or response.text
            or "Supabase Auth request failed"
        )
        normalized = str(detail).lower()
        if (
            "already registered" in normalized
            or "duplicate key" in normalized
            or "already exists" in normalized
            or "email exists" in normalized
        ):
            raise SupabaseAuthBridgeCollisionError(
                "Supabase Auth already has a different user for "
                f"{collision_email or 'the requested email'}."
            )
        raise SupabaseAuthBridgeError(str(detail))

    @classmethod
    def _response_message(cls, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        detail = (
            payload.get("msg")
            or payload.get("message")
            or payload.get("error_description")
            or payload.get("error")
            or response.text
            or ""
        )
        return str(detail).strip()

    @classmethod
    async def _fetch_admin_user(
        cls,
        client: httpx.AsyncClient,
        *,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        response = await client.get(cls._user_url(user_id), headers=cls._admin_headers())
        if response.status_code == 404:
            return None
        cls._raise_for_response(response)
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("user"), dict):
            return payload["user"]
        return payload if isinstance(payload, dict) else None

    @classmethod
    async def ensure_telegram_auth_user(
        cls,
        identity: TelegramIdentity,
    ) -> SupabaseAuthProvisionResult:
        payload = cls._admin_payload(identity)
        async with httpx.AsyncClient(timeout=cls.ADMIN_TIMEOUT) as client:
            existing = await cls._fetch_admin_user(client, user_id=identity.user_id)
            if existing:
                existing_email = str(existing.get("email") or "").strip().lower()
                if existing_email and existing_email != identity.email.lower():
                    raise SupabaseAuthBridgeCollisionError(
                        "Supabase Auth already has a different email for "
                        f"user {identity.user_id}."
                    )
                response = await client.put(
                    cls._user_url(identity.user_id),
                    headers=cls._admin_headers(),
                    json=payload,
                )
                cls._raise_for_response(
                    response,
                    collision_user_id=identity.user_id,
                    collision_email=identity.email,
                )
                return SupabaseAuthProvisionResult(
                    user_id=identity.user_id,
                    email=identity.email,
                    status="updated",
                )

            response = await client.post(
                cls._create_user_url(),
                headers=cls._admin_headers(),
                json={
                    **payload,
                    "id": identity.user_id,
                },
            )
            if response.status_code >= 400:
                detail = cls._response_message(response).lower()
                if "user not found" in detail:
                    response = await client.put(
                        cls._user_url(identity.user_id),
                        headers=cls._admin_headers(),
                        json=payload,
                    )
            cls._raise_for_response(
                response,
                collision_user_id=identity.user_id,
                collision_email=identity.email,
            )
            return SupabaseAuthProvisionResult(
                user_id=identity.user_id,
                email=identity.email,
                status="created",
            )

    @classmethod
    async def create_session_for_identity(
        cls,
        identity: TelegramIdentity,
    ) -> SupabaseAuthSession:
        password = cls.deterministic_password_for_user_id(identity.user_id)
        async with httpx.AsyncClient(timeout=cls.TOKEN_TIMEOUT) as client:
            response = await client.post(
                cls._token_url(),
                headers=cls._token_headers(),
                json={
                    "email": identity.email,
                    "password": password,
                },
            )
        cls._raise_for_response(response, collision_email=identity.email)
        payload = response.json()
        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        token_type = str(payload.get("token_type") or "bearer").strip() or "bearer"
        expires_in = int(payload.get("expires_in") or 0)
        if not access_token or not refresh_token or expires_in <= 0:
            raise SupabaseAuthBridgeError(
                "Supabase Auth did not return a valid access and refresh token pair."
            )
        return SupabaseAuthSession(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_in=expires_in,
        )

    @classmethod
    async def provision_identity_session(
        cls,
        identity: TelegramIdentity,
    ) -> SupabaseAuthSession:
        await cls.ensure_telegram_auth_user(identity)
        return await cls.create_session_for_identity(identity)
