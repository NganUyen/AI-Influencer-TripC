"""
MediaStorageService
===================
Non-blocking helper that:
  1. Downloads a URL (or receives raw bytes) and uploads to Supabase Storage
     under the 'media' bucket  (image/ or video/ prefix).
  2. Inserts a row into public.media_assets with storage metadata.

Design goals:
  - Never raise exceptions that break the calling activity.
  - All public methods are safe to fire-and-forget inside try/except.
  - Built on top of the existing StorageService; does NOT duplicate upload logic.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from io import BytesIO
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
MEDIA_BUCKET = "media"
SUPABASE_STORAGE_PUBLIC_BASE = (
    f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{MEDIA_BUCKET}"
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _supabase_headers() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    }


def _public_url(storage_path: str) -> str:
    """Construct public URL for an object in the 'media' bucket."""
    clean = storage_path.lstrip("/")
    return f"{SUPABASE_STORAGE_PUBLIC_BASE}/{clean}"


# ─── Core upload ──────────────────────────────────────────────────────────────

async def _upload_to_media_bucket(
    data: bytes,
    path: str,
    content_type: str,
) -> str:
    """
    Upload *data* to Supabase Storage under bucket='media' at key *path*.
    Returns the public URL of the uploaded object.
    Uses upsert=true so re-runs are idempotent.
    """
    api_base = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1"
    url = f"{api_base}/object/{MEDIA_BUCKET}/{path.lstrip('/')}"
    headers = {
        **_supabase_headers(),
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, content=data, headers=headers)
        response.raise_for_status()

    public = _public_url(path)
    logger.info("Uploaded to media bucket: %s  ->  %s", path, public)
    return public


# ─── DB record ────────────────────────────────────────────────────────────────

async def _record_media_asset(
    campaign_id: str,
    asset_type: str,           # 'IMAGE' | 'AUDIO' | 'VIDEO'
    generation_prompt: str,
    storage_path: str,
    public_url: str,
    mime_type: str,
    file_size: int,
    provider_job_id: Optional[str] = None,
    status: str = "COMPLETED",
) -> None:
    """
    Insert a row into public.media_assets via Supabase PostgREST REST API.
    Uses service_role key so RLS is bypassed.
    """
    rest_url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/media_assets"
    headers = {
        **_supabase_headers(),
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    payload = {
        "id": str(uuid.uuid4()),
        "campaign_id": campaign_id,
        "asset_type": asset_type,            # mapped to asset_type_enum
        "generation_prompt": generation_prompt,
        "storage_bucket": MEDIA_BUCKET,
        "storage_path": storage_path,
        "public_url": public_url,
        "mime_type": mime_type,
        "file_size": file_size,
        "status": status,                    # mapped to asset_status enum
    }
    if provider_job_id:
        payload["provider_job_id"] = provider_job_id

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(rest_url, json=payload, headers=headers)
        response.raise_for_status()

    logger.info("Recorded media_asset for campaign=%s  path=%s", campaign_id, storage_path)


# ─── Public service class ─────────────────────────────────────────────────────

class MediaStorageService:
    """
    Lightweight façade.  All methods swallow exceptions and log warnings so that
    they never break the surrounding activity pipeline.
    """

    # ── upload from raw bytes ────────────────────────────────────────────────
    async def upload_bytes(
        self,
        data: bytes,
        destination_path: str,   # e.g. 'image/day1/tiktok_abc12345.png'
        content_type: str,
        campaign_id: str,
        asset_type: str,         # IMAGE | AUDIO | VIDEO
        generation_prompt: str,
        provider_job_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Upload raw bytes to the 'media' bucket and record in media_assets.
        Returns the public URL or None on failure.
        """
        try:
            public_url = await _upload_to_media_bucket(
                data=data,
                path=destination_path,
                content_type=content_type,
            )
            await _record_media_asset(
                campaign_id=campaign_id,
                asset_type=asset_type,
                generation_prompt=generation_prompt,
                storage_path=destination_path,
                public_url=public_url,
                mime_type=content_type,
                file_size=len(data),
                provider_job_id=provider_job_id,
            )
            return public_url
        except Exception as exc:
            logger.warning("MediaStorageService.upload_bytes failed: %s", exc)
            return None

    # ── upload from URL ──────────────────────────────────────────────────────
    async def upload_from_url(
        self,
        url: str,
        destination_path: str,   # e.g. 'image/day1/tiktok_abc12345.png'
        campaign_id: str,
        asset_type: str,         # IMAGE | AUDIO | VIDEO
        generation_prompt: str,
        provider_job_id: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Optional[str]:
        """
        Download *url*, upload to the 'media' bucket, record in media_assets.
        Returns the public URL or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.content
                detected_ct = (
                    content_type
                    or resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
                )

            return await self.upload_bytes(
                data=data,
                destination_path=destination_path,
                content_type=detected_ct,
                campaign_id=campaign_id,
                asset_type=asset_type,
                generation_prompt=generation_prompt,
                provider_job_id=provider_job_id,
            )
        except Exception as exc:
            logger.warning("MediaStorageService.upload_from_url failed (%s): %s", url, exc)
            return None

    # ── record only (already stored elsewhere) ───────────────────────────────
    async def record_asset(
        self,
        campaign_id: str,
        asset_type: str,
        generation_prompt: str,
        storage_path: str,
        public_url: str,
        mime_type: str,
        file_size: int = 0,
        provider_job_id: Optional[str] = None,
        status: str = "COMPLETED",
    ) -> None:
        """
        Record an already-uploaded asset in media_assets without uploading.
        Silent on failure.
        """
        try:
            await _record_media_asset(
                campaign_id=campaign_id,
                asset_type=asset_type,
                generation_prompt=generation_prompt,
                storage_path=storage_path,
                public_url=public_url,
                mime_type=mime_type,
                file_size=file_size,
                provider_job_id=provider_job_id,
                status=status,
            )
        except Exception as exc:
            logger.warning("MediaStorageService.record_asset failed: %s", exc)
