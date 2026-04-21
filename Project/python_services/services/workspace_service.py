"""
Aggregated customer workspace read model.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, List, Optional

from config.settings import settings
from services.account_connection_service import AccountConnectionService
from services.assistant_service import AssistantService
from services.approval_state_service import ApprovalStateService
from services.brand_profile_service import BrandProfileService
from services.customer_ai_backbone_service import CustomerAIBackboneService
from services.customer_campaign_service import CustomerCampaignService
from services.customer_media_service import CustomerMediaService
from services.database_service import DatabaseService
from services.persona_registry_service import PersonaRegistryService
from services.quota_monitor_service import QuotaMonitorService
from services.system_persona_account_links_service import (
    SystemPersonaAccountLinksService,
)
from services.telegram_link_service import TelegramLinkService
from services.workflow_state_service import WorkflowStateService


class WorkspaceService:
    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _normalize_quota_items(cls, raw_quota: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_quota, Mapping):
            raw_items: List[Any] = [
                {"provider": provider, **item}
                if isinstance(item, Mapping)
                else {"provider": provider, "label": provider, "name": provider, "raw_value": item}
                for provider, item in raw_quota.items()
            ]
        elif isinstance(raw_quota, list):
            raw_items = raw_quota
        else:
            raw_items = []

        quota_list: List[Dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, Mapping):
                usage = item.get("usage") if isinstance(item.get("usage"), Mapping) else {}
                unit = str(item.get("usage_unit") or item.get("unit") or "units")
                name = str(
                    item.get("label")
                    or item.get("name")
                    or item.get("provider")
                    or "Unknown"
                )
                used = cls._coerce_float(
                    item.get("usage_value")
                    if item.get("usage_value") is not None
                    else usage.get(unit),
                    cls._coerce_float(item.get("used"), 0.0),
                )
                total = cls._coerce_float(
                    item.get("remaining_limit")
                    or item.get("monthly_limit")
                    or item.get("limit")
                    or item.get("total"),
                    100.0,
                )
                quota_list.append(
                    {
                        "provider": item.get("provider"),
                        "name": name,
                        "used": used,
                        "total": total,
                        "unit": unit,
                        "status": item.get("status"),
                        "usage_percent": item.get("usage_percent"),
                        "remaining": item.get("remaining_value"),
                        "remaining_unit": item.get("remaining_unit"),
                        "remaining_exact": item.get("remaining_exact"),
                        "remaining_source": item.get("remaining_source"),
                        "remaining_message": item.get("remaining_message"),
                        "reset_at": item.get("remaining_reset_at") or item.get("reset_at"),
                        "observed_at": item.get("remaining_observed_at") or item.get("observed_at"),
                        "billing_type": item.get("billing_type"),
                        "warn_at_percent": item.get("warn_at_percent"),
                        "snapshot_count": item.get("snapshot_count"),
                        "cost_usd": item.get("cost_usd"),
                        "requests_remaining": item.get("remaining_requests"),
                        "requests_limit": item.get("remaining_requests_limit"),
                        "requests_reset_at": item.get("remaining_requests_reset_at"),
                        "last_error": item.get("last_error"),
                        "last_error_type": item.get("last_error_type"),
                        "telemetry_scope": item.get("telemetry_scope"),
                    }
                )
                continue

            name = str(item or "").strip()
            if not name:
                continue
            quota_list.append(
                {
                    "provider": None,
                    "name": name,
                    "used": 0.0,
                    "total": 100.0,
                    "unit": "units",
                }
            )

        return quota_list

    @staticmethod
    def _workflow_display_payload(item: Dict[str, Any]) -> Dict[str, Any]:
        progress = int(item.get("progress") or 0)
        status = str(item.get("status") or "idle")
        if progress <= 0 and status in {"completed", "approved", "save"}:
            progress = 100
        return {
            "id": item.get("workflow_id"),
            "workflow_id": item.get("workflow_id"),
            "name": item.get("type") or item.get("workflow_id") or "workflow",
            "status": status,
            "progress": progress,
            "current_step": item.get("current_step"),
            "channel": item.get("channel"),
            "approval_status": item.get("approval_status"),
            "updated_at": item.get("updated_at"),
        }

    @staticmethod
    async def list_content(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 100), 100))
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, title, content, status, platform, scheduled_at, published_at, metadata, created_at, updated_at
                FROM public.content
                WHERE user_id = $1::uuid
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT $2
                """,
                user_id,
                normalized_limit,
            )
        import json
        items = []
        for row in rows:
            raw_metadata = row["metadata"]
            if isinstance(raw_metadata, str):
                try:
                    metadata = json.loads(raw_metadata)
                except Exception:
                    metadata = {}
            else:
                metadata = raw_metadata or {}

            items.append(
                {
                    "id": str(row["id"]),
                    "title": row["title"],
                    "content": row["content"],
                    "status": row["status"],
                    "platform": row["platform"] or [],
                    "scheduled_at": row["scheduled_at"].isoformat()
                    if row["scheduled_at"]
                    else None,
                    "published_at": row["published_at"].isoformat()
                    if row["published_at"]
                    else None,
                    "metadata": metadata,
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                    "updated_at": row["updated_at"].isoformat()
                    if row["updated_at"]
                    else None,
                }
            )
        return items

    @classmethod
    async def get_system_summary(
        cls,
        *,
        user_id: str,
        temporal_client: Any | None = None,
    ) -> Dict[str, Any]:
        try:
            try:
                summary_data = await QuotaMonitorService.get_summary(
                    days=0,
                    user_id=user_id,
                )
                raw_quota = summary_data.get("providers", [])
            except Exception:
                raw_quota = []

            quota_list = cls._normalize_quota_items(raw_quota)

            services = [
                {
                    "name": "Temporal Cluster",
                    "status": "online" if temporal_client else "error",
                    "latency": "12ms",
                },
                {
                    "name": "OpenClaw AI",
                    "status": "online" if settings.OPENCLAW_API_URL else "warning",
                    "latency": "450ms",
                },
                {
                    "name": "Postiz Publisher",
                    "status": "online" if settings.POSTIZ_API_URL else "warning",
                    "latency": "80ms",
                },
                {
                    "name": "GrowChief Growth",
                    "status": "online" if settings.GROWCHIEF_API_URL else "warning",
                    "latency": "120ms",
                },
            ]

            recent_videos = await CustomerMediaService.list_recent_assets(
                user_id=user_id,
                asset_type="video",
                limit=5,
            )

            return {
                "quota": quota_list,
                "services": services,
                "recent_videos": recent_videos,
                "status": "healthy" if temporal_client else "degraded",
                "telegram_bot_url": None,
            }
        except Exception as exc:
            return {
                "quota": [],
                "services": [
                    {"name": "System Status", "status": "error", "latency": "0ms"}
                ],
                "recent_videos": [],
                "status": "error",
                "detail": str(exc),
                "telegram_bot_url": None,
            }

    @classmethod
    async def get_workflow_summary(
        cls,
        *,
        user_id: str,
        temporal_client: Any | None = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        workflows = await WorkflowStateService.list_for_user(user_id=user_id, limit=limit)
        return {
            "workflows": [cls._workflow_display_payload(item) for item in workflows],
            "status": "ok" if workflows or temporal_client else "empty",
        }

    @classmethod
    async def get_workspace(
        cls,
        *,
        user_id: str,
        customer: Optional[Dict[str, Any]] = None,
        temporal_client: Any | None = None,
    ) -> Dict[str, Any]:
        brand = await BrandProfileService.get_for_user(user_id)
        social_accounts = await AccountConnectionService.list_accounts(user_id)
        assistant_threads = await AssistantService.list_threads(user_id)
        campaigns = await CustomerCampaignService.list_campaigns(user_id)
        approvals = await CustomerCampaignService.list_pending_approvals(user_id)
        approval_requests = await ApprovalStateService.list_for_approver(
            approver_id=user_id,
            limit=10,
        )
        content = await cls.list_content(user_id)
        ai_backbone = await CustomerAIBackboneService.get_for_user(user_id)
        personas = await PersonaRegistryService.list_personas(user_id=user_id)
        if not personas:
            # Keep workspace stable when persona tables are missing/outdated:
            # fall back to built-in preset personas used by review-engine setup.
            from services.app_review_studio_service import AppReviewStudioService

            personas = list(AppReviewStudioService.preset_persona_map().values())
        personas = await SystemPersonaAccountLinksService.apply_tiktok_links_to_personas(
            personas
        )
        telegram_link = {
            "linked": False,
            "link": None,
        }
        link = await TelegramLinkService.get_link_for_user(user_id)
        if link is not None:
            telegram_link = {"linked": True, "link": link}

        system_summary = await cls.get_system_summary(
            user_id=user_id,
            temporal_client=temporal_client,
        )
        workflow_summary = await cls.get_workflow_summary(
            user_id=user_id,
            temporal_client=temporal_client,
        )

        return {
            "customer": customer or {},
            "brand": brand,
            "social_accounts": social_accounts,
            "assistant_threads": assistant_threads,
            "campaigns": campaigns,
            "approvals": approvals,
            "approval_requests": approval_requests,
            "content": content,
            "ai_backbone": ai_backbone,
            "personas": personas,
            "telegram_link": telegram_link,
            "system_summary": system_summary,
            "workflow_summary": workflow_summary,
        }
