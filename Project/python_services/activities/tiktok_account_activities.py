"""
Temporal activities for TikTok account bootstrap and session refresh.
"""

from __future__ import annotations

from typing import Any, Dict

from temporalio import activity

from services.tiktok_automation_service import TikTokAutomationService


@activity.defn
async def bootstrap_tiktok_account(payload: Dict[str, Any]) -> Dict[str, Any]:
    service = TikTokAutomationService()
    return await service.bootstrap_account(payload)


@activity.defn
async def refresh_tiktok_account_session(payload: Dict[str, Any]) -> Dict[str, Any]:
    service = TikTokAutomationService()
    return await service.refresh_account_session(payload)
