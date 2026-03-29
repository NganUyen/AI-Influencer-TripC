"""
Canonical Telegram identity helpers shared across link and auth flows.
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid
from typing import Optional


TELEGRAM_USER_NAMESPACE = uuid.UUID("2d9d5f55-2d26-4e34-b0bb-2d2d2f67eaa1")


@dataclass(frozen=True)
class TelegramIdentity:
    chat_id: Optional[int]
    user_id: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    telegram_username: Optional[str] = None


class TelegramIdentityService:
    @staticmethod
    def owner_key_for_chat(chat_id: int) -> str:
        return f"telegram:{chat_id}"

    @classmethod
    def canonical_user_id_for_chat(cls, chat_id: int) -> str:
        return str(
            uuid.uuid5(
                TELEGRAM_USER_NAMESPACE,
                cls.owner_key_for_chat(chat_id),
            )
        )

    @classmethod
    def synthetic_user_id_for_owner_key(cls, owner_key: Optional[str]) -> Optional[str]:
        normalized = str(owner_key or "").strip()
        if not normalized:
            return None
        try:
            return str(uuid.UUID(normalized))
        except (TypeError, ValueError):
            return str(uuid.uuid5(TELEGRAM_USER_NAMESPACE, normalized))

    @staticmethod
    def email_for_chat(chat_id: int) -> str:
        return f"tg_{chat_id}@ai-influencer.invalid"

    @staticmethod
    def default_display_name(
        chat_id: int,
        *,
        telegram_username: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> str:
        normalized_display_name = str(display_name or "").strip()
        if normalized_display_name:
            return normalized_display_name
        normalized_username = str(telegram_username or "").strip().lstrip("@")
        if normalized_username:
            return f"@{normalized_username}"
        return f"Telegram User {chat_id}"

    @classmethod
    def legacy_user_id_candidates_for_chat(cls, chat_id: int) -> list[str]:
        candidates = [
            cls.canonical_user_id_for_chat(chat_id),
            str(uuid.uuid5(TELEGRAM_USER_NAMESPACE, f"tg:{chat_id}")),
            str(uuid.uuid5(uuid.NAMESPACE_DNS, cls.owner_key_for_chat(chat_id))),
        ]
        ordered: list[str] = []
        for candidate in candidates:
            if candidate not in ordered:
                ordered.append(candidate)
        return ordered

    @classmethod
    async def _find_existing_identity(cls, conn, *, chat_id: int) -> Optional[TelegramIdentity]:
        linked_row = await conn.fetchrow(
            """
            SELECT
                tul.chat_id,
                tul.user_id,
                tul.telegram_username,
                u.email,
                u.name,
                u.avatar_url
            FROM public.telegram_user_links tul
            LEFT JOIN public.users u
              ON u.id = tul.user_id
            WHERE tul.chat_id = $1
              AND tul.revoked_at IS NULL
            LIMIT 1
            """,
            chat_id,
        )
        if linked_row and linked_row.get("user_id"):
            return TelegramIdentity(
                chat_id=int(linked_row["chat_id"]),
                user_id=str(linked_row["user_id"]),
                email=str(linked_row.get("email") or cls.email_for_chat(chat_id)),
                display_name=linked_row.get("name"),
                avatar_url=linked_row.get("avatar_url"),
                telegram_username=linked_row.get("telegram_username"),
            )

        for candidate_id in cls.legacy_user_id_candidates_for_chat(chat_id):
            user_row = await conn.fetchrow(
                """
                SELECT id, email, name, avatar_url
                FROM public.users
                WHERE id = $1::uuid
                LIMIT 1
                """,
                candidate_id,
            )
            if user_row and user_row.get("id"):
                return TelegramIdentity(
                    chat_id=chat_id,
                    user_id=str(user_row["id"]),
                    email=str(user_row.get("email") or cls.email_for_chat(chat_id)),
                    display_name=user_row.get("name"),
                    avatar_url=user_row.get("avatar_url"),
                )

        email = cls.email_for_chat(chat_id)
        email_row = await conn.fetchrow(
            """
            SELECT id, email, name, avatar_url
            FROM public.users
            WHERE email = $1
            LIMIT 1
            """,
            email,
        )
        if email_row and email_row.get("id"):
            return TelegramIdentity(
                chat_id=chat_id,
                user_id=str(email_row["id"]),
                email=str(email_row.get("email") or email),
                display_name=email_row.get("name"),
                avatar_url=email_row.get("avatar_url"),
            )
        return None

    @classmethod
    async def resolve_or_create_identity(
        cls,
        conn,
        *,
        chat_id: int,
        telegram_username: Optional[str] = None,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> TelegramIdentity:
        existing_identity = await cls._find_existing_identity(conn, chat_id=chat_id)
        user_id = (
            existing_identity.user_id
            if existing_identity is not None
            else cls.canonical_user_id_for_chat(chat_id)
        )
        email = (
            existing_identity.email
            if existing_identity is not None and existing_identity.email
            else cls.email_for_chat(chat_id)
        )
        resolved_display_name = (
            existing_identity.display_name
            if existing_identity is not None and existing_identity.display_name
            else cls.default_display_name(
                chat_id,
                telegram_username=telegram_username,
                display_name=display_name,
            )
        )
        resolved_avatar_url = (
            existing_identity.avatar_url
            if existing_identity is not None and existing_identity.avatar_url
            else avatar_url
        )
        resolved_username = (
            existing_identity.telegram_username
            if existing_identity is not None and existing_identity.telegram_username
            else telegram_username
        )

        await conn.execute(
            """
            INSERT INTO public.users (id, email, name, avatar_url)
            VALUES ($1::uuid, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE
            SET email = COALESCE(public.users.email, EXCLUDED.email),
                name = COALESCE(public.users.name, EXCLUDED.name),
                avatar_url = COALESCE(public.users.avatar_url, EXCLUDED.avatar_url),
                updated_at = NOW()
            """,
            user_id,
            email,
            resolved_display_name,
            resolved_avatar_url,
        )

        return TelegramIdentity(
            chat_id=chat_id,
            user_id=user_id,
            email=email,
            display_name=resolved_display_name,
            avatar_url=resolved_avatar_url,
            telegram_username=resolved_username,
        )

    @staticmethod
    async def upsert_telegram_link(
        conn,
        *,
        chat_id: int,
        user_id: str,
        telegram_username: Optional[str] = None,
    ) -> None:
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
                telegram_username = COALESCE(
                    EXCLUDED.telegram_username,
                    public.telegram_user_links.telegram_username
                ),
                linked_at = NOW(),
                last_verified_at = NOW(),
                revoked_at = NULL
            """,
            chat_id,
            user_id,
            telegram_username,
        )

    @staticmethod
    async def get_identity_for_user_id(conn, *, user_id: str) -> Optional[TelegramIdentity]:
        row = await conn.fetchrow(
            """
            SELECT
                u.id,
                u.email,
                u.name,
                u.avatar_url,
                tul.chat_id,
                tul.telegram_username
            FROM public.users u
            LEFT JOIN public.telegram_user_links tul
              ON tul.user_id = u.id
             AND tul.revoked_at IS NULL
            WHERE u.id = $1::uuid
            LIMIT 1
            """,
            user_id,
        )
        if row is None or not row.get("id"):
            return None
        return TelegramIdentity(
            chat_id=int(row["chat_id"]) if row.get("chat_id") is not None else None,
            user_id=str(row["id"]),
            email=str(row.get("email") or ""),
            display_name=row.get("name"),
            avatar_url=row.get("avatar_url"),
            telegram_username=row.get("telegram_username"),
        )
