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

SESSION_TTL_SECONDS = 3600


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
                    session = SkillSession.model_validate(payload)
                    
                    # Refresh TTL on access to keep active sessions alive
                    try:
                        await cls._redis_client.expire(key, SESSION_TTL_SECONDS)
                    except Exception as refresh_exc:
                        logger.warning(
                            "Failed to refresh session TTL for chat_id=%s: %s",
                            chat_id,
                            refresh_exc,
                        )
                    
                    return session
                # Redis returned None - session not found
                return None
            except Exception as exc:  # pragma: no cover - depends on external Redis
                logger.error(
                    "Redis read failed for skill session store: %s",
                    exc,
                )
                # In production, fail fast - don't silently fall back to memory
                if settings.is_production_like:
                    raise RuntimeError(
                        "Session store unavailable in production. Redis is required."
                    ) from exc
                # In development, warn and fall back to memory
                logger.warning(
                    "Falling back to in-memory session store (development only)"
                )

        # Fallback to memory only in development or when Redis is not configured
        if settings.is_production_like and not cls._redis_enabled:
            raise RuntimeError(
                "Session store requires Redis in production, but Redis is not configured."
            )
        
        payload = cls._memory_sessions.get(key)
        return SkillSession.model_validate(payload) if payload else None

    @classmethod
    async def set_session(cls, chat_id: int | str, session: SkillSession) -> None:
        cls._init_redis()
        key = cls._session_key(chat_id)
        payload = session.model_dump(mode="json")
        
        # In production, only use Redis (no memory fallback)
        if settings.is_production_like:
            if not cls._redis_enabled or cls._redis_client is None:
                raise RuntimeError(
                    "Session store requires Redis in production, but Redis is not configured."
                )
            try:
                await cls._redis_client.setex(
                    key,
                    SESSION_TTL_SECONDS,
                    json.dumps(payload),
                )
            except Exception as exc:
                logger.error(
                    "Redis write failed for skill session store: %s",
                    exc,
                )
                raise RuntimeError(
                    "Failed to save session to Redis in production"
                ) from exc
            return
        
        # Development mode: try Redis first, fall back to memory
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
                logger.warning(
                    "Falling back to in-memory session store (development only)"
                )

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
