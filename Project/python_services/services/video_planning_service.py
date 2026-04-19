import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    def _coerce_json_value(value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except Exception:
                return default
        return value

    @classmethod
    def _record_from_row(cls, row: Any) -> Dict[str, Any]:
        if not row:
            return {}

        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        approved_at = row.get("approved_at")

        scenes_data = cls._coerce_json_value(row.get("scenes_data"), [])
        if not isinstance(scenes_data, list):
            scenes_data = []

        publish_settings = cls._coerce_json_value(row.get("publish_settings"), {})
        if not isinstance(publish_settings, dict):
            publish_settings = {}

        creative_preferences = cls._coerce_json_value(
            row.get("creative_preferences"), {}
        )
        if not isinstance(creative_preferences, dict):
            creative_preferences = {}

        page_review_data = cls._coerce_json_value(row.get("page_review_data"), {})
        if not isinstance(page_review_data, dict):
            page_review_data = {}

        return {
            "id": str(row.get("id")) if row.get("id") else None,
            "plan_id": str(row.get("id")) if row.get("id") else None,
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
            "creative_preferences": creative_preferences,
            "page_review_data": page_review_data,
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at,
            "approved_at": approved_at.isoformat() if hasattr(approved_at, "isoformat") else approved_at,
        }

    @classmethod
    async def create_plan(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        scenes_json = json.dumps(payload.get("scenes_data", []))
        publish_settings_json = json.dumps(payload.get("publish_settings") or {})
        creative_preferences_json = json.dumps(
            payload.get("creative_preferences") or {}
        )
        page_review_data_json = json.dumps(payload.get("page_review_data") or {})
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.video_render_plans (
                    user_id, campaign_id, persona_id, source_url, objective,
                    script_text, scenes_data, duration_estimate, status,
                    publish_settings, creative_preferences, page_review_data, approved_at
                ) VALUES (
                    $1::uuid, $2::uuid, $3, $4, $5,
                    $6, $7::jsonb, $8, $9,
                    $10::jsonb, $11::jsonb, $12::jsonb, $13::timestamptz
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
                payload.get("status", "generated"),
                publish_settings_json,
                creative_preferences_json,
                page_review_data_json,
                payload.get("approved_at"),
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
                ORDER BY updated_at DESC NULLS LAST, created_at DESC 
                LIMIT $2
                """,
                user_id, limit
            )
        return [cls._record_from_row(dict(row)) for row in rows]

    @classmethod
    async def find_plan_for_job(
        cls, public_job_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM public.video_render_plans
                WHERE user_id = $2::uuid
                  AND (id::text = $1 OR workflow_id = $1)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                public_job_id,
                user_id,
            )
        return cls._record_from_row(dict(row)) if row else None

    @classmethod
    async def update_plan(cls, plan_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not updates:
            return await cls.get_plan(plan_id, user_id)

        allowed = {
            "script_text": "plain",
            "scenes_data": "jsonb",
            "duration_estimate": "plain",
            "status": "plain",
            "workflow_id": "plain",
            "video_url": "plain",
            "publish_settings": "jsonb",
            "creative_preferences": "jsonb",
            "page_review_data": "jsonb",
            "approved_at": "timestamptz",
        }
        assignments = []
        args = []

        for k, v in updates.items():
            field_type = allowed.get(k)
            if field_type is None:
                continue
            if field_type == "jsonb":
                args.append(json.dumps(v if v is not None else {} if k != "scenes_data" else []))
                assignments.append(f"{k} = ${len(args)}::jsonb")
                continue
            args.append(v)
            if field_type == "timestamptz":
                assignments.append(f"{k} = ${len(args)}::timestamptz")
            else:
                assignments.append(f"{k} = ${len(args)}")

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
