"""
Small persistence helper for ChatGPT identity links.

The connector keeps OAuth states and short-lived sessions in memory, but the
identity link itself is durable when the database is available.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - local env dependent
    asyncpg = None

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ConnectorLinkRecord:
    chatgpt_subject: str
    user_id: str
    display_name: Optional[str]
    session_id: str
    linked_at: datetime
    last_used_at: datetime
    active: bool = True


class ConnectorLinkStore:
    def __init__(
        self,
        db_url: Optional[str] = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self.db_url = db_url or os.getenv("CHATGPT_CONNECTOR_DATABASE_URL") or os.getenv("DATABASE_URL")
        self._pool: Any = None
        self._lock = asyncio.Lock()
        self._memory: Dict[str, ConnectorLinkRecord] = {}

    async def _get_pool(self) -> Any:
        if not self.enabled or asyncpg is None or not self.db_url:
            raise RuntimeError("Connector link persistence is not available")
        if self._pool is None:
            async with self._lock:
                if self._pool is None:
                    self._pool = await asyncpg.create_pool(
                        dsn=self.db_url,
                        min_size=1,
                        max_size=2,
                        command_timeout=10,
                    )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def upsert_link(
        self,
        chatgpt_subject: str,
        user_id: str,
        display_name: Optional[str],
        session_id: str,
    ) -> ConnectorLinkRecord:
        now = _utcnow()
        record = ConnectorLinkRecord(
            chatgpt_subject=chatgpt_subject,
            user_id=user_id,
            display_name=display_name,
            session_id=session_id,
            linked_at=now,
            last_used_at=now,
            active=True,
        )

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO public.chatgpt_oauth_links (
                        chatgpt_subject,
                        user_id,
                        display_name,
                        session_id,
                        linked_at,
                        last_used_at,
                        active
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                    ON CONFLICT (chatgpt_subject)
                    DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        display_name = EXCLUDED.display_name,
                        session_id = EXCLUDED.session_id,
                        last_used_at = EXCLUDED.last_used_at,
                        active = TRUE
                    RETURNING chatgpt_subject, user_id, display_name, session_id, linked_at, last_used_at, active
                    """,
                    chatgpt_subject,
                    user_id,
                    display_name,
                    session_id,
                    now,
                    now,
                )
                if row:
                    record = self._row_to_record(row)
        except Exception as exc:  # pragma: no cover - fallback path exercised in unit tests
            logger.debug("Connector link persistence falling back to memory: %s", exc)

        self._memory[chatgpt_subject] = record
        return record

    async def get_link(self, chatgpt_subject: str) -> Optional[ConnectorLinkRecord]:
        cached = self._memory.get(chatgpt_subject)
        if cached is not None:
            return cached

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT chatgpt_subject, user_id, display_name, session_id, linked_at, last_used_at, active
                    FROM public.chatgpt_oauth_links
                    WHERE chatgpt_subject = $1
                    LIMIT 1
                    """,
                    chatgpt_subject,
                )
                if row:
                    record = self._row_to_record(row)
                    self._memory[chatgpt_subject] = record
                    return record
        except Exception as exc:  # pragma: no cover - fallback path exercised in unit tests
            logger.debug("Connector link read falling back to memory: %s", exc)

        return None

    async def touch_link(self, chatgpt_subject: str, session_id: Optional[str] = None) -> None:
        record = await self.get_link(chatgpt_subject)
        if record is None:
            return

        record.last_used_at = _utcnow()
        if session_id:
            record.session_id = session_id
        self._memory[chatgpt_subject] = record

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE public.chatgpt_oauth_links
                    SET last_used_at = $1,
                        session_id = COALESCE($2, session_id),
                        active = TRUE
                    WHERE chatgpt_subject = $3
                    """,
                    record.last_used_at,
                    session_id,
                    chatgpt_subject,
                )
        except Exception as exc:  # pragma: no cover - fallback path exercised in unit tests
            logger.debug("Connector link touch falling back to memory: %s", exc)

    @staticmethod
    def _row_to_record(row: Any) -> ConnectorLinkRecord:
        return ConnectorLinkRecord(
            chatgpt_subject=row["chatgpt_subject"],
            user_id=row["user_id"],
            display_name=row["display_name"],
            session_id=row["session_id"],
            linked_at=row["linked_at"],
            last_used_at=row["last_used_at"],
            active=row["active"],
        )
