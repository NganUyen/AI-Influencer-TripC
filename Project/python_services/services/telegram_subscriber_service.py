"""
Telegram Subscriber Service
============================
Manages the `telegram_subscribers` table — who has registered with the bot.

Follows the same asyncpg pool pattern as ContentPersistenceService.

Table expected (user runs this migration themselves):
    CREATE TABLE telegram_subscribers (
        chat_id       BIGINT PRIMARY KEY,
        chat_type     VARCHAR(20) NOT NULL DEFAULT 'private'
                          CHECK (chat_type IN ('private', 'group', 'supergroup')),
        username      VARCHAR(255),
        first_name    VARCHAR(255),
        role          VARCHAR(20) NOT NULL DEFAULT 'OPERATOR'
                          CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER')),
        is_active     BOOLEAN DEFAULT TRUE,
        registered_at TIMESTAMPTZ DEFAULT NOW(),
        last_seen_at  TIMESTAMPTZ DEFAULT NOW()
    );
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover
    asyncpg = None

from config.settings import settings

logger = logging.getLogger(__name__)


class TelegramSubscriberService:
    """
    Manages registered Telegram users/groups in the telegram_subscribers table.

    Usage:
        await TelegramSubscriberService.upsert(chat_id=123, chat_type="private",
                                               username="alice", first_name="Alice")

        chat_ids = await TelegramSubscriberService.get_active_chat_ids()
    """

    _pool: Optional[Any] = None
    _pool_lock = asyncio.Lock()

    @classmethod
    async def _get_pool(cls) -> Any:
        if asyncpg is None:
            raise RuntimeError("asyncpg is not installed")
        if cls._pool is None:
            async with cls._pool_lock:
                if cls._pool is None:
                    cls._pool = await asyncpg.create_pool(
                        dsn=settings.DATABASE_URL,
                        min_size=1,
                        max_size=3,
                        command_timeout=10,
                    )
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None

    # ── Write ──────────────────────────────────────────────────────────────────

    @classmethod
    async def upsert(
        cls,
        chat_id: int,
        chat_type: str = "private",
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        role: str = "OPERATOR",
    ) -> Dict[str, Any]:
        """
        Register or update a Telegram subscriber.

        Called when a user or group sends /start to the bot.
        Uses ON CONFLICT to update last_seen_at and username if they changed.
        The role is only set on first insert — it won't downgrade an ADMIN.
        """
        pool = await cls._get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.telegram_subscribers
                    (chat_id, chat_type, username, first_name, role, is_active,
                     registered_at, last_seen_at)
                VALUES
                    ($1, $2, $3, $4, $5, TRUE, NOW(), NOW())
                ON CONFLICT (chat_id) DO UPDATE
                    SET last_seen_at = NOW(),
                        username     = COALESCE(EXCLUDED.username, telegram_subscribers.username),
                        first_name   = COALESCE(EXCLUDED.first_name, telegram_subscribers.first_name),
                        is_active    = TRUE
                RETURNING chat_id, role, is_active, registered_at
                """,
                chat_id,
                chat_type,
                username,
                first_name,
                role,
            )

        result = dict(row)
        logger.info(
            "Subscriber upserted: chat_id=%s chat_type=%s role=%s",
            chat_id, chat_type, result.get("role"),
        )
        return result

    @classmethod
    async def deactivate(cls, chat_id: int) -> None:
        """Mark a subscriber as inactive (e.g. they blocked the bot)."""
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE public.telegram_subscribers SET is_active = FALSE WHERE chat_id = $1",
                chat_id,
            )
        logger.info("Subscriber deactivated: chat_id=%s", chat_id)

    # ── Read ───────────────────────────────────────────────────────────────────

    @classmethod
    async def get_active_chat_ids(
        cls,
        role: Optional[str] = None,
        chat_type: Optional[str] = None,
    ) -> List[int]:
        """
        Return all active subscriber chat_ids.

        Args:
            role:      Filter by role ('ADMIN', 'OPERATOR', 'VIEWER').
                       None = all roles.
            chat_type: Filter by type ('private', 'group', 'supergroup').
                       None = all types.

        Used by daily story workflow to know who to notify.
        """
        pool = await cls._get_pool()

        conditions = ["is_active = TRUE"]
        params: list = []

        if role:
            params.append(role)
            conditions.append(f"role = ${len(params)}")

        if chat_type:
            params.append(chat_type)
            conditions.append(f"chat_type = ${len(params)}")

        where = " AND ".join(conditions)
        query = f"SELECT chat_id FROM public.telegram_subscribers WHERE {where} ORDER BY registered_at"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [row["chat_id"] for row in rows]

    @classmethod
    async def get_by_chat_id(cls, chat_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single subscriber record."""
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.telegram_subscribers WHERE chat_id = $1",
                chat_id,
            )
        return dict(row) if row else None

    @classmethod
    async def touch(cls, chat_id: int) -> None:
        """Update last_seen_at without changing anything else. Call on every message."""
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.telegram_subscribers
                SET last_seen_at = NOW()
                WHERE chat_id = $1
                """,
                chat_id,
            )
