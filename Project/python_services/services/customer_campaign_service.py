"""
Customer campaign planning and launch helpers.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from temporalio.client import Client

from config.settings import settings
from services.account_connection_service import AccountConnectionService
from services.brand_profile_service import BrandProfileService
from services.customer_auth_service import CustomerSession
from services.database_service import DatabaseService
from services.workflow_state_service import WorkflowStateService
from workflows import WeeklyMarketingWorkflow


def _normalize_campaign(row: Any) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "brand_profile_id": str(row["brand_profile_id"]) if row["brand_profile_id"] else None,
        "plan_status": row["plan_status"],
        "approval_status": row["approval_status"],
        "approval_feedback": row["approval_feedback"],
        "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None,
        "launched_at": row["launched_at"].isoformat() if row["launched_at"] else None,
        "active_workflow_id": row["active_workflow_id"],
        "target_platforms": row["target_platforms"] or [],
        "connected_account_ids": [str(item) for item in (row["connected_account_ids"] or [])],
        "plan_data": row["plan_data"] or {},
        "artifact_summary": row["artifact_summary"] or {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


class CustomerCampaignService:
    @classmethod
    async def list_campaigns(cls, user_id: str) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM public.campaigns
                WHERE user_id = $1::uuid
                ORDER BY updated_at DESC, created_at DESC
                """,
                user_id,
            )
        return [_normalize_campaign(row) for row in rows]

    @classmethod
    async def create_campaign(
        cls,
        session: CustomerSession,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        brand = await BrandProfileService.get_for_user(session.user_id)
        if not brand:
            raise ValueError("Complete brand onboarding before creating a campaign")

        start_date = payload.get("start_date")
        end_date = payload.get("end_date")
        if start_date:
            start_dt = datetime.fromisoformat(str(start_date).replace("Z", "+00:00"))
        else:
            start_dt = datetime.now(timezone.utc)
        end_dt = (
            datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
            if end_date
            else start_dt + timedelta(days=7)
        )

        connected_account_ids = payload.get("connected_account_ids") or []
        target_platforms = payload.get("target_platforms") or []
        if not target_platforms:
            target_platforms = list(
                dict.fromkeys(
                    account["platform"]
                    for account in await AccountConnectionService.list_accounts(
                        session.user_id
                    )
                    if account["connection_status"] == "connected"
                )
            )

        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.campaigns (
                    user_id,
                    name,
                    description,
                    status,
                    start_date,
                    end_date,
                    brand_profile_id,
                    plan_status,
                    approval_status,
                    target_platforms,
                    connected_account_ids,
                    plan_data,
                    artifact_summary
                )
                VALUES (
                    $1::uuid, $2, $3, 'draft', $4, $5, $6::uuid, 'draft', 'pending',
                    $7::text[], $8::uuid[], $9::jsonb, $10::jsonb
                )
                RETURNING *
                """,
                session.user_id,
                payload.get("name") or "New Campaign",
                payload.get("description"),
                start_dt,
                end_dt,
                brand["id"],
                target_platforms,
                connected_account_ids,
                json.dumps(
                    {
                        "content_pillars": payload.get("content_pillars") or [],
                        "cta_rules": payload.get("cta_rules") or {},
                        "execution_windows": payload.get("execution_windows") or {},
                        "approval_mode": "review_first",
                    },
                    sort_keys=True,
                ),
                json.dumps(
                    {
                        "source_thread_id": payload.get("source_thread_id"),
                        "source_artifact_id": payload.get("source_artifact_id"),
                    },
                    sort_keys=True,
                ),
            )
        return _normalize_campaign(row)

    @classmethod
    async def approve_campaign(
        cls,
        session: CustomerSession,
        campaign_id: str,
        approved: bool,
        feedback: str = "",
    ) -> Dict[str, Any]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE public.campaigns
                SET approval_status = $3,
                    approval_feedback = $4,
                    approved_at = CASE WHEN $3 = 'approved' THEN NOW() ELSE NULL END,
                    plan_status = CASE WHEN $3 = 'approved' THEN 'approved' ELSE 'draft' END,
                    status = CASE WHEN $3 = 'approved' THEN 'ready_for_review' ELSE 'draft' END,
                    updated_at = NOW()
                WHERE id = $1::uuid
                  AND user_id = $2::uuid
                RETURNING *
                """,
                campaign_id,
                session.user_id,
                "approved" if approved else "rejected",
                feedback,
            )
        if row is None:
            raise ValueError("Campaign not found")
        return _normalize_campaign(row)

    @classmethod
    async def list_pending_approvals(cls, user_id: str) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM public.campaigns
                WHERE user_id = $1::uuid
                  AND approval_status = 'pending'
                ORDER BY created_at DESC
                """,
                user_id,
            )
        return [_normalize_campaign(row) for row in rows]

    @classmethod
    async def launch_campaign(
        cls,
        session: CustomerSession,
        campaign_id: str,
    ) -> Dict[str, Any]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM public.campaigns
                WHERE id = $1::uuid
                  AND user_id = $2::uuid
                LIMIT 1
                """,
                campaign_id,
                session.user_id,
            )
        if row is None:
            raise ValueError("Campaign not found")

        campaign = _normalize_campaign(row)
        if campaign["approval_status"] != "approved":
            raise ValueError("Campaign must be approved before launch")

        brand = await BrandProfileService.build_strategy_input(session.user_id)
        connected_accounts = await AccountConnectionService.list_accounts(session.user_id)
        selected_accounts = [
            account for account in connected_accounts if not campaign["connected_account_ids"] or account["id"] in campaign["connected_account_ids"]
        ]
        if not selected_accounts:
            raise ValueError("Connect at least one social account before launch")

        workflow_id = f"weekly-marketing-{session.user_id}-{campaign_id[:8]}-{uuid4().hex[:6]}"
        client = await Client.connect(
            settings.temporal_connection_address,
            namespace=settings.TEMPORAL_NAMESPACE,
        )
        brand_config = {
            **brand,
            "campaign_id": campaign_id,
            "campaign_name": campaign["name"],
            "campaign_description": campaign["description"],
            "platforms": campaign["target_platforms"],
            "connected_accounts": selected_accounts,
            "campaign_plan": campaign["plan_data"],
            "approval_channel": "web_app",
            "skip_internal_approval": True,
            "review_first_approved": True,
        }
        handle = await client.start_workflow(
            WeeklyMarketingWorkflow.run,
            args=[session.user_id, brand_config],
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            execution_timeout=timedelta(days=8),
        )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE public.campaigns
                    SET status = 'active',
                        plan_status = 'launched',
                        launched_at = NOW(),
                        active_workflow_id = $3,
                        updated_at = NOW()
                    WHERE id = $1::uuid
                      AND user_id = $2::uuid
                    """,
                    campaign_id,
                    session.user_id,
                    workflow_id,
                )
        await WorkflowStateService.record_started(
            workflow_id=workflow_id,
            user_id=session.user_id,
            workflow_type="weekly_marketing",
            status="running",
            current_step="launch_requested",
            progress=5,
            channel="web_app",
            input_data={
                "campaign_id": campaign_id,
                "brand_profile_id": brand["brand_profile_id"],
                "campaign_name": campaign["name"],
                "target_platforms": campaign["target_platforms"],
                "connected_account_ids": campaign["connected_account_ids"],
            },
        )

        return {
            "campaign_id": campaign_id,
            "workflow_id": workflow_id,
            "run_id": handle.id,
            "status": "launched",
        }
