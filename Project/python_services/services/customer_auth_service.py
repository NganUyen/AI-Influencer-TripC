"""
Customer session validation against Supabase Auth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from config.settings import settings
from services.database_service import DatabaseService
from utils import jwt_compat as jwt


@dataclass
class CustomerSession:
    user_id: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    access_token: str
    raw_user: Dict[str, Any]


class CustomerAuthError(RuntimeError):
    pass


class CustomerAuthService:
    @staticmethod
    def _normalize_token(authorization: Optional[str]) -> Optional[str]:
        if not authorization:
            return None
        value = authorization.strip()
        if not value:
            return None
        if value.lower().startswith("bearer "):
            token = value.split(" ", 1)[1].strip()
            return token or None
        return value

    @classmethod
    def _build_session(cls, token: str, payload: Dict[str, Any]) -> CustomerSession:
        user_id = str(payload.get("id") or payload.get("sub") or "").strip()
        email = str(payload.get("email") or "").strip()
        if not user_id or not email:
            raise CustomerAuthError("Supabase session did not include a valid user")

        user_metadata = payload.get("user_metadata") or {}
        display_name = (
            user_metadata.get("full_name")
            or user_metadata.get("name")
            or payload.get("phone")
            or email.split("@", 1)[0]
        )
        avatar_url = user_metadata.get("avatar_url")

        return CustomerSession(
            user_id=user_id,
            email=email,
            display_name=str(display_name).strip() if display_name else None,
            avatar_url=str(avatar_url).strip() if avatar_url else None,
            access_token=token,
            raw_user=payload,
        )

    @classmethod
    def _resolve_local_jwt_session(cls, token: str) -> CustomerSession:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as exc:
            raise CustomerAuthError("Customer session is invalid or expired") from exc
        if settings.is_production_like or not payload.get("mock_telegram_login"):
            raise CustomerAuthError("Customer session is invalid or expired")
        return cls._build_session(token, payload)

    @classmethod
    async def resolve_session(
        cls,
        authorization: Optional[str],
    ) -> CustomerSession:
        token = cls._normalize_token(authorization)
        if not token:
            raise CustomerAuthError("Missing customer session token")

        auth_base = settings.SUPABASE_URL.rstrip("/")
        user_url = f"{auth_base}/auth/v1/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(user_url, headers=headers)
        except httpx.HTTPError:
            session = cls._resolve_local_jwt_session(token)
            await cls.ensure_user_record(session)
            return session

        if response.status_code == 200:
            session = cls._build_session(token, response.json())
            await cls.ensure_user_record(session)
            return session

        session = cls._resolve_local_jwt_session(token)
        await cls.ensure_user_record(session)
        return session

    @classmethod
    async def ensure_user_record(cls, session: CustomerSession) -> None:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.users (id, email, name, avatar_url)
                VALUES ($1::uuid, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE
                SET email = EXCLUDED.email,
                    name = COALESCE(EXCLUDED.name, public.users.name),
                    avatar_url = COALESCE(EXCLUDED.avatar_url, public.users.avatar_url),
                    updated_at = NOW()
                """,
                session.user_id,
                session.email,
                session.display_name,
                session.avatar_url,
            )
