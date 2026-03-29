"""
Telegram customer-link helpers.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from config.settings import settings
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)
USER_NAMESPACE = uuid.UUID("2d9d5f55-2d26-4e34-b0bb-2d2d2f67eaa1")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TelegramLinkError(RuntimeError):
    pass


class TelegramLinkService:
    DEFAULT_TOKEN_TTL_MINUTES = 15
    PENDING_TELEGRAM_USER_NAME = "Pending Telegram Login"

    @classmethod
    def _allows_legacy_fallback(cls, allow_fallback: bool) -> bool:
        # Legacy fallback is permanently disabled - Telegram linking is required
        return False

    @staticmethod
    def _parse_owner_chat_id(owner_key: Optional[str]) -> Optional[int]:
        if not owner_key:
            return None
        normalized = str(owner_key).strip()
        if not normalized.lower().startswith("telegram:"):
            return None
        raw_chat_id = normalized.split(":", 1)[1].strip()
        if not raw_chat_id or not raw_chat_id.lstrip("-").isdigit():
            return None
        return int(raw_chat_id)

    @staticmethod
    def _is_missing_relation_error(exc: Exception, *relation_names: str) -> bool:
        message = str(exc or "").lower()
        sqlstate = str(
            getattr(exc, "sqlstate", "") or getattr(exc, "pgcode", "")
        ).strip()
        if sqlstate and sqlstate != "42P01":
            return False
        if "does not exist" not in message:
            return False
        if not relation_names:
            return True
        return any(name.lower() in message for name in relation_names)

    @classmethod
    def synthetic_user_id_for_owner_key(cls, owner_key: Optional[str]) -> Optional[str]:
        normalized = str(owner_key or "").strip()
        if not normalized:
            return None
        try:
            return str(uuid.UUID(normalized))
        except (TypeError, ValueError):
            return str(uuid.uuid5(USER_NAMESPACE, normalized))

    @classmethod
    def _fallback_user_id(cls, owner_key: Optional[str]) -> Optional[str]:
        # Do not return a synthetic user_id for unlinked owners to avoid
        # accidental persona creation under shared or system accounts.
        return None

    @staticmethod
    def _synthetic_owner_label(owner_key: Optional[str]) -> Optional[str]:
        normalized = str(owner_key or "").strip()
        if not normalized:
            return None
        sanitized = "".join(
            ch if ch.isalnum() else "-" for ch in normalized.lower()
        ).strip("-")
        return sanitized or None

    @classmethod
    async def _resolve_legacy_synthetic_user_id(
        cls,
        owner_key: Optional[str],
    ) -> Optional[str]:
        owner_label = cls._synthetic_owner_label(owner_key)
        if not owner_label:
            return None

        candidate_emails = [
            f"persona-{owner_label}@local.ai-influencer.invalid",
            f"media-{owner_label}@local.ai-influencer.invalid",
        ]

        pool = await DatabaseService.get_pool()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, email
                    FROM public.users
                    WHERE email = ANY($1::text[])
                    ORDER BY array_position($1::text[], email)
                    LIMIT 1
                    """,
                    candidate_emails,
                )
        except Exception:
            return None

        if row and row.get("id"):
            logger.info(
                "Reusing legacy synthetic Telegram owner user_id %s for %s",
                row["id"],
                owner_key,
            )
            return str(row["id"])
        return None

    @classmethod
    async def create_link_token(
        cls,
        *,
        user_id: str,
        expires_in_minutes: int | None = None,
    ) -> Dict[str, Any]:
        token, token_hash, expires_at = cls._generate_start_token(expires_in_minutes)

        pool = await DatabaseService.get_pool()
        try:
            async with pool.acquire() as conn:
                await cls._insert_link_token(
                    conn,
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                )
        except Exception as exc:
            if cls._is_missing_relation_error(exc, "telegram_link_tokens"):
                raise TelegramLinkError(
                    "Telegram link tables are not installed. Apply migration 20260326_telegram_owner_links_and_avatar_assets.sql first."
                ) from exc
            raise

        logger.info("create_link_token: created token=%s... hash=%s... expires=%s", token[:8], token_hash[:16], expires_at.isoformat())
        return {
            "start_token": token,
            "expires_at": expires_at.isoformat(),
        }

    @classmethod
    async def create_public_auth_link_token(
        cls,
        *,
        expires_in_minutes: int | None = None,
    ) -> Dict[str, Any]:
        token, token_hash, expires_at = cls._generate_start_token(expires_in_minutes)
        user_id = str(uuid.uuid4())
        placeholder_email = cls._pending_telegram_email(user_id)

        pool = await DatabaseService.get_pool()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO public.users (id, email, name)
                        VALUES ($1::uuid, $2, $3)
                        """,
                        user_id,
                        placeholder_email,
                        cls.PENDING_TELEGRAM_USER_NAME,
                    )
                    await cls._insert_link_token(
                        conn,
                        user_id=user_id,
                        token_hash=token_hash,
                        expires_at=expires_at,
                    )
        except Exception as exc:
            if cls._is_missing_relation_error(exc, "telegram_link_tokens", "users"):
                raise TelegramLinkError(
                    "Telegram link tables are not installed. Apply migration 20260326_telegram_owner_links_and_avatar_assets.sql first."
                ) from exc
            raise

        logger.info(
            "create_public_auth_link_token: created token=%s... hash=%s... user_id=%s expires=%s",
            token[:8],
            token_hash[:16],
            user_id,
            expires_at.isoformat(),
        )
        return {
            "start_token": token,
            "expires_at": expires_at.isoformat(),
        }

    @classmethod
    def _generate_start_token(
        cls,
        expires_in_minutes: int | None = None,
    ) -> tuple[str, str, datetime]:
        ttl_minutes = max(1, int(expires_in_minutes or cls.DEFAULT_TOKEN_TTL_MINUTES))
        token = secrets.token_urlsafe(24)
        token_hash = _hash_token(token)
        expires_at = _utcnow() + timedelta(minutes=ttl_minutes)
        return token, token_hash, expires_at

    @staticmethod
    async def _insert_link_token(
        conn: Any,
        *,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO public.telegram_link_tokens (
                user_id,
                token_hash,
                expires_at
            )
            VALUES ($1::uuid, $2, $3)
            """,
            user_id,
            token_hash,
            expires_at,
        )

    @staticmethod
    def _pending_telegram_email(user_id: str) -> str:
        return f"tg_pending_{str(user_id).strip().lower()}@ai-influencer.invalid"

    @classmethod
    async def consume_link_token(
        cls,
        *,
        token: str,
        chat_id: int,
        telegram_username: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise TelegramLinkError("Missing Telegram link token.")

        token_hash = _hash_token(normalized_token)
        logger.info("consume_link_token: token=%s... hash=%s...", normalized_token[:8], token_hash[:16])
        pool = await DatabaseService.get_pool()

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    row = await conn.fetchrow(
                        """
                        SELECT user_id, expires_at, used_at
                        FROM public.telegram_link_tokens
                        WHERE token_hash = $1
                        LIMIT 1
                        FOR UPDATE
                        """,
                        token_hash,
                    )
                    logger.info("consume_link_token: DB lookup result=%s", "found" if row else "NOT FOUND")
                    if row is None:
                        raise TelegramLinkError("Telegram link token is invalid.")
                    if row["used_at"] is not None:
                        raise TelegramLinkError(
                            "Telegram link token has already been used."
                        )
                    if row["expires_at"] <= _utcnow():
                        raise TelegramLinkError("Telegram link token has expired.")

                    user_id = str(row["user_id"])

                    await conn.execute(
                        """
                        UPDATE public.telegram_link_tokens
                        SET used_at = NOW(),
                            updated_at = NOW()
                        WHERE token_hash = $1
                        """,
                        token_hash,
                    )

                    await conn.execute(
                        """
                        UPDATE public.telegram_user_links
                        SET revoked_at = NOW()
                        WHERE user_id = $1::uuid
                          AND chat_id <> $2
                          AND revoked_at IS NULL
                        """,
                        user_id,
                        chat_id,
                    )

                    await conn.execute(
                        """
                        INSERT INTO public.telegram_user_links (
                            chat_id,
                            user_id,
                            telegram_username,
                            linked_at,
                            last_verified_at,
                            revoked_at
                        )
                        VALUES ($1, $2::uuid, $3, NOW(), NOW(), NULL)
                        ON CONFLICT (chat_id) DO UPDATE
                        SET user_id = EXCLUDED.user_id,
                            telegram_username = COALESCE(EXCLUDED.telegram_username, public.telegram_user_links.telegram_username),
                            linked_at = NOW(),
                            last_verified_at = NOW(),
                            revoked_at = NULL
                        """,
                        chat_id,
                        user_id,
                        telegram_username,
                    )
        except Exception as exc:
            if cls._is_missing_relation_error(
                exc, "telegram_link_tokens", "telegram_user_links"
            ):
                raise TelegramLinkError(
                    "Telegram link tables are not installed. Apply migration 20260326_telegram_owner_links_and_avatar_assets.sql first."
                ) from exc
            raise

        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "telegram_username": telegram_username,
        }

    @classmethod
    async def touch_link(
        cls,
        *,
        chat_id: int,
        telegram_username: Optional[str] = None,
    ) -> None:
        pool = await DatabaseService.get_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE public.telegram_user_links
                    SET last_verified_at = NOW(),
                        telegram_username = COALESCE($2, public.telegram_user_links.telegram_username)
                    WHERE chat_id = $1
                      AND revoked_at IS NULL
                    """,
                    chat_id,
                    telegram_username,
                )
        except Exception as exc:
            if cls._is_missing_relation_error(exc, "telegram_user_links"):
                logger.info(
                    "Skipping Telegram link touch because telegram_user_links is missing."
                )
                return
            raise

    @classmethod
    async def get_link_for_user(cls, user_id: str) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT
                        chat_id,
                        user_id,
                        telegram_username,
                        linked_at,
                        last_verified_at,
                        revoked_at
                    FROM public.telegram_user_links
                    WHERE user_id = $1::uuid
                      AND revoked_at IS NULL
                    LIMIT 1
                    """,
                    user_id,
                )
        except Exception as exc:
            if cls._is_missing_relation_error(exc, "telegram_user_links"):
                logger.info(
                    "Telegram link status requested before telegram_user_links migration was applied."
                )
                return None
            raise
        if row is None:
            return None

        return {
            "chat_id": int(row["chat_id"]),
            "user_id": str(row["user_id"]),
            "telegram_username": row["telegram_username"],
            "linked_at": row["linked_at"].isoformat() if row["linked_at"] else None,
            "last_verified_at": row["last_verified_at"].isoformat()
            if row["last_verified_at"]
            else None,
            "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None,
        }

    @classmethod
    async def resolve_user_id_for_owner_key(
        cls,
        owner_key: Optional[str],
        *,
        allow_fallback: bool = False,
    ) -> Optional[str]:
        legacy_fallback_allowed = cls._allows_legacy_fallback(allow_fallback)
        chat_id = cls._parse_owner_chat_id(owner_key)
        if chat_id is None:
            if legacy_fallback_allowed:
                legacy_user_id = await cls._resolve_legacy_synthetic_user_id(owner_key)
                if legacy_user_id:
                    return legacy_user_id
            return cls._fallback_user_id(owner_key) if legacy_fallback_allowed else None

        pool = await DatabaseService.get_pool()
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT user_id
                    FROM public.telegram_user_links
                    WHERE chat_id = $1
                      AND revoked_at IS NULL
                    LIMIT 1
                    """,
                    chat_id,
                )
        except Exception as exc:
            if cls._is_missing_relation_error(exc, "telegram_user_links"):
                if legacy_fallback_allowed:
                    logger.warning(
                        "telegram_user_links is missing; falling back to a synthetic Telegram owner user_id."
                    )
                    legacy_user_id = await cls._resolve_legacy_synthetic_user_id(
                        owner_key
                    )
                    if legacy_user_id:
                        return legacy_user_id
                    return cls._fallback_user_id(owner_key)
                logger.warning(
                    "telegram_user_links is missing; production-like ownership fallback is disabled."
                )
                return None
            raise
        if row is None or not row.get("user_id"):
            if legacy_fallback_allowed:
                legacy_user_id = await cls._resolve_legacy_synthetic_user_id(owner_key)
                if legacy_user_id:
                    return legacy_user_id
            return cls._fallback_user_id(owner_key) if legacy_fallback_allowed else None
        return str(row["user_id"])
