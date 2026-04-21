"""
Persistence helpers for dashboard-friendly content and publishing state.
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid5

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    asyncpg = None

from config.settings import settings
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

USER_NAMESPACE = UUID("2d9d5f55-2d26-4e34-b0bb-2d2d2f67eaa1")
POSTIZ_PLATFORMS = {"twitter", "facebook", "linkedin", "youtube"}


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _json_loads_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _json_dumps_canonical(value: Any) -> str:
    return json.dumps(value or {}, sort_keys=True, default=str)


def _coerce_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sum_engagement_metrics(metrics: Dict[str, Any]) -> float:
    engagement_fields = (
        "likes",
        "comments",
        "shares",
        "saves",
        "clicks",
        "reposts",
        "bookmarks",
    )
    return sum(_coerce_float(metrics.get(field)) for field in engagement_fields)


class ContentPersistenceService:
    @staticmethod
    def empty_analytics_summary(days: int = 30) -> Dict[str, Any]:
        return {
            "total_posts": 0,
            "published_posts": 0,
            "scheduled_posts": 0,
            "failed_posts": 0,
            "total_engagement": 0,
            "average_engagement_rate": None,
            "tracked_posts": 0,
            "syndicate_jobs": {
                "triggered": 0,
                "completed": 0,
                "failed": 0,
            },
            "platforms": {},
            "time_period": f"{days}_days",
        }

    @classmethod
    async def _get_pool(cls) -> Any:
        return await DatabaseService.get_pool()

    @classmethod
    async def close_pool(cls) -> None:
        return None

    @staticmethod
    def _resolve_user_uuid(user_id: str) -> UUID:
        try:
            return UUID(str(user_id))
        except (TypeError, ValueError):
            return uuid5(USER_NAMESPACE, str(user_id))

    @classmethod
    async def _ensure_user(cls, conn: Any, raw_user_id: str) -> UUID:
        user_uuid = cls._resolve_user_uuid(raw_user_id)
        synthetic_email = f"{user_uuid.hex}@local.ai-influencer.invalid"
        display_name = str(raw_user_id)[:255]
        await conn.execute(
            """
            INSERT INTO public.users (id, email, name)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET name = COALESCE(public.users.name, EXCLUDED.name)
            """,
            user_uuid,
            synthetic_email,
            display_name,
        )
        return user_uuid

    @classmethod
    async def _resolve_content_id(
        cls,
        conn: Any,
        workflow_id: Optional[str],
        logical_post_id: Optional[str],
        content_id: Optional[str] = None,
    ) -> Optional[UUID]:
        if content_id:
            return UUID(str(content_id))

        if not workflow_id or not logical_post_id:
            return None

        resolved = await conn.fetchval(
            """
            SELECT id
            FROM public.content
            WHERE metadata->>'workflow_id' = $1
              AND metadata->>'logical_post_id' = $2
            LIMIT 1
            """,
            workflow_id,
            logical_post_id,
        )
        if resolved is None:
            return None
        return UUID(str(resolved))

    @classmethod
    async def _resolve_content_id_for_postiz_sync(
        cls,
        conn: Any,
        event: Dict[str, Any],
    ) -> Optional[UUID]:
        content_id = event.get("content_id")
        if content_id:
            return UUID(str(content_id))

        resolved = await cls._resolve_content_id(
            conn=conn,
            workflow_id=event.get("workflow_id"),
            logical_post_id=event.get("logical_post_id"),
        )
        if resolved:
            return resolved

        provider_post_id = event.get("provider_post_id")
        platform_post_id = event.get("platform_post_id")
        if provider_post_id or platform_post_id:
            matched = await conn.fetchval(
                """
                SELECT c.id
                FROM public.content c
                LEFT JOIN public.postiz_schedules ps ON ps.content_id = c.id
                WHERE ps.postiz_post_id = $1
                   OR c.metadata->>'provider_post_id' = $1
                   OR c.metadata->>'platform_post_id' = $2
                LIMIT 1
                """,
                provider_post_id,
                platform_post_id,
            )
            if matched:
                return UUID(str(matched))

        return None

    @classmethod
    async def _resolve_content_id_for_growchief_sync(
        cls,
        conn: Any,
        event: Dict[str, Any],
    ) -> Optional[UUID]:
        content_id = event.get("content_id")
        if content_id:
            return UUID(str(content_id))

        resolved = await cls._resolve_content_id(
            conn=conn,
            workflow_id=event.get("workflow_id"),
            logical_post_id=event.get("logical_post_id"),
        )
        if resolved:
            return resolved

        target_post_id = event.get("target_post_id")
        target_url = event.get("target_url")
        if target_post_id or target_url:
            matched = await conn.fetchval(
                """
                SELECT id
                FROM public.content
                WHERE metadata->>'platform_post_id' = $1
                   OR metadata->>'provider_post_id' = $1
                   OR metadata->>'post_url' = $2
                LIMIT 1
                """,
                target_post_id,
                target_url,
            )
            if matched:
                return UUID(str(matched))

        return None

    @classmethod
    async def persist_scheduled_post(
        cls,
        workflow_id: str,
        post_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        pool = await cls._get_pool()
        logical_post_id = post_config["id"]
        scheduled_at = _parse_timestamp(post_config.get("scheduled_time"))
        media_urls = [
            media.get("storage_url") or media.get("url")
            for media in post_config.get("media", [])
            if media.get("storage_url") or media.get("url")
        ]
        metadata = {
            "workflow_id": workflow_id,
            "logical_post_id": logical_post_id,
            "day": post_config.get("day"),
            "platform": post_config.get("platform"),
            "social_account_id": post_config.get("social_account_id"),
            "theme": post_config.get("theme"),
            "hashtags": post_config.get("hashtags", []),
            "cta": post_config.get("cta", ""),
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                user_uuid = await cls._ensure_user(conn, post_config["user_id"])
                existing = await conn.fetchrow(
                    """
                    SELECT id
                    FROM public.content
                    WHERE metadata->>'workflow_id' = $1
                      AND metadata->>'logical_post_id' = $2
                    LIMIT 1
                    """,
                    workflow_id,
                    logical_post_id,
                )

                title = (
                    post_config.get("title")
                    or post_config.get("theme")
                    or f"Day {post_config.get('day')} {post_config.get('platform', '').title()} post"
                )

                if existing:
                    content_id = existing["id"]
                    await conn.execute(
                        """
                        UPDATE public.content
                        SET title = $1,
                            content = $2,
                            platform = $3::text[],
                            status = $4,
                            scheduled_at = $5,
                            media_urls = $6::text[],
                            metadata = $7::jsonb
                        WHERE id = $8
                        """,
                        title,
                        post_config["content"],
                        [post_config["platform"]],
                        "scheduled" if scheduled_at else "approved",
                        scheduled_at,
                        media_urls,
                        json.dumps(metadata),
                        content_id,
                    )
                else:
                    content_id = await conn.fetchval(
                        """
                        INSERT INTO public.content (
                            user_id,
                            title,
                            content,
                            platform,
                            status,
                            scheduled_at,
                            media_urls,
                            metadata
                        )
                        VALUES ($1, $2, $3, $4::text[], $5, $6, $7::text[], $8::jsonb)
                        RETURNING id
                        """,
                        user_uuid,
                        title,
                        post_config["content"],
                        [post_config["platform"]],
                        "scheduled" if scheduled_at else "approved",
                        scheduled_at,
                        media_urls,
                        json.dumps(metadata),
                    )

                if post_config["platform"] in POSTIZ_PLATFORMS:
                    schedule_row = await conn.fetchrow(
                        """
                        SELECT id
                        FROM public.postiz_schedules
                        WHERE content_id = $1 AND platform = $2
                        LIMIT 1
                        """,
                        content_id,
                        post_config["platform"],
                    )
                    if schedule_row:
                        await conn.execute(
                            """
                            UPDATE public.postiz_schedules
                            SET scheduled_for = $1,
                                status = $2,
                                response_payload = $3::jsonb
                            WHERE id = $4
                            """,
                            scheduled_at,
                            "scheduled",
                            json.dumps({"logical_post_id": logical_post_id}),
                            schedule_row["id"],
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO public.postiz_schedules (
                                content_id,
                                platform,
                                scheduled_for,
                                status,
                                response_payload
                            )
                            VALUES ($1, $2, $3, $4, $5::jsonb)
                            """,
                            content_id,
                            post_config["platform"],
                            scheduled_at,
                            "scheduled",
                            json.dumps({"logical_post_id": logical_post_id}),
                        )

        return {"content_record_id": str(content_id), "workflow_id": workflow_id}

    @classmethod
    async def update_publish_result(
        cls,
        workflow_id: Optional[str],
        post_config: Dict[str, Any],
        publish_result: Dict[str, Any],
    ) -> None:
        pool = await cls._get_pool()
        content_id = post_config.get("content_record_id")
        logical_post_id = post_config.get("id")
        published_at = _parse_timestamp(publish_result.get("published_at")) or datetime.utcnow()
        scheduled_at = _parse_timestamp(post_config.get("scheduled_time"))
        publish_status = str(publish_result.get("status") or "failed")
        status = (
            publish_status
            if publish_status in {"scheduled", "published", "failed", "canceled"}
            else ("published" if publish_status == "success" else "failed")
        )
        metadata_patch = {
            "platform_post_id": publish_result.get("platform_post_id"),
            "provider_post_id": publish_result.get("provider_post_id"),
            "post_url": publish_result.get("post_url"),
            "publish_method": publish_result.get("method"),
            "social_account_id": post_config.get("social_account_id"),
            "provider_status": publish_result.get("provider_status"),
            "publish_error": publish_result.get("error"),
            "last_publish_result_status": status,
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                content_id = await cls._resolve_content_id(
                    conn=conn,
                    workflow_id=workflow_id,
                    logical_post_id=logical_post_id,
                    content_id=content_id,
                )

                if not content_id:
                    return

                await conn.execute(
                    """
                    UPDATE public.content
                    SET status = $1,
                        scheduled_at = CASE
                            WHEN $1 = 'scheduled' AND $2 IS NOT NULL THEN $2
                            ELSE scheduled_at
                        END,
                        published_at = CASE
                            WHEN $1 = 'published' THEN $3
                            ELSE published_at
                        END,
                        metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                    WHERE id = $5
                    """,
                    status,
                    scheduled_at,
                    published_at,
                    json.dumps(metadata_patch),
                    content_id,
                )

                if post_config.get("platform") in POSTIZ_PLATFORMS:
                    existing_schedule_id = await conn.fetchval(
                        """
                        SELECT id
                        FROM public.postiz_schedules
                        WHERE content_id = $1 AND platform = $2
                        LIMIT 1
                        """,
                        content_id,
                        post_config.get("platform"),
                    )
                    schedule_payload = publish_result.get("provider_response") or publish_result
                    provider_post_id = (
                        publish_result.get("provider_post_id")
                        or publish_result.get("platform_post_id")
                    )
                    if existing_schedule_id:
                        await conn.execute(
                            """
                            UPDATE public.postiz_schedules
                            SET postiz_post_id = $1,
                                scheduled_for = COALESCE($2, scheduled_for),
                                status = $3,
                                response_payload = $4::jsonb
                            WHERE id = $5
                            """,
                            provider_post_id,
                            scheduled_at,
                            status,
                            json.dumps(schedule_payload),
                            existing_schedule_id,
                        )
                    else:
                        await conn.execute(
                            """
                            INSERT INTO public.postiz_schedules (
                                content_id,
                                platform,
                                postiz_post_id,
                                scheduled_for,
                                status,
                                response_payload
                            )
                            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                            """,
                            content_id,
                            post_config.get("platform"),
                            provider_post_id,
                            scheduled_at,
                            status,
                            json.dumps(schedule_payload),
                        )

    @classmethod
    async def record_engagement_result(
        cls,
        workflow_id: Optional[str],
        post_data: Dict[str, Any],
        engagement_result: Dict[str, Any],
    ) -> None:
        pool = await cls._get_pool()
        logical_post_id = post_data.get("logical_post_id") or post_data.get("post_id")
        platform = post_data.get("platform") or "unknown"
        metrics = _json_loads_if_needed(engagement_result.get("metrics")) or {}
        syndicate_result = (
            _json_loads_if_needed(engagement_result.get("syndicate_result")) or {}
        )
        checked_at = datetime.utcnow()
        log_status = (
            "failed"
            if engagement_result.get("status") == "failed"
            else "completed"
        )
        post_url = (
            post_data.get("post_url")
            or syndicate_result.get("post_url")
            or (
                f"{platform}://{post_data.get('platform_post_id', '')}"
                if post_data.get("platform_post_id")
                else None
            )
        )
        target_post_id = post_data.get("platform_post_id") or post_data.get(
            "provider_post_id"
        )
        action_types = engagement_result.get("action_types") or []
        snapshot_payload = {
            "metrics": metrics,
            "engagement_rate": metrics.get("engagement_rate"),
            "syndicate_triggered": bool(engagement_result.get("syndicate_triggered")),
            "syndicate_result": syndicate_result,
            "engagement_status": engagement_result.get("status", "completed"),
            "error": engagement_result.get("error"),
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                content_id = await cls._resolve_content_id(
                    conn=conn,
                    workflow_id=workflow_id,
                    logical_post_id=logical_post_id,
                    content_id=post_data.get("content_record_id"),
                )

                if content_id:
                    await conn.execute(
                        """
                        INSERT INTO public.analytics_events (
                            content_id,
                            user_id,
                            event_type,
                            platform,
                            metadata
                        )
                        VALUES ($1, (SELECT user_id FROM public.content WHERE id = $1), $2, $3, $4::jsonb)
                        """,
                        content_id,
                        "engagement_snapshot",
                        platform,
                        json.dumps(snapshot_payload),
                    )

                    metadata_patch = {
                        "engagement_metrics": metrics,
                        "last_engagement_checked_at": checked_at.isoformat(),
                        "engagement_status": engagement_result.get(
                            "status", "completed"
                        ),
                        "engagement_error": engagement_result.get("error"),
                        "syndicate_triggered": bool(
                            engagement_result.get("syndicate_triggered")
                        ),
                        "syndicate_job_id": syndicate_result.get("job_id"),
                    }
                    if post_url:
                        metadata_patch["post_url"] = post_url

                    await conn.execute(
                        """
                        UPDATE public.content
                        SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb
                        WHERE id = $2
                        """,
                        json.dumps(metadata_patch),
                        content_id,
                    )

                await conn.execute(
                    """
                    INSERT INTO public.engagement_action_logs (
                        workflow_id,
                        platform,
                        target_post_id,
                        target_url,
                        action_types,
                        status,
                        provider_job_id,
                        result_payload,
                        error_message,
                        completed_at
                    )
                    VALUES ($1, $2, $3, $4, $5::text[], $6, $7, $8::jsonb, $9, $10)
                    """,
                    workflow_id,
                    platform,
                    target_post_id,
                    post_url,
                    action_types,
                    log_status,
                    syndicate_result.get("job_id"),
                    json.dumps(snapshot_payload),
                    engagement_result.get("error"),
                    checked_at,
                )

    @classmethod
    async def sync_postiz_webhook(cls, event: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        status = event.get("status") or "scheduled"
        scheduled_for = _parse_timestamp(event.get("scheduled_for"))
        published_at = _parse_timestamp(event.get("published_at")) or datetime.utcnow()
        metadata_patch = {
            "platform_post_id": event.get("platform_post_id"),
            "provider_post_id": event.get("provider_post_id"),
            "post_url": event.get("post_url"),
            "provider_status": event.get("provider_status"),
            "publish_error": event.get("error"),
            "last_publish_result_status": status,
            "last_postiz_webhook_event": event.get("event_type"),
            "last_postiz_webhook_received_at": datetime.utcnow().isoformat(),
        }
        raw_payload = event.get("raw") or event
        payload_json = _json_dumps_canonical(raw_payload)

        async with pool.acquire() as conn:
            async with conn.transaction():
                content_id = await cls._resolve_content_id_for_postiz_sync(conn, event)
                if not content_id:
                    return {
                        "matched": False,
                        "status": status,
                        "provider_post_id": event.get("provider_post_id"),
                    }

                existing_schedule = await conn.fetchrow(
                    """
                    SELECT id, status, response_payload
                    FROM public.postiz_schedules
                    WHERE content_id = $1
                      AND (
                        platform = $2
                        OR postiz_post_id = $3
                        OR postiz_post_id = $4
                      )
                    ORDER BY updated_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    content_id,
                    event.get("platform"),
                    event.get("provider_post_id"),
                    event.get("platform_post_id"),
                )
                duplicate = (
                    existing_schedule is not None
                    and existing_schedule["status"] == status
                    and _json_dumps_canonical(existing_schedule["response_payload"])
                    == payload_json
                )

                await conn.execute(
                    """
                    UPDATE public.content
                    SET status = CASE
                            WHEN $1 IN ('scheduled', 'published', 'failed', 'canceled')
                                THEN $1
                            ELSE status
                        END,
                        scheduled_at = CASE
                            WHEN $1 = 'scheduled' AND $2 IS NOT NULL THEN $2
                            ELSE scheduled_at
                        END,
                        published_at = CASE
                            WHEN $1 = 'published' THEN COALESCE($3, published_at)
                            ELSE published_at
                        END,
                        metadata = COALESCE(metadata, '{}'::jsonb) || $4::jsonb
                    WHERE id = $5
                    """,
                    status,
                    scheduled_for,
                    published_at,
                    json.dumps(metadata_patch),
                    content_id,
                )

                if existing_schedule:
                    await conn.execute(
                        """
                        UPDATE public.postiz_schedules
                        SET postiz_post_id = COALESCE($1, postiz_post_id),
                            scheduled_for = COALESCE($2, scheduled_for),
                            status = $3,
                            response_payload = $4::jsonb
                        WHERE id = $5
                        """,
                        event.get("provider_post_id") or event.get("platform_post_id"),
                        scheduled_for,
                        status,
                        json.dumps(raw_payload),
                        existing_schedule["id"],
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO public.postiz_schedules (
                            content_id,
                            platform,
                            postiz_post_id,
                            scheduled_for,
                            status,
                            response_payload
                        )
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                        """,
                        content_id,
                        event.get("platform") or "unknown",
                        event.get("provider_post_id") or event.get("platform_post_id"),
                        scheduled_for,
                        status,
                        json.dumps(raw_payload),
                    )

                return {
                    "matched": True,
                    "duplicate": duplicate,
                    "content_id": str(content_id),
                    "status": status,
                    "provider_post_id": event.get("provider_post_id"),
                }

    @classmethod
    async def sync_growchief_webhook(cls, event: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        status = event.get("status") or "pending"
        raw_payload = event.get("raw") or event
        payload_json = _json_dumps_canonical(raw_payload)
        completed_at = datetime.utcnow() if status in {"completed", "failed"} else None
        metrics = _json_loads_if_needed(event.get("metrics")) or {}

        async with pool.acquire() as conn:
            async with conn.transaction():
                existing_log = None
                provider_job_id = event.get("provider_job_id")
                if provider_job_id:
                    existing_log = await conn.fetchrow(
                        """
                        SELECT id, status, result_payload
                        FROM public.engagement_action_logs
                        WHERE provider_job_id = $1
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        provider_job_id,
                    )

                if existing_log is None and event.get("workflow_id") and event.get(
                    "target_post_id"
                ):
                    existing_log = await conn.fetchrow(
                        """
                        SELECT id, status, result_payload
                        FROM public.engagement_action_logs
                        WHERE workflow_id = $1
                          AND target_post_id = $2
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        event.get("workflow_id"),
                        event.get("target_post_id"),
                    )

                duplicate = (
                    existing_log is not None
                    and existing_log["status"] == status
                    and _json_dumps_canonical(existing_log["result_payload"])
                    == payload_json
                )

                if existing_log:
                    await conn.execute(
                        """
                        UPDATE public.engagement_action_logs
                        SET workflow_id = COALESCE($1, workflow_id),
                            platform = COALESCE($2, platform),
                            target_post_id = COALESCE($3, target_post_id),
                            target_url = COALESCE($4, target_url),
                            action_types = CASE
                                WHEN array_length($5::text[], 1) IS NULL THEN action_types
                                ELSE $5::text[]
                            END,
                            status = $6,
                            provider_job_id = COALESCE($7, provider_job_id),
                            result_payload = $8::jsonb,
                            error_message = $9,
                            completed_at = COALESCE($10, completed_at)
                        WHERE id = $11
                        """,
                        event.get("workflow_id"),
                        event.get("platform"),
                        event.get("target_post_id"),
                        event.get("target_url"),
                        event.get("action_types") or [],
                        status,
                        provider_job_id,
                        json.dumps(raw_payload),
                        event.get("error"),
                        completed_at,
                        existing_log["id"],
                    )
                else:
                    await conn.execute(
                        """
                        INSERT INTO public.engagement_action_logs (
                            workflow_id,
                            platform,
                            target_post_id,
                            target_url,
                            action_types,
                            status,
                            provider_job_id,
                            result_payload,
                            error_message,
                            completed_at
                        )
                        VALUES ($1, $2, $3, $4, $5::text[], $6, $7, $8::jsonb, $9, $10)
                        """,
                        event.get("workflow_id"),
                        event.get("platform") or "unknown",
                        event.get("target_post_id"),
                        event.get("target_url"),
                        event.get("action_types") or [],
                        status,
                        provider_job_id,
                        json.dumps(raw_payload),
                        event.get("error"),
                        completed_at,
                    )

                content_id = await cls._resolve_content_id_for_growchief_sync(conn, event)
                if content_id:
                    metadata_patch = {
                        "engagement_metrics": metrics,
                        "last_engagement_checked_at": datetime.utcnow().isoformat(),
                        "engagement_status": status,
                        "engagement_error": event.get("error"),
                        "syndicate_triggered": bool(provider_job_id),
                        "syndicate_job_id": provider_job_id,
                        "last_growchief_webhook_received_at": datetime.utcnow().isoformat(),
                    }
                    if event.get("target_url"):
                        metadata_patch["post_url"] = event.get("target_url")

                    await conn.execute(
                        """
                        UPDATE public.content
                        SET metadata = COALESCE(metadata, '{}'::jsonb) || $1::jsonb
                        WHERE id = $2
                        """,
                        json.dumps(metadata_patch),
                        content_id,
                    )

                    if metrics and not duplicate:
                        analytics_payload = {
                            "metrics": metrics,
                            "engagement_rate": metrics.get("engagement_rate"),
                            "provider_job_id": provider_job_id,
                            "syndicate_status": status,
                            "target_url": event.get("target_url"),
                            "source": "growchief_webhook",
                        }
                        await conn.execute(
                            """
                            INSERT INTO public.analytics_events (
                                content_id,
                                user_id,
                                event_type,
                                platform,
                                metadata
                            )
                            VALUES ($1, (SELECT user_id FROM public.content WHERE id = $1), $2, $3, $4::jsonb)
                            """,
                            content_id,
                            "engagement_snapshot",
                            event.get("platform") or "unknown",
                            json.dumps(analytics_payload),
                        )

                return {
                    "matched": content_id is not None,
                    "duplicate": duplicate,
                    "content_id": str(content_id) if content_id else None,
                    "status": status,
                    "provider_job_id": provider_job_id,
                }

    @classmethod
    async def get_analytics_summary(cls, days: int = 30) -> Dict[str, Any]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            content_rows = await conn.fetch(
                """
                SELECT id, platform, status
                FROM public.content
                WHERE COALESCE(published_at, scheduled_at, created_at)
                    >= NOW() - make_interval(days => $1)
                """,
                days,
            )
            analytics_rows = await conn.fetch(
                """
                SELECT content_id, platform, metadata, created_at
                FROM public.analytics_events
                WHERE event_type = 'engagement_snapshot'
                  AND created_at >= NOW() - make_interval(days => $1)
                ORDER BY content_id, platform, created_at DESC
                """,
                days,
            )
            engagement_log_rows = await conn.fetch(
                """
                SELECT platform, status, provider_job_id
                FROM public.engagement_action_logs
                WHERE created_at >= NOW() - make_interval(days => $1)
                """,
                days,
            )

        summary = cls.empty_analytics_summary(days=days)
        platforms: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "posts": 0,
                "published_posts": 0,
                "scheduled_posts": 0,
                "failed_posts": 0,
                "total_engagement": 0,
                "average_engagement_rate": None,
                "tracked_posts": 0,
                "syndicate_jobs": {
                    "triggered": 0,
                    "completed": 0,
                    "failed": 0,
                },
            }
        )

        for row in content_rows:
            summary["total_posts"] += 1
            status = row["status"]
            if status == "published":
                summary["published_posts"] += 1
            elif status == "scheduled":
                summary["scheduled_posts"] += 1
            elif status == "failed":
                summary["failed_posts"] += 1

            row_platforms = list(row["platform"] or []) or ["unknown"]
            for platform in row_platforms:
                platform_summary = platforms[platform]
                platform_summary["posts"] += 1
                if status == "published":
                    platform_summary["published_posts"] += 1
                elif status == "scheduled":
                    platform_summary["scheduled_posts"] += 1
                elif status == "failed":
                    platform_summary["failed_posts"] += 1

        latest_snapshots: Dict[tuple[str, str], Dict[str, Any]] = {}
        for row in analytics_rows:
            key = (str(row["content_id"]), row["platform"])
            if key in latest_snapshots:
                continue
            latest_snapshots[key] = _json_loads_if_needed(row["metadata"]) or {}

        total_rate = 0.0
        tracked_posts = 0
        for (_, platform), snapshot in latest_snapshots.items():
            metrics = snapshot.get("metrics")
            if not isinstance(metrics, dict):
                metrics = snapshot

            engagement_total = int(round(_sum_engagement_metrics(metrics)))
            engagement_rate = _coerce_float(
                snapshot.get("engagement_rate", metrics.get("engagement_rate"))
            )

            summary["total_engagement"] += engagement_total
            tracked_posts += 1
            total_rate += engagement_rate

            platform_summary = platforms[platform]
            platform_summary["total_engagement"] += engagement_total
            platform_summary["tracked_posts"] += 1
            previous_total = platform_summary.get("_engagement_rate_total", 0.0)
            platform_summary["_engagement_rate_total"] = previous_total + engagement_rate

        for row in engagement_log_rows:
            platform = row["platform"] or "unknown"
            platform_summary = platforms[platform]
            if row["provider_job_id"]:
                summary["syndicate_jobs"]["triggered"] += 1
                platform_summary["syndicate_jobs"]["triggered"] += 1
                if row["status"] == "completed":
                    summary["syndicate_jobs"]["completed"] += 1
                    platform_summary["syndicate_jobs"]["completed"] += 1
                elif row["status"] == "failed":
                    summary["syndicate_jobs"]["failed"] += 1
                    platform_summary["syndicate_jobs"]["failed"] += 1
            elif row["status"] == "failed":
                summary["syndicate_jobs"]["failed"] += 1
                platform_summary["syndicate_jobs"]["failed"] += 1

        summary["tracked_posts"] = tracked_posts
        if tracked_posts:
            summary["average_engagement_rate"] = round(total_rate / tracked_posts, 2)

        normalized_platforms: Dict[str, Dict[str, Any]] = {}
        for platform, values in platforms.items():
            tracked = values["tracked_posts"]
            total_platform_rate = values.pop("_engagement_rate_total", 0.0)
            values["average_engagement_rate"] = (
                round(total_platform_rate / tracked, 2) if tracked else None
            )
            normalized_platforms[platform] = values

        summary["platforms"] = normalized_platforms
        return summary

    @classmethod
    async def get_retry_post_config(cls, content_id: str) -> Optional[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    content,
                    platform,
                    status,
                    scheduled_at,
                    media_urls,
                    metadata
                FROM public.content
                WHERE id = $1
                LIMIT 1
                """,
                UUID(str(content_id)),
            )

        if not row:
            return None

        metadata = _json_loads_if_needed(row["metadata"]) or {}
        platform = metadata.get("platform")
        if not platform:
            platform_values = list(row["platform"] or [])
            platform = platform_values[0] if platform_values else None

        return {
            "content_record_id": str(row["id"]),
            "id": metadata.get("logical_post_id") or str(row["id"]),
            "logical_post_id": metadata.get("logical_post_id") or str(row["id"]),
            "workflow_id": metadata.get("workflow_id"),
            "user_id": str(row["user_id"]),
            "title": row["title"],
            "content": row["content"],
            "platform": platform,
            "day": metadata.get("day"),
            "theme": metadata.get("theme"),
            "hashtags": metadata.get("hashtags", []),
            "cta": metadata.get("cta", ""),
            "scheduled_time": (
                row["scheduled_at"].isoformat() if row["scheduled_at"] else None
            ),
            "media": [
                {"storage_url": url}
                for url in list(row["media_urls"] or [])
                if url
            ],
            "status": row["status"],
            "platform_post_id": metadata.get("platform_post_id"),
            "provider_post_id": metadata.get("provider_post_id"),
            "publish_method": metadata.get("publish_method"),
            "post_url": metadata.get("post_url"),
            "publish_error": metadata.get("publish_error"),
            "engagement_metrics": metadata.get("engagement_metrics"),
            "syndicate_triggered": metadata.get("syndicate_triggered"),
            "syndicate_job_id": metadata.get("syndicate_job_id"),
        }

    @classmethod
    async def list_content_items(cls, limit: int = 20) -> List[Dict[str, Any]]:
        pool = await cls._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    title,
                    content,
                    platform,
                    status,
                    scheduled_at,
                    published_at,
                    media_urls,
                    metadata,
                    created_at,
                    updated_at
                FROM public.content
                ORDER BY COALESCE(published_at, scheduled_at, created_at) DESC, created_at DESC
                LIMIT $1
                """,
                limit,
            )

        items: List[Dict[str, Any]] = []
        for row in rows:
            metadata = _json_loads_if_needed(row["metadata"]) or {}
            items.append(
                {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "content": row["content"],
                    "platform": list(row["platform"] or []),
                    "status": row["status"],
                    "scheduledAt": (
                        row["scheduled_at"].isoformat() if row["scheduled_at"] else None
                    ),
                    "publishedAt": (
                        row["published_at"].isoformat() if row["published_at"] else None
                    ),
                    "mediaUrls": list(row["media_urls"] or []),
                    "createdAt": (
                        row["created_at"].isoformat() if row["created_at"] else None
                    ),
                    "updatedAt": (
                        row["updated_at"].isoformat() if row["updated_at"] else None
                    ),
                    "workflowId": metadata.get("workflow_id"),
                    "logicalPostId": metadata.get("logical_post_id"),
                    "currentStep": metadata.get("current_step"),
                    "approvalFeedback": metadata.get("approval_feedback", ""),
                    "platformPostId": metadata.get("platform_post_id"),
                    "providerPostId": metadata.get("provider_post_id"),
                    "postUrl": metadata.get("post_url"),
                    "publishMethod": metadata.get("publish_method"),
                    "publishError": metadata.get("publish_error"),
                    "engagementMetrics": metadata.get("engagement_metrics"),
                    "lastEngagementCheckedAt": metadata.get(
                        "last_engagement_checked_at"
                    ),
                    "syndicateTriggered": metadata.get("syndicate_triggered"),
                    "syndicateJobId": metadata.get("syndicate_job_id"),
                }
            )
        return items
