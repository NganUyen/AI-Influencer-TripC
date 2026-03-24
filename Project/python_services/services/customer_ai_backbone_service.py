"""
Customer-selectable OpenClaw backbone settings and secure credential resolution.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from chatgpt_connector.auth import ConnectorAuthService
from config.settings import settings
from services.customer_auth_service import CustomerSession
from services.customer_token_vault import CustomerTokenVault
from services.database_service import DatabaseService


ACCESS_MODE_PLATFORM_MANAGED = "platform_managed"
ACCESS_MODE_CUSTOMER_API_KEY = "customer_api_key"
ACCESS_MODE_CHATGPT_OAUTH = "chatgpt_oauth"
VALID_ACCESS_MODES = {
    ACCESS_MODE_PLATFORM_MANAGED,
    ACCESS_MODE_CUSTOMER_API_KEY,
    ACCESS_MODE_CHATGPT_OAUTH,
}
VALID_CHATGPT_SUBSCRIPTION_TIERS = {"plus", "pro"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_optional_url(value: Any) -> Optional[str]:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("OpenClaw API URL must be a valid http or https URL")
    return normalized.rstrip("/")


def _isoformat(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _is_connector_session_expired(expires_at: Any) -> bool:
    if not isinstance(expires_at, datetime):
        return False
    return expires_at <= _utcnow()


class CustomerAIBackboneService:
    @classmethod
    async def _get_row(cls, user_id: str) -> Optional[Any]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                """
                SELECT *
                FROM public.customer_ai_backbone_settings
                WHERE user_id = $1::uuid
                LIMIT 1
                """,
                user_id,
            )

    @classmethod
    async def _get_chatgpt_link(
        cls,
        user_id: str,
        preferred_subject: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = None
            if preferred_subject:
                row = await conn.fetchrow(
                    """
                    SELECT chatgpt_subject, user_id, display_name, session_id, linked_at, last_used_at, active
                    FROM public.chatgpt_oauth_links
                    WHERE user_id = $1
                      AND chatgpt_subject = $2
                      AND active = TRUE
                    LIMIT 1
                    """,
                    user_id,
                    preferred_subject,
                )
            if row is None:
                row = await conn.fetchrow(
                    """
                    SELECT chatgpt_subject, user_id, display_name, session_id, linked_at, last_used_at, active
                    FROM public.chatgpt_oauth_links
                    WHERE user_id = $1
                      AND active = TRUE
                    ORDER BY last_used_at DESC NULLS LAST, linked_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    user_id,
                )

        if row is None:
            return None

        return {
            "chatgpt_subject": row["chatgpt_subject"],
            "user_id": row["user_id"],
            "display_name": row["display_name"],
            "session_id": row["session_id"],
            "linked_at": _isoformat(row["linked_at"]),
            "last_used_at": _isoformat(row["last_used_at"]),
            "active": bool(row["active"]),
        }

    @classmethod
    def _default_payload(cls) -> Dict[str, Any]:
        return {
            "access_mode": ACCESS_MODE_PLATFORM_MANAGED,
            "workspace_default": {
                "api_url": settings.OPENCLAW_API_URL.rstrip("/"),
                "has_api_key": bool(settings.OPENCLAW_API_KEY),
            },
            "customer_api": {
                "api_url": settings.OPENCLAW_API_URL.rstrip("/"),
                "has_api_key": False,
                "updated_at": None,
            },
            "chatgpt_oauth": {
                "linked": False,
                "session_ready": False,
                "chatgpt_subject": None,
                "display_name": None,
                "subscription_tier": None,
                "linked_at": None,
                "last_used_at": None,
                "session_expires_at": None,
            },
            "effective_status": {
                "ready": True,
                "message": "Using workspace-managed OpenClaw access.",
            },
        }

    @classmethod
    def _build_mode_status(
        cls,
        access_mode: str,
        has_customer_api_key: bool,
        has_connector_session: bool,
        connector_session_expires_at: Any,
        chatgpt_linked: bool,
    ) -> Dict[str, Any]:
        if access_mode == ACCESS_MODE_CUSTOMER_API_KEY:
            if has_customer_api_key:
                return {
                    "ready": True,
                    "message": "Using the customer-provided OpenClaw API key.",
                }
            return {
                "ready": False,
                "message": "Add your OpenClaw API key before switching to customer-managed access.",
            }

        if access_mode == ACCESS_MODE_CHATGPT_OAUTH:
            if not chatgpt_linked or not has_connector_session:
                return {
                    "ready": False,
                    "message": "Link a GPT Plus or Pro account before using connector-backed OAuth access.",
                }
            if _is_connector_session_expired(connector_session_expires_at):
                return {
                    "ready": False,
                    "message": "Your GPT OAuth session expired. Reconnect it from the dashboard.",
                }
            return {
                "ready": True,
                "message": "Using connector-backed GPT OAuth access.",
            }

        return {
            "ready": True,
            "message": "Using workspace-managed OpenClaw access.",
        }

    @classmethod
    async def get_for_user(cls, user_id: str) -> Dict[str, Any]:
        payload = cls._default_payload()
        row = await cls._get_row(user_id)
        if row is None:
            link = await cls._get_chatgpt_link(user_id)
            if link:
                payload["chatgpt_oauth"] = {
                    "linked": True,
                    "session_ready": False,
                    "chatgpt_subject": link["chatgpt_subject"],
                    "display_name": link["display_name"],
                    "subscription_tier": None,
                    "linked_at": link["linked_at"],
                    "last_used_at": link["last_used_at"],
                    "session_expires_at": None,
                }
            return payload

        preferred_subject = _normalize_optional_text(row["chatgpt_subject"])
        link = await cls._get_chatgpt_link(user_id, preferred_subject=preferred_subject)

        access_mode = row["access_mode"] or ACCESS_MODE_PLATFORM_MANAGED
        has_customer_api_key = bool(row["encrypted_openclaw_api_key"])
        has_connector_session = bool(row["encrypted_connector_session_token"])
        connector_session_expires_at = row["connector_session_expires_at"]

        payload["access_mode"] = access_mode
        payload["customer_api"] = {
            "api_url": row["openclaw_api_url"] or settings.OPENCLAW_API_URL.rstrip("/"),
            "has_api_key": has_customer_api_key,
            "updated_at": _isoformat(row["updated_at"]),
        }
        payload["chatgpt_oauth"] = {
            "linked": bool(link),
            "session_ready": bool(
                has_connector_session and not _is_connector_session_expired(connector_session_expires_at)
            ),
            "chatgpt_subject": link["chatgpt_subject"] if link else preferred_subject,
            "display_name": (link or {}).get("display_name")
            or row["chatgpt_display_name"],
            "subscription_tier": row["chatgpt_subscription_tier"],
            "linked_at": (link or {}).get("linked_at"),
            "last_used_at": (link or {}).get("last_used_at"),
            "session_expires_at": _isoformat(connector_session_expires_at),
        }
        payload["effective_status"] = cls._build_mode_status(
            access_mode=access_mode,
            has_customer_api_key=has_customer_api_key,
            has_connector_session=has_connector_session,
            connector_session_expires_at=connector_session_expires_at,
            chatgpt_linked=bool(link),
        )
        return payload

    @classmethod
    def _normalize_access_mode(cls, value: Any) -> str:
        normalized = _normalize_optional_text(value) or ACCESS_MODE_PLATFORM_MANAGED
        if normalized not in VALID_ACCESS_MODES:
            raise ValueError("Unsupported AI backbone access mode")
        return normalized

    @classmethod
    def _normalize_subscription_tier(cls, value: Any) -> str:
        normalized = (_normalize_optional_text(value) or "plus").lower()
        if normalized not in VALID_CHATGPT_SUBSCRIPTION_TIERS:
            raise ValueError("Subscription tier must be either plus or pro")
        return normalized

    @classmethod
    async def _persist_settings(
        cls,
        user_id: str,
        values: Dict[str, Any],
    ) -> None:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.customer_ai_backbone_settings (
                    user_id,
                    access_mode,
                    openclaw_api_url,
                    encrypted_openclaw_api_key,
                    chatgpt_subject,
                    chatgpt_display_name,
                    chatgpt_subscription_tier,
                    encrypted_connector_session_token,
                    connector_session_id,
                    connector_session_expires_at,
                    metadata
                )
                VALUES (
                    $1::uuid,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9,
                    $10,
                    $11::jsonb
                )
                ON CONFLICT (user_id) DO UPDATE
                SET access_mode = EXCLUDED.access_mode,
                    openclaw_api_url = EXCLUDED.openclaw_api_url,
                    encrypted_openclaw_api_key = EXCLUDED.encrypted_openclaw_api_key,
                    chatgpt_subject = EXCLUDED.chatgpt_subject,
                    chatgpt_display_name = EXCLUDED.chatgpt_display_name,
                    chatgpt_subscription_tier = EXCLUDED.chatgpt_subscription_tier,
                    encrypted_connector_session_token = EXCLUDED.encrypted_connector_session_token,
                    connector_session_id = EXCLUDED.connector_session_id,
                    connector_session_expires_at = EXCLUDED.connector_session_expires_at,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                """,
                user_id,
                values["access_mode"],
                values["openclaw_api_url"],
                values["encrypted_openclaw_api_key"],
                values["chatgpt_subject"],
                values["chatgpt_display_name"],
                values["chatgpt_subscription_tier"],
                values["encrypted_connector_session_token"],
                values["connector_session_id"],
                values["connector_session_expires_at"],
                json.dumps(values["metadata"] or {}, sort_keys=True),
            )

    @classmethod
    async def upsert_for_session(
        cls,
        session: CustomerSession,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        current = await cls._get_row(session.user_id)
        current_values = dict(current) if current is not None else {}

        access_mode = cls._normalize_access_mode(payload.get("access_mode"))
        openclaw_api_url = current_values.get("openclaw_api_url")
        if "openclaw_api_url" in payload:
            openclaw_api_url = _normalize_optional_url(payload.get("openclaw_api_url"))

        encrypted_openclaw_api_key = current_values.get("encrypted_openclaw_api_key")
        if payload.get("clear_api_key"):
            encrypted_openclaw_api_key = None
        api_key = _normalize_optional_text(payload.get("api_key"))
        if api_key:
            encrypted_openclaw_api_key = CustomerTokenVault.seal(
                {
                    "kind": "openclaw_api_key",
                    "api_key": api_key,
                    "issued_at": _utcnow().isoformat(),
                }
            )

        if access_mode == ACCESS_MODE_CUSTOMER_API_KEY and not encrypted_openclaw_api_key:
            raise ValueError("Customer-managed access requires an OpenClaw API key")

        if access_mode == ACCESS_MODE_CHATGPT_OAUTH:
            if not current_values.get("encrypted_connector_session_token"):
                raise ValueError("Link a GPT Plus or Pro account before enabling OAuth mode")
            if _is_connector_session_expired(current_values.get("connector_session_expires_at")):
                raise ValueError("Your GPT OAuth session expired. Reconnect it before enabling OAuth mode")

        values = {
            "access_mode": access_mode,
            "openclaw_api_url": openclaw_api_url,
            "encrypted_openclaw_api_key": encrypted_openclaw_api_key,
            "chatgpt_subject": current_values.get("chatgpt_subject"),
            "chatgpt_display_name": current_values.get("chatgpt_display_name"),
            "chatgpt_subscription_tier": current_values.get("chatgpt_subscription_tier"),
            "encrypted_connector_session_token": current_values.get("encrypted_connector_session_token"),
            "connector_session_id": current_values.get("connector_session_id"),
            "connector_session_expires_at": current_values.get("connector_session_expires_at"),
            "metadata": current_values.get("metadata") or {},
        }
        await cls._persist_settings(session.user_id, values)
        return await cls.get_for_user(session.user_id)

    @classmethod
    async def link_chatgpt_oauth(
        cls,
        session: CustomerSession,
        chatgpt_subject: str,
        display_name: Optional[str] = None,
        subscription_tier: str = "plus",
    ) -> Dict[str, Any]:
        normalized_subject = _normalize_optional_text(chatgpt_subject)
        if normalized_subject is None:
            raise ValueError("ChatGPT account identifier is required")

        normalized_display_name = _normalize_optional_text(display_name) or session.display_name or session.email
        normalized_tier = cls._normalize_subscription_tier(subscription_tier)

        auth = ConnectorAuthService(
            public_url=settings.CHATGPT_CONNECTOR_PUBLIC_URL,
            secret=settings.CHATGPT_CONNECTOR_SESSION_SECRET,
            persist_links=True,
            db_url=settings.CHATGPT_CONNECTOR_DATABASE_URL or settings.DATABASE_URL,
        )
        try:
            start = await auth.begin_oauth(
                chatgpt_subject=normalized_subject,
                user_id=session.user_id,
                display_name=normalized_display_name,
            )
            issued = await auth.complete_oauth(
                state=start.state,
                chatgpt_subject=normalized_subject,
                user_id=session.user_id,
                display_name=normalized_display_name,
            )
        finally:
            await auth.close()

        current = await cls._get_row(session.user_id)
        current_values = dict(current) if current is not None else {}

        values = {
            "access_mode": ACCESS_MODE_CHATGPT_OAUTH,
            "openclaw_api_url": current_values.get("openclaw_api_url"),
            "encrypted_openclaw_api_key": current_values.get("encrypted_openclaw_api_key"),
            "chatgpt_subject": normalized_subject,
            "chatgpt_display_name": issued.display_name,
            "chatgpt_subscription_tier": normalized_tier,
            "encrypted_connector_session_token": CustomerTokenVault.seal(
                {
                    "kind": "connector_session",
                    "session_token": issued.session_token,
                    "issued_at": _utcnow().isoformat(),
                }
            ),
            "connector_session_id": issued.session_id,
            "connector_session_expires_at": issued.expires_at,
            "metadata": current_values.get("metadata") or {},
        }
        await cls._persist_settings(session.user_id, values)
        return await cls.get_for_user(session.user_id)

    @classmethod
    async def disconnect_chatgpt_oauth(cls, session: CustomerSession) -> Dict[str, Any]:
        current = await cls._get_row(session.user_id)
        current_values = dict(current) if current is not None else {}

        values = {
            "access_mode": (
                ACCESS_MODE_PLATFORM_MANAGED
                if current_values.get("access_mode") == ACCESS_MODE_CHATGPT_OAUTH
                else current_values.get("access_mode") or ACCESS_MODE_PLATFORM_MANAGED
            ),
            "openclaw_api_url": current_values.get("openclaw_api_url"),
            "encrypted_openclaw_api_key": current_values.get("encrypted_openclaw_api_key"),
            "chatgpt_subject": None,
            "chatgpt_display_name": None,
            "chatgpt_subscription_tier": None,
            "encrypted_connector_session_token": None,
            "connector_session_id": None,
            "connector_session_expires_at": None,
            "metadata": current_values.get("metadata") or {},
        }
        await cls._persist_settings(session.user_id, values)
        return await cls.get_for_user(session.user_id)

    @classmethod
    async def resolve_runtime_config(cls, user_id: str) -> Dict[str, Any]:
        row = await cls._get_row(user_id)
        access_mode = (
            row["access_mode"]
            if row is not None and row["access_mode"] in VALID_ACCESS_MODES
            else ACCESS_MODE_PLATFORM_MANAGED
        )

        if access_mode == ACCESS_MODE_PLATFORM_MANAGED:
            return {
                "access_mode": ACCESS_MODE_PLATFORM_MANAGED,
                "transport": "responses",
                "base_url": settings.OPENCLAW_API_URL.rstrip("/"),
                "api_key": settings.OPENCLAW_API_KEY,
            }

        if access_mode == ACCESS_MODE_CUSTOMER_API_KEY:
            if row is None or not row["encrypted_openclaw_api_key"]:
                raise ValueError("Customer-managed access is enabled, but no OpenClaw API key is stored")
            payload = CustomerTokenVault.open(row["encrypted_openclaw_api_key"])
            api_key = _normalize_optional_text(payload.get("api_key"))
            if api_key is None:
                raise ValueError("Stored OpenClaw API key is invalid. Save it again from the dashboard.")
            return {
                "access_mode": ACCESS_MODE_CUSTOMER_API_KEY,
                "transport": "responses",
                "base_url": (row["openclaw_api_url"] or settings.OPENCLAW_API_URL).rstrip("/"),
                "api_key": api_key,
            }

        if row is None or not row["encrypted_connector_session_token"]:
            raise ValueError("GPT OAuth access is enabled, but no connector session is stored")
        if _is_connector_session_expired(row["connector_session_expires_at"]):
            raise ValueError("Your GPT OAuth session expired. Reconnect it from the dashboard.")

        payload = CustomerTokenVault.open(row["encrypted_connector_session_token"])
        session_token = _normalize_optional_text(payload.get("session_token"))
        if session_token is None:
            raise ValueError("Stored GPT OAuth session is invalid. Reconnect it from the dashboard.")

        return {
            "access_mode": ACCESS_MODE_CHATGPT_OAUTH,
            "transport": "connector",
            "base_url": settings.CHATGPT_CONNECTOR_PUBLIC_URL.rstrip("/"),
            "connector_session_token": session_token,
            "chatgpt_subject": row["chatgpt_subject"],
            "chatgpt_display_name": row["chatgpt_display_name"],
            "chatgpt_subscription_tier": row["chatgpt_subscription_tier"],
            "connector_session_expires_at": _isoformat(row["connector_session_expires_at"]),
        }
