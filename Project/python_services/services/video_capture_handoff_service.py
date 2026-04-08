"""Secure workspace handoff tokens for authenticated PC capture."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from config.settings import settings
from utils import jwt_compat as jwt


class VideoCaptureHandoffError(RuntimeError):
    pass


class VideoCaptureHandoffService:
    AUDIENCE = "video_capture_handoff"
    DEFAULT_TTL_SECONDS = 15 * 60

    @classmethod
    def create_token(
        cls,
        *,
        user_id: str,
        plan_id: str,
        objective: str,
        target_url: str,
        persona_id: str,
        execution_mode: str,
        review_plan: Dict[str, Any],
        telegram_chat_id: Optional[str] = None,
        expires_in_seconds: int | None = None,
    ) -> Dict[str, Any]:
        ttl_seconds = max(60, int(expires_in_seconds or cls.DEFAULT_TTL_SECONDS))
        now = int(time.time())
        payload = {
            "aud": cls.AUDIENCE,
            "sub": user_id,
            "iat": now,
            "exp": now + ttl_seconds,
            "plan_id": plan_id,
            "objective": objective,
            "target_url": target_url,
            "persona_id": persona_id,
            "execution_mode": execution_mode,
            "review_plan": review_plan,
            "telegram_chat_id": telegram_chat_id,
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(payload["exp"]))
        return {
            "token": token,
            "expires_at": expires_at,
            "handoff_url": cls.build_handoff_url(token),
        }

    @classmethod
    def inspect_token(
        cls,
        token: str,
        *,
        expected_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=["HS256"],
                audience=cls.AUDIENCE,
            )
        except Exception as exc:
            raise VideoCaptureHandoffError(f"Invalid capture handoff token: {exc}") from exc

        user_id = str(payload.get("sub") or "").strip()
        if not user_id:
            raise VideoCaptureHandoffError("Capture handoff token is missing a user binding.")
        if expected_user_id and expected_user_id != user_id:
            raise VideoCaptureHandoffError(
                "This secure handoff link belongs to a different workspace user."
            )

        return {
            "user_id": user_id,
            "plan_id": str(payload.get("plan_id") or "").strip(),
            "objective": str(payload.get("objective") or "").strip(),
            "target_url": str(payload.get("target_url") or "").strip(),
            "persona_id": str(payload.get("persona_id") or "").strip(),
            "execution_mode": str(payload.get("execution_mode") or "").strip(),
            "review_plan": payload.get("review_plan")
            if isinstance(payload.get("review_plan"), dict)
            else None,
            "telegram_chat_id": str(payload.get("telegram_chat_id") or "").strip() or None,
            "expires_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ",
                time.gmtime(int(payload.get("exp") or 0)),
            ),
        }

    @classmethod
    def build_handoff_url(cls, token: str) -> str:
        frontend_url = (settings.FRONTEND_PUBLIC_URL or "http://localhost:3000").rstrip("/")
        query = urlencode({"token": token})
        return f"{frontend_url}/capture-handoff?{query}"
