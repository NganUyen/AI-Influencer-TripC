"""
Quota API routes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.security import require_internal_api_token
from services.quota_monitor_service import QuotaMonitorService

router = APIRouter(dependencies=[Depends(require_internal_api_token)])


class QuotaSnapshotCreate(BaseModel):
    provider: str
    usage: Dict[str, Any] = Field(default_factory=dict)
    cost_usd: Optional[float] = None
    quota: Dict[str, Any] = Field(default_factory=dict)
    observed_at: Optional[datetime] = None
    source: str = "manual"
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.get("/providers")
async def get_provider_overview(days: int = 30) -> Dict[str, Any]:
    return await QuotaMonitorService.get_provider_overview(days=days)


@router.get("/providers/{provider}")
async def get_provider_detail(provider: str, days: int = 30) -> Dict[str, Any]:
    try:
        return await QuotaMonitorService.get_provider_detail(provider, days=days)
    except KeyError as exc:
        detail = exc.args[0] if exc.args else str(exc)
        raise HTTPException(status_code=404, detail=detail)


@router.get("/summary")
async def get_quota_summary(days: int = 30) -> Dict[str, Any]:
    return await QuotaMonitorService.get_summary(days=days)


@router.get("/snapshots")
async def list_quota_snapshots(
    provider: Optional[str] = None,
    limit: int = 100,
    days: int = 30,
) -> Dict[str, List[Dict[str, Any]]]:
    items = await QuotaMonitorService.list_snapshots(
        provider=provider, limit=limit, days=days
    )
    return {"items": items}


@router.post("/snapshots")
async def create_quota_snapshot(payload: QuotaSnapshotCreate) -> Dict[str, Any]:
    return await QuotaMonitorService.record_snapshot(
        provider=payload.provider,
        usage=payload.usage,
        cost_usd=payload.cost_usd,
        quota=payload.quota,
        source=payload.source,
        observed_at=payload.observed_at,
        metadata=payload.metadata,
    )
