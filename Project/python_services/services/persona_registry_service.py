"""
Persona registry helpers for short-video pipeline bootstrap and reuse.
"""

from __future__ import annotations

import asyncio
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    asyncpg = None

from services.errors import PersonaConfigurationError, PersonaNotReadyError
from config.settings import settings
from services.customer_media_service import CustomerMediaService
from services.google_tts_service import GoogleTTSService
from services.telegram_link_service import TelegramLinkService

logger = logging.getLogger(__name__)
_SYSTEM_PERSONA_USER_ID = "00000000-0000-0000-0000-000000000001"


def _persona_db_write_timeout_seconds() -> float:
    raw_value = os.getenv("PERSONA_DB_WRITE_TIMEOUT_SECONDS", "3.0").strip()
    try:
        timeout = float(raw_value)
    except ValueError:
        timeout = 3.0
    return max(0.5, timeout)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_uuid(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(UUID(text))
    except (TypeError, ValueError):
        return None


class PersonaRegistryService:
    _pool: Optional[Any] = None
    _pool_lock = asyncio.Lock()
    _memory_store: Dict[str, Dict[str, Any]] = {}

    @classmethod
    async def _resolve_owner_user_id(
        cls,
        *,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> str:
        normalized_user_id = _normalize_uuid(user_id)
        if user_id and not normalized_user_id:
            raise PersonaConfigurationError("user_id must be a valid UUID")
        if normalized_user_id:
            return normalized_user_id

        if owner_key:
            owner_user_id = await TelegramLinkService.resolve_user_id_for_owner_key(
                owner_key,
                allow_fallback=False,
            )
            if owner_user_id:
                return owner_user_id
            raise PersonaConfigurationError(
                "Telegram owner scope is invalid or not linked. "
                "Please link your Telegram account via the dashboard first."
            )
        if settings.is_production_like:
            raise PersonaConfigurationError(
                "user_id is required for persona operations."
            )
        return _SYSTEM_PERSONA_USER_ID

    @classmethod
    async def _ensure_owner_user_row(
        cls, user_id: str, owner_key: Optional[str]
    ) -> None:
        if user_id == _SYSTEM_PERSONA_USER_ID:
            return
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id
                FROM public.users
                WHERE id = $1::uuid
                LIMIT 1
                """,
                user_id,
            )
            if row is None:
                raise PersonaConfigurationError(
                    "Resolved persona owner user_id does not exist in public.users. "
                    "Please ensure your Telegram account is linked via the dashboard."
                )

    @classmethod
    def _legacy_owner_scope_enabled(
        cls,
        *,
        user_id: Optional[str],
        owner_key: Optional[str],
        resolved_user_id: Optional[str] = None,
    ) -> bool:
        return bool(
            owner_key
            and not user_id
            and not settings.is_production_like
            and (
                resolved_user_id is None or resolved_user_id != _SYSTEM_PERSONA_USER_ID
            )
        )

    @classmethod
    def _memory_key(cls, user_id: str, persona_id: str) -> str:
        return f"{user_id}:{persona_id}"

    @classmethod
    def _scope_candidates(
        cls,
        *,
        resolved_user_id: str,
        user_id: Optional[str],
        owner_key: Optional[str],
    ) -> List[str]:
        candidates = [resolved_user_id]
        if cls._legacy_owner_scope_enabled(
            user_id=user_id,
            owner_key=owner_key,
            resolved_user_id=resolved_user_id,
        ):
            candidates.append(_SYSTEM_PERSONA_USER_ID)
        deduped: List[str] = []
        for candidate in candidates:
            if candidate and candidate not in deduped:
                deduped.append(candidate)
        return deduped

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
            "user_id": str(row.get("user_id")) if row.get("user_id") else None,
            "persona_id": row.get("persona_id"),
            "display_name": row.get("display_name") or row.get("persona_id"),
            "language": row.get("language") or "English",
            "tts_voice": row.get("tts_voice"),
            "avatar_image_url": row.get("avatar_image_url"),
            "avatar_source_type": row.get("avatar_source_type"),
            "avatar_prompt": row.get("avatar_prompt"),
            "heygen_avatar_id": row.get("heygen_avatar_id"),
            "avatar_media_asset_id": str(row.get("avatar_media_asset_id"))
            if row.get("avatar_media_asset_id")
            else None,
            "status": row.get("status") or "draft",
            "video_count": int(row.get("video_count") or 0),
            "tone_default": row.get("tone_default"),
            "market_default": row.get("market_default"),
            "thumbnail_url": row.get("thumbnail_url"),
            "description": row.get("description"),
            "avatar_storage_bucket": row.get("avatar_storage_bucket"),
            "avatar_storage_path": row.get("avatar_storage_path"),
            "created_at": created_at.isoformat()
            if hasattr(created_at, "isoformat")
            else created_at,
            "updated_at": updated_at.isoformat()
            if hasattr(updated_at, "isoformat")
            else updated_at,
        }

    @classmethod
    async def _decorate_persona_record(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        decorated = deepcopy(record)
        access = await CustomerMediaService.build_access_url(
            bucket_name=decorated.get("avatar_storage_bucket"),
            storage_path=decorated.get("avatar_storage_path"),
        )
        if access:
            decorated["avatar_image_url"] = access["access_url"]
            decorated["avatar_image_expires_at"] = access.get("expires_at")
        decorated.pop("avatar_storage_bucket", None)
        decorated.pop("avatar_storage_path", None)
        return decorated

    @classmethod
    async def _list_from_db(
        cls, *, user_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pool = await cls._get_pool()
        query = """
            SELECT
                p.user_id,
                p.persona_id,
                p.display_name,
                p.language,
                p.tts_voice,
                p.avatar_image_url,
                p.avatar_source_type,
                p.avatar_prompt,
                p.heygen_avatar_id,
                p.avatar_media_asset_id,
                p.status,
                p.video_count,
                p.tone_default,
                p.market_default,
                p.thumbnail_url,
                p.description,
                ma.bucket_name AS avatar_storage_bucket,
                ma.storage_path AS avatar_storage_path,
                p.created_at,
                p.updated_at
            FROM public.personas p
            LEFT JOIN public.media_assets ma
              ON ma.id = p.avatar_media_asset_id
            WHERE p.user_id = $1::uuid
        """
        args: List[Any] = [user_id]
        if status:
            query += " AND p.status = $2"
            args.append(status)
        query += " ORDER BY p.created_at DESC NULLS LAST, p.persona_id ASC"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        records = [cls._record_from_row(dict(row)) for row in rows]
        decorated: List[Dict[str, Any]] = []
        for item in records:
            try:
                decorated.append(await cls._decorate_persona_record(item))
            except Exception as exc:
                logger.error(
                    "Failed to decorate persona record %s: %s",
                    item.get("persona_id"),
                    exc,
                )
                decorated.append(item)
        return decorated

    @classmethod
    async def _list_unowned_from_db(
        cls, *, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pool = await cls._get_pool()
        query = """
            SELECT
                p.user_id,
                p.persona_id,
                p.display_name,
                p.language,
                p.tts_voice,
                p.avatar_image_url,
                p.avatar_source_type,
                p.avatar_prompt,
                p.heygen_avatar_id,
                p.avatar_media_asset_id,
                p.status,
                p.video_count,
                p.tone_default,
                p.market_default,
                p.thumbnail_url,
                p.description,
                ma.bucket_name AS avatar_storage_bucket,
                ma.storage_path AS avatar_storage_path,
                p.created_at,
                p.updated_at
            FROM public.personas p
            LEFT JOIN public.media_assets ma
              ON ma.id = p.avatar_media_asset_id
            WHERE p.user_id IS NULL
        """
        args: List[Any] = []
        if status:
            query += " AND p.status = $1"
            args.append(status)
        query += " ORDER BY p.created_at DESC NULLS LAST, p.persona_id ASC"

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
        records = [cls._record_from_row(dict(row)) for row in rows]
        decorated: List[Dict[str, Any]] = []
        for item in records:
            try:
                decorated.append(await cls._decorate_persona_record(item))
            except Exception as exc:
                logger.error(
                    "Failed to decorate persona record %s: %s",
                    item.get("persona_id"),
                    exc,
                )
                decorated.append(item)
        return decorated

    @classmethod
    async def _get_from_db(
        cls, persona_id: str, *, user_id: str
    ) -> Optional[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.user_id,
                    p.persona_id,
                    p.display_name,
                    p.language,
                    p.tts_voice,
                    p.avatar_image_url,
                    p.avatar_source_type,
                    p.avatar_prompt,
                    p.heygen_avatar_id,
                    p.avatar_media_asset_id,
                    p.status,
                    p.video_count,
                    p.tone_default,
                    p.market_default,
                    p.thumbnail_url,
                    p.description,
                    ma.bucket_name AS avatar_storage_bucket,
                    ma.storage_path AS avatar_storage_path,
                    p.created_at,
                    p.updated_at
                FROM public.personas p
                LEFT JOIN public.media_assets ma
                  ON ma.id = p.avatar_media_asset_id
                WHERE p.persona_id = $1
                  AND p.user_id = $2::uuid
                LIMIT 1
                """,
                persona_id,
                user_id,
            )
        if row is None:
            return None
        return await cls._decorate_persona_record(cls._record_from_row(dict(row)))

    @classmethod
    async def _get_unowned_from_db(cls, persona_id: str) -> Optional[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.user_id,
                    p.persona_id,
                    p.display_name,
                    p.language,
                    p.tts_voice,
                    p.avatar_image_url,
                    p.avatar_source_type,
                    p.avatar_prompt,
                    p.heygen_avatar_id,
                    p.avatar_media_asset_id,
                    p.status,
                    p.video_count,
                    p.tone_default,
                    p.market_default,
                    p.thumbnail_url,
                    p.description,
                    ma.bucket_name AS avatar_storage_bucket,
                    ma.storage_path AS avatar_storage_path,
                    p.created_at,
                    p.updated_at
                FROM public.personas p
                LEFT JOIN public.media_assets ma
                  ON ma.id = p.avatar_media_asset_id
                WHERE p.persona_id = $1
                  AND p.user_id IS NULL
                LIMIT 1
                """,
                persona_id,
            )
        if row is None:
            return None
        return await cls._decorate_persona_record(cls._record_from_row(dict(row)))

    @classmethod
    async def _find_personas_by_id_global(cls, persona_id: str) -> List[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    p.user_id,
                    p.persona_id,
                    p.display_name,
                    p.language,
                    p.tts_voice,
                    p.avatar_image_url,
                    p.avatar_source_type,
                    p.avatar_prompt,
                    p.heygen_avatar_id,
                    p.avatar_media_asset_id,
                    p.status,
                    p.video_count,
                    p.tone_default,
                    p.market_default,
                    p.thumbnail_url,
                    p.description,
                    ma.bucket_name AS avatar_storage_bucket,
                    ma.storage_path AS avatar_storage_path,
                    p.created_at,
                    p.updated_at
                FROM public.personas p
                LEFT JOIN public.media_assets ma
                  ON ma.id = p.avatar_media_asset_id
                WHERE p.persona_id = $1
                ORDER BY p.created_at DESC NULLS LAST, p.updated_at DESC NULLS LAST
                """,
                persona_id,
            )
        records = [cls._record_from_row(dict(row)) for row in rows]
        decorated: List[Dict[str, Any]] = []
        for item in records:
            try:
                decorated.append(await cls._decorate_persona_record(item))
            except Exception as exc:
                logger.error(
                    "Failed to decorate persona record %s: %s",
                    item.get("persona_id"),
                    exc,
                )
                decorated.append(item)
        return decorated

    @classmethod
    def _dedupe_personas(cls, personas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for persona in personas:
            persona_id = str(persona.get("persona_id") or "").strip()
            if not persona_id or persona_id in seen_ids:
                continue
            seen_ids.add(persona_id)
            deduped.append(persona)
        return deduped

    @classmethod
    async def _compatible_existing_persona(
        cls,
        persona_id: str,
        *,
        candidate_user_ids: List[str],
        include_unowned: bool,
    ) -> Optional[Dict[str, Any]]:
        for candidate_user_id in candidate_user_ids:
            existing = await cls._get_from_db(persona_id, user_id=candidate_user_id)
            if existing:
                return existing
        if include_unowned:
            return await cls._get_unowned_from_db(persona_id)
        return None

    @classmethod
    async def _recover_duplicate_persona(
        cls,
        persona_id: str,
        *,
        candidate_user_ids: List[str],
        include_unowned: bool,
    ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        compatible = await cls._compatible_existing_persona(
            persona_id,
            candidate_user_ids=candidate_user_ids,
            include_unowned=include_unowned,
        )
        if compatible:
            return compatible, compatible

        global_matches = await cls._find_personas_by_id_global(persona_id)
        if not global_matches:
            return None, None

        compatible_user_ids = set(candidate_user_ids)
        for match in global_matches:
            if match.get("user_id") in compatible_user_ids:
                return match, match
            if include_unowned and not match.get("user_id"):
                return match, match

        return None, global_matches[0]

    @classmethod
    async def _create_in_memory(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = _utcnow_iso()
        record = {
            "user_id": payload["user_id"],
            "persona_id": payload["persona_id"],
            "display_name": payload["display_name"],
            "language": payload["language"],
            "tts_voice": payload["tts_voice"],
            "avatar_image_url": payload.get("avatar_image_url"),
            "avatar_source_type": payload.get("avatar_source_type"),
            "avatar_prompt": payload.get("avatar_prompt"),
            "heygen_avatar_id": payload.get("heygen_avatar_id"),
            "avatar_media_asset_id": payload.get("avatar_media_asset_id"),
            "status": payload.get("status", "draft"),
            "video_count": int(payload.get("video_count", 0)),
            "tone_default": payload.get("tone_default"),
            "market_default": payload.get("market_default"),
            "thumbnail_url": payload.get("thumbnail_url"),
            "description": payload.get("description"),
            "created_at": now,
            "updated_at": now,
        }
        cls._memory_store[cls._memory_key(record["user_id"], record["persona_id"])] = (
            record
        )
        return deepcopy(record)

    @classmethod
    async def _create_in_db(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.personas (
                    user_id,
                    persona_id,
                    display_name,
                    language,
                    tts_voice,
                    avatar_image_url,
                    avatar_source_type,
                    avatar_prompt,
                    heygen_avatar_id,
                    avatar_media_asset_id,
                    status,
                    video_count,
                    tone_default,
                    market_default,
                    thumbnail_url,
                    description
                )
                VALUES (
                    $1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10::uuid, $11, $12, $13, $14, $15, $16
                )
                """,
                payload["user_id"],
                payload["persona_id"],
                payload["display_name"],
                payload["language"],
                payload["tts_voice"],
                payload.get("avatar_image_url"),
                payload.get("avatar_source_type"),
                payload.get("avatar_prompt"),
                payload.get("heygen_avatar_id"),
                payload.get("avatar_media_asset_id"),
                payload.get("status", "draft"),
                int(payload.get("video_count", 0)),
                payload.get("tone_default"),
                payload.get("market_default"),
                payload.get("thumbnail_url"),
                payload.get("description"),
            )
        return await cls._get_from_db(payload["persona_id"], user_id=payload["user_id"])

    @classmethod
    async def _update_in_db(
        cls,
        persona_id: str,
        fields: Dict[str, Any],
        *,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        if not fields:
            return await cls._get_from_db(persona_id, user_id=user_id)

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
            "avatar_media_asset_id",
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
                if field == "avatar_media_asset_id" and fields[field] is not None:
                    assignments.append(f"{field} = ${len(args)}::uuid")
                else:
                    assignments.append(f"{field} = ${len(args)}")

        if not assignments:
            return await cls._get_from_db(persona_id, user_id=user_id)

        args.append(persona_id)
        args.append(user_id)
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE public.personas
                SET {", ".join(assignments)},
                    updated_at = NOW()
                WHERE persona_id = ${len(args) - 1}
                  AND user_id = ${len(args)}::uuid
                RETURNING persona_id
                """,
                *args,
            )
        if row is None:
            return None
        return await cls._get_from_db(persona_id, user_id=user_id)

    @classmethod
    async def list_personas(
        cls,
        status: Optional[str] = None,
        *,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resolved_user_id = await cls._resolve_owner_user_id(
            user_id=user_id,
            owner_key=owner_key,
        )
        candidate_user_ids = cls._scope_candidates(
            resolved_user_id=resolved_user_id,
            user_id=user_id,
            owner_key=owner_key,
        )
        include_legacy_scope = cls._legacy_owner_scope_enabled(
            user_id=user_id,
            owner_key=owner_key,
            resolved_user_id=resolved_user_id,
        )
        try:
            for candidate_user_id in candidate_user_ids:
                personas = await cls._list_from_db(
                    status=status, user_id=candidate_user_id
                )
                if personas:
                    return personas

            if include_legacy_scope:
                legacy_personas: List[Dict[str, Any]] = []
                if _SYSTEM_PERSONA_USER_ID not in candidate_user_ids:
                    legacy_personas.extend(
                        await cls._list_from_db(
                            status=status, user_id=_SYSTEM_PERSONA_USER_ID
                        )
                    )
                legacy_personas.extend(await cls._list_unowned_from_db(status=status))
                return cls._dedupe_personas(legacy_personas)

            return []
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.exception("Persona DB list failed, using in-memory fallback")
            personas = [
                item
                for item in cls._memory_store.values()
                if item.get("user_id") in candidate_user_ids
            ]
            if status:
                personas = [item for item in personas if item.get("status") == status]
            return [deepcopy(item) for item in personas]

    @classmethod
    async def get_persona(
        cls,
        persona_id: str,
        *,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        resolved_user_id = await cls._resolve_owner_user_id(
            user_id=user_id,
            owner_key=owner_key,
        )
        candidate_user_ids = cls._scope_candidates(
            resolved_user_id=resolved_user_id,
            user_id=user_id,
            owner_key=owner_key,
        )
        include_legacy_scope = cls._legacy_owner_scope_enabled(
            user_id=user_id,
            owner_key=owner_key,
            resolved_user_id=resolved_user_id,
        )
        try:
            for candidate_user_id in candidate_user_ids:
                persona = await cls._get_from_db(persona_id, user_id=candidate_user_id)
                if persona:
                    return persona
            if include_legacy_scope:
                return await cls._get_unowned_from_db(persona_id)
            return None
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.warning(
                "Persona DB lookup failed, using in-memory fallback: %s", exc
            )
            for candidate_user_id in candidate_user_ids:
                record = cls._memory_store.get(
                    cls._memory_key(candidate_user_id, persona_id)
                )
                if record:
                    return deepcopy(record)
            return None

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

        resolved_user_id = await cls._resolve_owner_user_id(
            user_id=payload.get("user_id"),
            owner_key=payload.get("owner_key"),
        )
        candidate_user_ids = cls._scope_candidates(
            resolved_user_id=resolved_user_id,
            user_id=payload.get("user_id"),
            owner_key=payload.get("owner_key"),
        )
        include_legacy_scope = cls._legacy_owner_scope_enabled(
            user_id=payload.get("user_id"),
            owner_key=payload.get("owner_key"),
            resolved_user_id=resolved_user_id,
        )
        normalized_voice = GoogleTTSService.resolve_voice_name(
            payload.get("tts_voice"),
            language=payload.get("language"),
        )
        base_payload = {
            **payload,
            "user_id": resolved_user_id,
            "tts_voice": normalized_voice,
            "status": payload.get("status") or "draft",
            "video_count": int(payload.get("video_count", 0)),
        }

        try:
            if resolved_user_id != _SYSTEM_PERSONA_USER_ID:
                await cls._ensure_owner_user_row(
                    resolved_user_id, payload.get("owner_key")
                )
            existing = await cls._compatible_existing_persona(
                payload["persona_id"],
                candidate_user_ids=candidate_user_ids,
                include_unowned=include_legacy_scope,
            )
            if existing:
                return existing
            return await asyncio.wait_for(
                cls._create_in_db(base_payload),
                timeout=_persona_db_write_timeout_seconds(),
            )
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            message = str(exc).lower()
            if "duplicate key value violates unique constraint" in message:
                recovered_persona = None
                conflicting_persona = None
                try:
                    (
                        recovered_persona,
                        conflicting_persona,
                    ) = await cls._recover_duplicate_persona(
                        payload["persona_id"],
                        candidate_user_ids=candidate_user_ids,
                        include_unowned=include_legacy_scope,
                    )
                except Exception:
                    recovered_persona = None
                    conflicting_persona = None

                if recovered_persona:
                    return recovered_persona
                if conflicting_persona and conflicting_persona.get(
                    "user_id"
                ) not in set(candidate_user_ids):
                    raise PersonaConfigurationError(
                        "persona_id is colliding with a legacy global persona index. "
                        "Apply migration 20260326_personas_user_scoped_unique.sql or choose a different persona ID."
                    ) from exc
                if "idx_personas_persona_id" in message or "persona_id_key" in message:
                    raise PersonaConfigurationError(
                        "persona_id is colliding with an existing global index. "
                        "Apply migration 20260326_personas_user_scoped_unique.sql or choose a different persona ID."
                    ) from exc
                raise PersonaConfigurationError(
                    f"Persona '{payload['persona_id']}' already exists for this owner."
                ) from exc
            logger.warning(
                "Persona DB create failed, using in-memory fallback: %s", exc
            )
            return await cls._create_in_memory(base_payload)

    @classmethod
    async def update_persona(
        cls,
        persona_id: str,
        fields: Dict[str, Any],
        *,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        resolved_user_id = await cls._resolve_owner_user_id(
            user_id=user_id,
            owner_key=owner_key,
        )
        candidate_user_ids = cls._scope_candidates(
            resolved_user_id=resolved_user_id,
            user_id=user_id,
            owner_key=owner_key,
        )
        include_legacy_scope = cls._legacy_owner_scope_enabled(
            user_id=user_id,
            owner_key=owner_key,
            resolved_user_id=resolved_user_id,
        )
        normalized_fields = dict(fields)
        if normalized_fields.get("tts_voice"):
            language = normalized_fields.get("language")
            if not language:
                existing = await cls.get_persona(persona_id, user_id=resolved_user_id)
                language = existing.get("language") if existing else None
            normalized_fields["tts_voice"] = GoogleTTSService.resolve_voice_name(
                normalized_fields.get("tts_voice"),
                language=language,
            )
        try:
            for candidate_user_id in candidate_user_ids:
                updated = await cls._update_in_db(
                    persona_id,
                    normalized_fields,
                    user_id=candidate_user_id,
                )
                if updated:
                    return updated
            if include_legacy_scope:
                pool = await cls._get_pool()
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
                    "avatar_media_asset_id",
                    "status",
                    "video_count",
                    "tone_default",
                    "market_default",
                    "thumbnail_url",
                    "description",
                ]
                for field in allowed_fields:
                    if field in normalized_fields:
                        args.append(normalized_fields[field])
                        assignments.append(f"{field} = ${len(args)}")
                if assignments:
                    args.append(persona_id)
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(
                            f"""
                            UPDATE public.personas
                            SET {", ".join(assignments)},
                                updated_at = NOW()
                            WHERE persona_id = ${len(args)}
                              AND user_id IS NULL
                            RETURNING persona_id
                            """,
                            *args,
                        )
                    if row is not None:
                        return await cls._get_unowned_from_db(persona_id)
            return None
        except Exception as exc:  # pragma: no cover - degraded-mode fallback
            logger.warning(
                "Persona DB update failed, using in-memory fallback: %s", exc
            )
            for candidate_user_id in candidate_user_ids:
                memory_key = cls._memory_key(candidate_user_id, persona_id)
                if memory_key not in cls._memory_store:
                    continue
                cls._memory_store[memory_key].update(normalized_fields)
                cls._memory_store[memory_key]["updated_at"] = _utcnow_iso()
                return deepcopy(cls._memory_store[memory_key])
            return None

    @classmethod
    def build_readiness_report(
        cls, persona_id: str, persona: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        checks = {
            "status_ready": bool(persona and persona.get("status") == "ready"),
            "has_tts_voice": bool(persona and persona.get("tts_voice")),
            "has_avatar_asset": bool(persona and persona.get("avatar_media_asset_id")),
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
        elif not checks["has_avatar_asset"]:
            blocking_reason = "Missing avatar_media_asset_id. Save persona media first."
        elif not checks["has_heygen_avatar_id"]:
            blocking_reason = (
                "Missing heygen_avatar_id. Run persona avatar setup first."
            )

        return {
            "persona_id": persona_id,
            "ready": blocking_reason is None,
            "status": status,
            "blocking_reason": blocking_reason,
            "checks": checks,
        }

    @classmethod
    async def get_readiness(
        cls,
        persona_id: str,
        *,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        persona = await cls.get_persona(
            persona_id, user_id=user_id, owner_key=owner_key
        )
        return cls.build_readiness_report(persona_id, persona)

    @classmethod
    async def resolve_ready_persona(
        cls,
        persona_id: str,
        *,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        persona = await cls.get_persona(
            persona_id, user_id=user_id, owner_key=owner_key
        )
        if not persona:
            raise PersonaConfigurationError(f"Persona '{persona_id}' was not found.")
        if persona.get("status") != "ready":
            raise PersonaNotReadyError(f"Persona '{persona_id}' is not ready.")
        if not persona.get("avatar_media_asset_id"):
            raise PersonaNotReadyError(
                f"Persona '{persona_id}' is missing avatar_media_asset_id."
            )
        if not persona.get("heygen_avatar_id"):
            raise PersonaNotReadyError(
                f"Persona '{persona_id}' is missing heygen_avatar_id."
            )
        if not persona.get("tts_voice"):
            raise PersonaNotReadyError(f"Persona '{persona_id}' is missing tts_voice.")
        return persona
