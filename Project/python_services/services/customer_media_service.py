"""
Customer-scoped media access helpers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.database_service import DatabaseService
from services.storage_service import StorageService


class CustomerMediaService:
    @staticmethod
    async def list_recent_assets(
        *,
        user_id: str,
        asset_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 5), 20))
        pool = await DatabaseService.get_pool()
        query = """
            SELECT
                id,
                user_id,
                persona_id,
                url,
                filename,
                bucket_name,
                storage_path,
                type,
                status,
                metadata,
                created_at
            FROM public.media_assets
            WHERE user_id = $1::uuid
        """
        args: List[Any] = [user_id]
        if asset_type:
            query += " AND type = $2"
            args.append(str(asset_type).lower())
            limit_arg_index = 3
        else:
            limit_arg_index = 2
        query += (
            f" ORDER BY created_at DESC NULLS LAST, id DESC LIMIT ${limit_arg_index}"
        )
        args.append(normalized_limit)

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)

        assets: List[Dict[str, Any]] = []
        import json
        for row in rows:
            raw_metadata = row.get("metadata")
            if isinstance(raw_metadata, str):
                try:
                    metadata = json.loads(raw_metadata)
                except Exception:
                    metadata = {}
            else:
                metadata = raw_metadata or {}

            access = await CustomerMediaService.build_access_url(
                bucket_name=row.get("bucket_name"),
                storage_path=row.get("storage_path"),
            )
            access_url = (access or {}).get("access_url") or row.get("url")
            created_at = row.get("created_at")
            assets.append(
                {
                    "asset_id": str(row.get("id")),
                    "persona_id": row.get("persona_id"),
                    "type": row.get("type"),
                    "status": row.get("status"),
                    "filename": row.get("filename"),
                    "title": metadata.get("topic")
                    or metadata.get("generation_prompt")
                    or row.get("filename"),
                    "access_url": access_url,
                    "created_at": created_at.isoformat()
                    if hasattr(created_at, "isoformat")
                    else created_at,
                }
            )
        return assets

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
