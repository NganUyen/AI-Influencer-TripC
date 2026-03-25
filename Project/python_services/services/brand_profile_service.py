"""
Customer brand profile persistence helpers.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from services.customer_auth_service import CustomerSession
from services.database_service import DatabaseService


def _normalize_brand_record(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": str(row["id"]),
        "brand_profile_id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "product_name": row["product_name"],
        "website_url": row["website_url"],
        "audience": row["audience"],
        "offer_summary": row["offer_summary"],
        "tone_voice": row["tone_voice"],
        "campaign_goals": row["campaign_goals"] or [],
        "asset_urls": row["asset_urls"] or [],
        "timezone": row["timezone"],
        "posting_cadence": row["posting_cadence"] or {},
        "approval_preferences": row["approval_preferences"] or {},
        "telegram_contact": row["telegram_contact"],
        "onboarding_status": row["onboarding_status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


class BrandProfileService:
    @classmethod
    async def get_for_user(cls, user_id: str) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM public.brand_profiles
                WHERE user_id = $1::uuid
                LIMIT 1
                """,
                user_id,
            )
        if row is None:
            return None
        return _normalize_brand_record(row)

    @classmethod
    async def upsert_for_session(
        cls,
        session: CustomerSession,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.brand_profiles (
                    user_id,
                    product_name,
                    website_url,
                    audience,
                    offer_summary,
                    tone_voice,
                    campaign_goals,
                    asset_urls,
                    timezone,
                    posting_cadence,
                    approval_preferences,
                    telegram_contact,
                    onboarding_status
                )
                VALUES (
                    $1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, $10::jsonb, $11::jsonb, $12, $13
                )
                ON CONFLICT (user_id) DO UPDATE
                SET product_name = EXCLUDED.product_name,
                    website_url = EXCLUDED.website_url,
                    audience = EXCLUDED.audience,
                    offer_summary = EXCLUDED.offer_summary,
                    tone_voice = EXCLUDED.tone_voice,
                    campaign_goals = EXCLUDED.campaign_goals,
                    asset_urls = EXCLUDED.asset_urls,
                    timezone = EXCLUDED.timezone,
                    posting_cadence = EXCLUDED.posting_cadence,
                    approval_preferences = EXCLUDED.approval_preferences,
                    telegram_contact = EXCLUDED.telegram_contact,
                    onboarding_status = EXCLUDED.onboarding_status,
                    updated_at = NOW()
                RETURNING *
                """,
                session.user_id,
                payload.get("product_name"),
                payload.get("website_url"),
                payload.get("audience"),
                payload.get("offer_summary"),
                payload.get("tone_voice"),
                json.dumps(payload.get("campaign_goals") or [], sort_keys=True),
                json.dumps(payload.get("asset_urls") or [], sort_keys=True),
                payload.get("timezone") or "UTC",
                json.dumps(payload.get("posting_cadence") or {}, sort_keys=True),
                json.dumps(
                    payload.get("approval_preferences") or {"mode": "review_first"},
                    sort_keys=True,
                ),
                payload.get("telegram_contact"),
                payload.get("onboarding_status") or "completed",
            )
        return _normalize_brand_record(row)

    @classmethod
    async def build_strategy_input(cls, user_id: str) -> Dict[str, Any]:
        brand = await cls.get_for_user(user_id)
        if not brand:
            raise ValueError("Customer has not completed brand onboarding")
        return {
            "brand_profile_id": brand["id"],
            "product_name": brand["product_name"],
            "website_url": brand["website_url"],
            "audience": brand["audience"],
            "offer_summary": brand["offer_summary"],
            "brand_voice": brand["tone_voice"],
            "campaign_goals": brand["campaign_goals"],
            "asset_urls": brand["asset_urls"],
            "timezone": brand["timezone"],
            "posting_cadence": brand["posting_cadence"],
            "approval_preferences": brand["approval_preferences"],
            "telegram_contact": brand["telegram_contact"],
        }
