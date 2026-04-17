import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class VideoPlanningService:
    """
    Service for managing Video Render Plans, which hold the intermediate
    state of a video generation process between initial script generation
    (Step 1) and final workflow execution (Step 3).
    """

    @classmethod
    async def _get_pool(cls) -> Any:
        return await DatabaseService.get_pool()

    @staticmethod
    def _record_from_row(row: Any) -> Dict[str, Any]:
        if not row:
            return {}
        
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        approved_at = row.get("approved_at")
        
        scenes_data = row.get("scenes_data") or []
        if isinstance(scenes_data, str):
            try:
                scenes_data = json.loads(scenes_data)
            except Exception:
                scenes_data = []

        publish_settings = row.get("publish_settings") or {}
        if isinstance(publish_settings, str):
            try:
                publish_settings = json.loads(publish_settings)
            except Exception:
                publish_settings = {}

        return {
            "id": str(row.get("id")) if row.get("id") else None,
            "user_id": str(row.get("user_id")) if row.get("user_id") else None,
            "campaign_id": str(row.get("campaign_id")) if row.get("campaign_id") else None,
            "persona_id": str(row.get("persona_id")) if row.get("persona_id") else None,
            "source_url": row.get("source_url"),
            "objective": row.get("objective"),
            "script_text": row.get("script_text"),
            "scenes_data": scenes_data,
            "duration_estimate": row.get("duration_estimate"),
            "status": row.get("status"),
            "workflow_id": row.get("workflow_id"),
            "video_url": row.get("video_url"),
            "publish_settings": publish_settings,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
            "approved_at": approved_at.isoformat() if hasattr(approved_at, "isoformat") else approved_at,
        }

    @classmethod
    async def create_plan(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        scenes_json = json.dumps(payload.get("scenes_data", []))
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.video_render_plans (
                    user_id, campaign_id, persona_id, source_url, objective,
                    script_text, scenes_data, duration_estimate, status
                ) VALUES (
                    $1::uuid, $2::uuid, $3::uuid, $4, $5,
                    $6, $7::jsonb, $8, $9
                )
                RETURNING *
                """,
                payload.get("user_id"),
                payload.get("campaign_id"),
                payload.get("persona_id"),
                payload.get("source_url", ""),
                payload.get("objective"),
                payload.get("script_text", ""),
                scenes_json,
                payload.get("duration_estimate", 0.0),
                payload.get("status", "generated")
            )
        return cls._record_from_row(dict(row))

    @classmethod
    async def get_plan(cls, plan_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM public.video_render_plans WHERE id = $1::uuid AND user_id = $2::uuid",
                plan_id, user_id
            )
        return cls._record_from_row(dict(row)) if row else None

    @classmethod
    async def list_plans(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM public.video_render_plans 
                WHERE user_id = $1::uuid 
                ORDER BY created_at DESC 
                LIMIT $2
                """,
                user_id, limit
            )
        return [cls._record_from_row(dict(row)) for row in rows]

    @classmethod
    async def update_plan(cls, plan_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not updates:
            return await cls.get_plan(plan_id, user_id)
            
        allowed = ["script_text", "scenes_data", "duration_estimate", "status", "workflow_id", "video_url", "publish_settings"]
        assignments = []
        args = []
        
        for k, v in updates.items():
            if k in allowed:
                args.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
                arg_idx = len(args)
                if k in ["scenes_data", "publish_settings"]:
                    assignments.append(f"{k} = ${arg_idx}::jsonb")
                else:
                    assignments.append(f"{k} = ${arg_idx}")
                    
        if not assignments:
            return await cls.get_plan(plan_id, user_id)
            
        args.append(plan_id)
        args.append(user_id)
        
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE public.video_render_plans
                SET {', '.join(assignments)}, updated_at = NOW()
                WHERE id = ${len(args)-1}::uuid AND user_id = ${len(args)}::uuid
                RETURNING *
                """,
                *args
            )
        return cls._record_from_row(dict(row)) if row else None

    @classmethod
    async def approve_plan(cls, plan_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        return await cls.update_plan(
            plan_id, user_id, 
            {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}
        )

    @classmethod
    async def delete_plan(cls, plan_id: str, user_id: str) -> bool:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM public.video_render_plans WHERE id = $1::uuid AND user_id = $2::uuid",
                plan_id, user_id
            )
            return res == "DELETE 1"

