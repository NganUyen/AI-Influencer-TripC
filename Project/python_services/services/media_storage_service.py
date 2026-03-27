"""
MediaStorageService
===================
Uploads generated assets to object storage and records metadata in
`public.media_assets`.

Storage layout is user/persona scoped:
  users/<user_id>/personas/<persona_id>/<asset_kind>/<yyyy-mm>/<file>
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from services.database_service import DatabaseService
from services.storage_service import StorageService
from services.telegram_link_service import TelegramLinkService

logger = logging.getLogger(__name__)

MEDIA_BUCKET = "media"


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


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "")).strip("-_.")
    return cleaned[:96] or fallback


def _infer_asset_type(content_type: str, requested: Optional[str]) -> str:
    if requested:
        return requested.upper()
    normalized = (content_type or "").lower()
    if normalized.startswith("image/"):
        return "IMAGE"
    if normalized.startswith("video/"):
        return "VIDEO"
    if normalized.startswith("audio/"):
        return "AUDIO"
    return "DOCUMENT"


def _default_extension(asset_type: str, content_type: str) -> str:
    from_ct = (content_type or "").split("/", 1)
    if len(from_ct) == 2 and from_ct[1]:
        subtype = from_ct[1].split(";", 1)[0].strip().lower()
        if subtype:
            return subtype.replace("jpeg", "jpg")
    if asset_type == "IMAGE":
        return "png"
    if asset_type == "VIDEO":
        return "mp4"
    if asset_type == "AUDIO":
        return "mp3"
    return "bin"


def _now_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _normalize_asset_kind(asset_kind: Optional[str], asset_type: str) -> str:
    normalized = str(asset_kind or "").strip().lower()
    if normalized in {"avatar", "image", "video", "audio", "document"}:
        return normalized
    return asset_type.lower()


def _normalize_asset_origin(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"generated", "uploaded", "imported", "backfill"}:
        return normalized
    return "generated"


def _normalize_asset_status(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"available", "pending", "failed", "archived"}:
        return normalized
    if normalized in {"completed", "stored", "success"}:
        return "available"
    return "available"


class MediaStorageService:
    async def _resolve_user_id(
        self,
        *,
        user_id: Optional[str],
        owner_key: Optional[str],
        campaign_id: Optional[str],
        persona_id: Optional[str],
    ) -> Optional[str]:
        normalized_user = _normalize_uuid(user_id)
        if normalized_user:
            await self._ensure_user_row(normalized_user, owner_key)
            return normalized_user

        linked_owner_user = await TelegramLinkService.resolve_user_id_for_owner_key(
            owner_key,
            allow_fallback=bool(owner_key),
        )

        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            if campaign_id:
                row = await conn.fetchrow(
                    """
                    SELECT user_id
                    FROM public.campaigns
                    WHERE id = $1::uuid
                    LIMIT 1
                    """,
                    campaign_id,
                )
                if row and row.get("user_id"):
                    return str(row["user_id"])

            if persona_id and linked_owner_user:
                row = await conn.fetchrow(
                    """
                    SELECT user_id
                    FROM public.personas
                    WHERE persona_id = $1
                      AND user_id = $2::uuid
                    LIMIT 1
                    """,
                    persona_id,
                    linked_owner_user,
                )
                if row and row.get("user_id"):
                    return str(row["user_id"])
        if owner_key:
            logger.warning("Unlinked or invalid Telegram owner_key rejected: %s", owner_key)
        if linked_owner_user:
            return linked_owner_user

        return None

    async def _ensure_user_row(self, user_id: str, owner_key: Optional[str]) -> None:
        pool = await DatabaseService.get_pool()
        owner_label = (owner_key or user_id).strip() if owner_key else user_id
        sanitized = "".join(ch if ch.isalnum() else "-" for ch in owner_label.lower()).strip("-")
        if not sanitized:
            sanitized = user_id.replace("-", "")[:16]
        email = f"media-{sanitized}@local.ai-influencer.invalid"
        name = owner_key if owner_key else f"Media Owner {user_id[:8]}"

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.users (id, email, name)
                VALUES ($1::uuid, $2, $3)
                ON CONFLICT (id) DO UPDATE
                SET email = EXCLUDED.email,
                    name = COALESCE(public.users.name, EXCLUDED.name),
                    updated_at = NOW()
                """,
                user_id,
                email,
                name,
            )

    def _build_destination_path(
        self,
        *,
        asset_type: str,
        asset_kind: Optional[str],
        user_id: Optional[str],
        persona_id: Optional[str],
        content_type: str,
        file_name_hint: Optional[str],
    ) -> str:
        user_segment = _safe_segment(user_id or "system", "system")
        persona_segment = _safe_segment(persona_id or "unassigned", "unassigned")
        kind_segment = _safe_segment(
            _normalize_asset_kind(asset_kind, asset_type),
            "document",
        )
        ext = _default_extension(asset_type, content_type)

        hint = _safe_segment(file_name_hint or f"asset-{uuid.uuid4().hex[:12]}", "asset")
        if "." in hint:
            hint = hint.rsplit(".", 1)[0]

        return (
            f"users/{user_segment}/personas/{persona_segment}/"
            f"{kind_segment}/{_now_month()}/{hint}.{ext}"
        )

    async def _record_media_asset(
        self,
        *,
        user_id: str,
        asset_url: str,
        persona_id: Optional[str],
        owner_key: Optional[str],
        source_url: Optional[str],
        asset_type: str,
        bucket_name: Optional[str],
        storage_path: Optional[str],
        storage_provider: str,
        visibility: str,
        asset_origin: str,
        asset_status: str,
        provider_job_id: Optional[str],
        filename: str,
        file_size: int,
        mime_type: str,
        metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.media_assets (
                    id,
                    user_id,
                    url,
                    persona_id,
                    owner_key,
                    source_url,
                    type,
                    filename,
                    bucket_name,
                    storage_path,
                    storage_provider,
                    visibility,
                    asset_origin,
                    status,
                    provider_job_id,
                    size,
                    mime_type,
                    metadata
                )
                VALUES (
                    $1::uuid,
                    $2::uuid,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9,
                    $10,
                    $11,
                    $12,
                    $13,
                    $14,
                    $15,
                    $16,
                    $17,
                    $18::jsonb
                )
                ON CONFLICT (storage_provider, bucket_name, storage_path) DO UPDATE
                SET
                    user_id = EXCLUDED.user_id,
                    persona_id = EXCLUDED.persona_id,
                    owner_key = EXCLUDED.owner_key,
                    source_url = COALESCE(EXCLUDED.source_url, public.media_assets.source_url),
                    type = EXCLUDED.type,
                    filename = EXCLUDED.filename,
                    visibility = EXCLUDED.visibility,
                    asset_origin = EXCLUDED.asset_origin,
                    status = EXCLUDED.status,
                    provider_job_id = COALESCE(EXCLUDED.provider_job_id, public.media_assets.provider_job_id),
                    size = EXCLUDED.size,
                    mime_type = EXCLUDED.mime_type,
                    metadata = EXCLUDED.metadata
                RETURNING id, user_id, persona_id, bucket_name, storage_path, storage_provider, visibility, status
                """,
                str(uuid.uuid4()),
                user_id,
                asset_url,
                persona_id,
                owner_key,
                source_url,
                asset_type.lower(),
                filename,
                bucket_name,
                storage_path,
                storage_provider,
                visibility,
                asset_origin,
                asset_status,
                provider_job_id,
                int(file_size or 0),
                mime_type,
                metadata,
            )
        if row is None:
            return None
        return {
            "media_asset_id": str(row["id"]),
            "user_id": str(row["user_id"]),
            "persona_id": row["persona_id"],
            "bucket_name": row["bucket_name"],
            "storage_path": row["storage_path"],
            "storage_provider": row["storage_provider"],
            "visibility": row["visibility"],
            "status": row["status"],
        }

    async def upload_bytes(
        self,
        data: bytes,
        destination_path: Optional[str] = None,
        content_type: str = "application/octet-stream",
        campaign_id: Optional[str] = None,
        asset_type: Optional[str] = None,
        asset_kind: Optional[str] = None,
        asset_origin: Optional[str] = None,
        generation_prompt: str = "",
        provider_job_id: Optional[str] = None,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
        persona_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        file_name_hint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            resolved_type = _infer_asset_type(content_type, asset_type)
            resolved_user_id = await self._resolve_user_id(
                user_id=user_id,
                owner_key=owner_key,
                campaign_id=campaign_id,
                persona_id=persona_id,
            )
            if not resolved_user_id:
                logger.warning(
                    "MediaStorageService.upload_bytes skipped (missing linked user context): %s",
                    owner_key or persona_id or "unknown",
                )
                return None

            storage = StorageService()
            resolved_destination = destination_path or self._build_destination_path(
                asset_type=resolved_type,
                asset_kind=asset_kind,
                user_id=resolved_user_id,
                persona_id=persona_id,
                content_type=content_type,
                file_name_hint=file_name_hint,
            )

            access_url = await storage.upload_bytes(
                data=data,
                filename=resolved_destination,
                content_type=content_type,
            )
            normalized_origin = _normalize_asset_origin(asset_origin)

            db_metadata = {
                **(metadata or {}),
                "campaign_id": campaign_id,
                "persona_id": persona_id,
                "owner_key": owner_key,
                "provider_job_id": provider_job_id,
                "generation_prompt": generation_prompt,
                "storage_bucket": storage.bucket_name,
                "storage_path": resolved_destination,
                "storage_provider": storage.provider,
                "visibility": "private" if storage.provider == "supabase" else "public",
                "asset_origin": normalized_origin,
            }
            cleaned_metadata = {k: v for k, v in db_metadata.items() if v is not None}

            asset_row = await self._record_media_asset(
                user_id=resolved_user_id,
                asset_url=access_url,
                persona_id=persona_id,
                owner_key=owner_key,
                source_url=cleaned_metadata.get("source_url"),
                asset_type=resolved_type,
                bucket_name=storage.bucket_name,
                storage_path=resolved_destination,
                storage_provider=storage.provider,
                visibility="private" if storage.provider == "supabase" else "public",
                asset_origin=normalized_origin,
                asset_status="available",
                provider_job_id=provider_job_id,
                filename=resolved_destination,
                file_size=len(data),
                mime_type=content_type,
                metadata=cleaned_metadata,
            )
            if asset_row is None:
                return None
            return {
                **asset_row,
                "access_url": access_url,
                "url": access_url,
                "source_url": cleaned_metadata.get("source_url"),
                "expires_at": None,
            }
        except Exception as exc:
            logger.warning("MediaStorageService.upload_bytes failed: %s", exc)
            return None

    async def upload_from_url(
        self,
        url: str,
        destination_path: Optional[str] = None,
        campaign_id: Optional[str] = None,
        asset_type: Optional[str] = None,
        asset_kind: Optional[str] = None,
        asset_origin: Optional[str] = None,
        generation_prompt: str = "",
        provider_job_id: Optional[str] = None,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
        persona_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        file_name_hint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content
                detected_ct = (
                    content_type
                    or resp.headers.get("content-type", "application/octet-stream").split(";", 1)[0].strip()
                )

            return await self.upload_bytes(
                data=data,
                destination_path=destination_path,
                content_type=detected_ct,
                campaign_id=campaign_id,
                asset_type=asset_type,
                asset_kind=asset_kind,
                asset_origin=asset_origin,
                generation_prompt=generation_prompt,
                provider_job_id=provider_job_id,
                user_id=user_id,
                owner_key=owner_key,
                persona_id=persona_id,
                metadata={**(metadata or {}), "source_url": url},
                file_name_hint=file_name_hint,
            )
        except Exception as exc:
            logger.warning("MediaStorageService.upload_from_url failed (%s): %s", url, exc)
            return None

    async def record_asset(
        self,
        campaign_id: Optional[str],
        asset_type: str,
        generation_prompt: str,
        storage_path: str,
        public_url: str,
        mime_type: str,
        file_size: int = 0,
        provider_job_id: Optional[str] = None,
        status: str = "COMPLETED",
        asset_origin: Optional[str] = None,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
        persona_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            resolved_type = _infer_asset_type(mime_type, asset_type)
            resolved_user_id = await self._resolve_user_id(
                user_id=user_id,
                owner_key=owner_key,
                campaign_id=campaign_id,
                persona_id=persona_id,
            )
            if not resolved_user_id:
                logger.warning(
                    "MediaStorageService.record_asset skipped (missing user context): %s",
                    storage_path,
                )
                return None

            storage = StorageService()
            access_url = public_url or storage.get_public_url(storage_path)
            normalized_origin = _normalize_asset_origin(asset_origin)

            db_metadata = {
                **(metadata or {}),
                "campaign_id": campaign_id,
                "persona_id": persona_id,
                "owner_key": owner_key,
                "provider_job_id": provider_job_id,
                "generation_prompt": generation_prompt,
                "status": status,
                "storage_bucket": storage.bucket_name,
                "storage_path": storage_path,
                "storage_provider": storage.provider,
                "visibility": "private" if storage.provider == "supabase" else "public",
                "asset_origin": normalized_origin,
            }
            cleaned_metadata = {k: v for k, v in db_metadata.items() if v is not None}

            asset_row = await self._record_media_asset(
                user_id=resolved_user_id,
                asset_url=access_url,
                persona_id=persona_id,
                owner_key=owner_key,
                source_url=cleaned_metadata.get("source_url"),
                asset_type=resolved_type,
                bucket_name=storage.bucket_name,
                storage_path=storage_path,
                storage_provider=storage.provider,
                visibility="private" if storage.provider == "supabase" else "public",
                asset_origin=normalized_origin,
                asset_status=_normalize_asset_status(status),
                provider_job_id=provider_job_id,
                filename=storage_path,
                file_size=file_size,
                mime_type=mime_type,
                metadata=cleaned_metadata,
            )
            if asset_row is None:
                return None
            return {
                **asset_row,
                "access_url": access_url,
                "url": access_url,
                "source_url": cleaned_metadata.get("source_url"),
                "expires_at": None,
            }
        except Exception as exc:
            logger.warning("MediaStorageService.record_asset failed: %s", exc)
            return None
