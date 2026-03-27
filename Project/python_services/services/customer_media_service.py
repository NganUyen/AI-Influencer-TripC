"""
Customer-scoped media access helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.database_service import DatabaseService
from services.storage_service import StorageService


class CustomerMediaService:
    @staticmethod
    async def get_access_url(*, user_id: str, asset_id: str) -> Dict[str, Any]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id,
                    user_id,
                    bucket_name,
                    storage_path
                FROM public.media_assets
                WHERE id = $1::uuid
                  AND user_id = $2::uuid
                LIMIT 1
                """,
                asset_id,
                user_id,
            )
        if row is None:
            raise PermissionError("Media asset not found.")
        if not row.get("storage_path"):
            raise ValueError("Media asset is missing storage_path.")

        storage = StorageService()
        access_url = await storage.get_access_url(str(row["storage_path"]))
        expires_at = storage.signed_url_expires_at()
        return {
            "asset_id": str(row["id"]),
            "access_url": access_url,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }

    @staticmethod
    async def build_access_url(
        *,
        bucket_name: Optional[str],
        storage_path: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        if not bucket_name or not storage_path:
            return None

        storage = StorageService()
        access_url = await storage.get_access_url(storage_path)
        expires_at = storage.signed_url_expires_at()
        return {
            "access_url": access_url,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
