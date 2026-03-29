"""Redis-backed Telegram skill session store with in-memory fallback."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from skills.base import SkillSession

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    Redis = None

from config.settings import settings

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 600


class TelegramSkillSessionStore:
    """Persist per-chat skill sessions for multi-step Telegram flows."""

    _redis_client: Optional[Any] = None
    _redis_enabled: bool = False
    _redis_init_attempted: bool = False
    _memory_sessions: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _session_key(cls, chat_id: int | str) -> str:
        return f"telegram_session:{chat_id}"

    @classmethod
    def _init_redis(cls) -> None:
        if cls._redis_init_attempted:
            return
        cls._redis_init_attempted = True

        if Redis is None:
            logger.warning(
                "Redis client not installed. Falling back to in-memory skill sessions."
            )
            cls._redis_enabled = False
            return

        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            logger.warning(
                "REDIS_URL is not configured. Falling back to in-memory skill sessions."
            )
            cls._redis_enabled = False
            return

        try:
            cls._redis_client = Redis.from_url(redis_url, decode_responses=True)
            cls._redis_enabled = True
        except Exception as exc:  # pragma: no cover - depends on external Redis
            logger.warning(
                "Redis unavailable for skill session store (%s). Falling back to memory.",
                exc,
            )
            cls._redis_client = None
            cls._redis_enabled = False

    @classmethod
    async def get_session(cls, chat_id: int | str) -> Optional[SkillSession]:
        cls._init_redis()
        key = cls._session_key(chat_id)

        if cls._redis_enabled and cls._redis_client is not None:
            try:
                raw = await cls._redis_client.get(key)
                if raw:
                    payload = json.loads(raw)
                    # Keep memory cache in sync for this worker
                    cls._memory_sessions[key] = payload
                    return SkillSession.model_validate(payload)
                # Redis returned None - check memory before giving up
                # (session might exist in memory if previous write to Redis failed)
            except Exception as exc:  # pragma: no cover - depends on external Redis
                logger.error(
                    "Redis read failed for skill session store: %s. Falling back to memory.",
                    exc,
                )
                # Don't disable Redis on transient errors; try again next request

        # Fallback to memory if:
        # - Redis is not enabled at all
        # - Redis read failed
        # - Redis returned None but we might have it in memory from a failed write
        payload = cls._memory_sessions.get(key)
        return SkillSession.model_validate(payload) if payload else None

    @classmethod
    async def set_session(cls, chat_id: int | str, session: SkillSession) -> None:
        cls._init_redis()
        key = cls._session_key(chat_id)
        payload = session.model_dump(mode="json")
        # Always keep memory cache in sync for this worker
        cls._memory_sessions[key] = payload

        if cls._redis_enabled and cls._redis_client is not None:
            try:
                await cls._redis_client.setex(
                    key,
                    SESSION_TTL_SECONDS,
                    json.dumps(payload),
                )
            except Exception as exc:  # pragma: no cover - depends on external Redis
                logger.error(
                    "Redis write failed for skill session store: %s. Session saved to memory only.",
                    exc,
                )
                # Don't disable Redis on transient errors; try again next request
                # cls._redis_enabled = False

    @classmethod
    async def clear_session(cls, chat_id: int | str) -> None:
        cls._init_redis()
        key = cls._session_key(chat_id)
        cls._memory_sessions.pop(key, None)

        if cls._redis_enabled and cls._redis_client is not None:
            try:
                await cls._redis_client.delete(key)
            except Exception as exc:  # pragma: no cover - depends on external Redis
                logger.warning("Redis delete failed for skill session store: %s", exc)
                cls._redis_enabled = False
