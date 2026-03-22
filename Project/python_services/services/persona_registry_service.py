"""
Persona registry helpers for short-video pipeline bootstrap and reuse.
"""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    asyncpg = None

from services.errors import PersonaConfigurationError, PersonaNotReadyError
from config.settings import settings

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PersonaRegistryService:
    _pool: Optional[Any] = None
    _pool_lock = asyncio.Lock()
    _memory_store: Dict[str, Dict[str, Any]] = {}

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
                        max_size=5,
                        command_timeout=15,
                    )
        return cls._pool

    @classmethod
    async def close_pool(cls) -> None:
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None

    @staticmethod
    def _record_from_row(row: Any) -> Dict[str, Any]:
        if row is None:
            return {}
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        return {
            "persona_id": row.get("persona_id"),
            "display_name": row.get("display_name") or row.get("persona_id"),
            "language": row.get("language") or "English",
            "tts_voice": row.get("tts_voice"),
            "avatar_image_url": row.get("avatar_image_url"),
            "avatar_source_type": row.get("avatar_source_type"),
            "avatar_prompt": row.get("avatar_prompt"),
            "heygen_avatar_id": row.get("heygen_avatar_id"),
            "status": row.get("status") or "draft",
            "video_count": int(row.get("video_count") or 0),
            "tone_default": row.get("tone_default"),
            "market_default": row.get("market_default"),
            "thumbnail_url": row.get("thumbnail_url"),
            "description": row.get("description"),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
        }

    @classmethod
    async def _list_from_db(cls, status: Optional[str] = None) -> List[Dict[str, Any]]:
        pool = await cls._get_pool()
        query = """
            SELECT
                persona_id,
                display_name,
                language,
                tts_voice,
                avatar_image_url,
                avatar_source_type,
                avatar_prompt,
                heygen_avatar_id,
                status,
                video_count,
                tone_default,
                market_default,
                thumbnail_url,
                description,
                created_at,
                updated_at
            FROM public.personas
        """
        args: List[Any] = []
        if status:
            query += " WHERE status = $1"
            args.append(status)
        query += " ORDER BY created_at DESC NULLS LAST, persona_id ASC"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        return [cls._record_from_row(dict(row)) for row in rows]

    @classmethod
    async def _get_from_db(cls, persona_id: str) -> Optional[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    persona_id,
                    display_name,
                    language,
                    tts_voice,
                    avatar_image_url,
                    avatar_source_type,
                    avatar_prompt,
                    heygen_avatar_id,
                    status,
                    video_count,
                    tone_default,
                    market_default,
                    thumbnail_url,
                    description,
                    created_at,
                    updated_at
                FROM public.personas
                WHERE persona_id = $1
                LIMIT 1
                """,
                persona_id,
            )
        if row is None:
            return None
        return cls._record_from_row(dict(row))

    @classmethod
    async def _create_in_memory(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = _utcnow_iso()
        record = {
            "persona_id": payload["persona_id"],
            "display_name": payload["display_name"],
            "language": payload["language"],
            "tts_voice": payload["tts_voice"],
            "avatar_image_url": payload.get("avatar_image_url"),
            "avatar_source_type": payload.get("avatar_source_type"),
            "avatar_prompt": payload.get("avatar_prompt"),
            "heygen_avatar_id": payload.get("heygen_avatar_id"),
            "status": payload.get("status", "draft"),
            "video_count": int(payload.get("video_count", 0)),
            "tone_default": payload.get("tone_default"),
            "market_default": payload.get("market_default"),
            "thumbnail_url": payload.get("thumbnail_url"),
            "description": payload.get("description"),
            "created_at": now,
            "updated_at": now,
        }
        cls._memory_store[record["persona_id"]] = record
        return deepcopy(record)

    @classmethod
    async def _create_in_db(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.personas (
                    persona_id,
                    display_name,
                    language,
                    tts_voice,
                    avatar_image_url,
                    avatar_source_type,
                    avatar_prompt,
                    heygen_avatar_id,
                    status,
                    video_count,
                    tone_default,
                    market_default,
                    thumbnail_url,
                    description
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                )
                RETURNING
                    persona_id,
                    display_name,
                    language,
                    tts_voice,
                    avatar_image_url,
                    avatar_source_type,
                    avatar_prompt,
                    heygen_avatar_id,
                    status,
                    video_count,
                    tone_default,
                    market_default,
                    thumbnail_url,
                    description,
                    created_at,
                    updated_at
                """,
                payload["persona_id"],
                payload["display_name"],
                payload["language"],
                payload["tts_voice"],
                payload.get("avatar_image_url"),
                payload.get("avatar_source_type"),
                payload.get("avatar_prompt"),
                payload.get("heygen_avatar_id"),
                payload.get("status", "draft"),
                int(payload.get("video_count", 0)),
                payload.get("tone_default"),
                payload.get("market_default"),
                payload.get("thumbnail_url"),
                payload.get("description"),
            )
        return cls._record_from_row(dict(row))

    @classmethod
    async def _update_in_db(cls, persona_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not fields:
            return await cls._get_from_db(persona_id)

        assignments: List[str] = []
        args: List[Any] = []
        allowed_fields = [
            "display_name",
            "language",
            "tts_voice",
            "avatar_image_url",
            "avatar_source_type",
            "avatar_prompt",
            "heygen_avatar_id",
            "status",
            "video_count",
            "tone_default",
            "market_default",
            "thumbnail_url",
            "description",
        ]
        for field in allowed_fields:
            if field in fields:
                args.append(fields[field])
                assignments.append(f"{field} = ${len(args)}")

        if not assignments:
            return await cls._get_from_db(persona_id)

        args.append(persona_id)
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE public.personas
                SET {", ".join(assignments)},
                    updated_at = NOW()
                WHERE persona_id = ${len(args)}
                RETURNING
                    persona_id,
                    display_name,
                    language,
                    tts_voice,
                    avatar_image_url,
                    avatar_source_type,
                    avatar_prompt,
                    heygen_avatar_id,
                    status,
                    video_count,
                    tone_default,
                    market_default,
                    thumbnail_url,
                    description,
                    created_at,
                    updated_at
                """,
                *args,
            )
        if row is None:
            return None
        return cls._record_from_row(dict(row))

    @classmethod
    async def list_personas(cls, status: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return await cls._list_from_db(status=status)
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.warning("Persona DB list failed, using in-memory fallback: %s", exc)
            personas = list(cls._memory_store.values())
            if status:
                personas = [item for item in personas if item.get("status") == status]
            return [deepcopy(item) for item in personas]

    @classmethod
    async def get_persona(cls, persona_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await cls._get_from_db(persona_id)
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.warning("Persona DB lookup failed, using in-memory fallback: %s", exc)
            record = cls._memory_store.get(persona_id)
            return deepcopy(record) if record else None

    @classmethod
    async def create_persona(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload.get("persona_id"):
            raise PersonaConfigurationError("persona_id is required")
        if not payload.get("display_name"):
            raise PersonaConfigurationError("display_name is required")
        if not payload.get("language"):
            raise PersonaConfigurationError("language is required")
        if not payload.get("tts_voice"):
            raise PersonaConfigurationError("tts_voice is required")

        base_payload = {
            **payload,
            "status": payload.get("status") or "draft",
            "video_count": int(payload.get("video_count", 0)),
        }

        try:
            return await cls._create_in_db(base_payload)
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.warning("Persona DB create failed, using in-memory fallback: %s", exc)
            return await cls._create_in_memory(base_payload)

    @classmethod
    async def update_persona(cls, persona_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            return await cls._update_in_db(persona_id, fields)
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.warning("Persona DB update failed, using in-memory fallback: %s", exc)
            if persona_id not in cls._memory_store:
                return None
            cls._memory_store[persona_id].update(fields)
            cls._memory_store[persona_id]["updated_at"] = _utcnow_iso()
            return deepcopy(cls._memory_store[persona_id])

    @classmethod
    def build_readiness_report(
        cls, persona_id: str, persona: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        checks = {
            "status_ready": bool(persona and persona.get("status") == "ready"),
            "has_tts_voice": bool(persona and persona.get("tts_voice")),
            "has_avatar_image": bool(persona and persona.get("avatar_image_url")),
            "has_heygen_avatar_id": bool(persona and persona.get("heygen_avatar_id")),
        }

        blocking_reason = None
        status = persona.get("status", "missing") if persona else "missing"
        if not persona:
            blocking_reason = f"Persona '{persona_id}' was not found."
        elif not checks["status_ready"]:
            blocking_reason = "Persona status is not ready."
        elif not checks["has_tts_voice"]:
            blocking_reason = "Missing tts_voice. Configure persona voice first."
        elif not checks["has_avatar_image"]:
            blocking_reason = "Missing avatar_image_url. Run persona avatar setup first."
        elif not checks["has_heygen_avatar_id"]:
            blocking_reason = "Missing heygen_avatar_id. Run persona avatar setup first."

        return {
            "persona_id": persona_id,
            "ready": blocking_reason is None,
            "status": status,
            "blocking_reason": blocking_reason,
            "checks": checks,
        }

    @classmethod
    async def get_readiness(cls, persona_id: str) -> Dict[str, Any]:
        persona = await cls.get_persona(persona_id)
        return cls.build_readiness_report(persona_id, persona)

    @classmethod
    async def resolve_ready_persona(cls, persona_id: str) -> Dict[str, Any]:
        persona = await cls.get_persona(persona_id)
        if not persona:
            raise PersonaConfigurationError(f"Persona '{persona_id}' was not found.")
        if persona.get("status") != "ready":
            raise PersonaNotReadyError(f"Persona '{persona_id}' is not ready.")
        if not persona.get("heygen_avatar_id"):
            raise PersonaNotReadyError(
                f"Persona '{persona_id}' is missing heygen_avatar_id."
            )
        if not persona.get("tts_voice"):
            raise PersonaNotReadyError(f"Persona '{persona_id}' is missing tts_voice.")
        return persona
