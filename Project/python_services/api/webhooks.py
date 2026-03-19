"""
Provider webhook routes for Postiz and GrowChief status synchronization.
"""

from typing import Any, Dict, Optional
import secrets

from fastapi import APIRouter, HTTPException, Request

from config.settings import settings
from services import ContentPersistenceService, GrowChiefService, PostizService

router = APIRouter()


def _extract_presented_secret(request: Request, provider_name: str) -> Optional[str]:
    provider_header = request.headers.get(f"x-{provider_name}-webhook-secret")
    generic_header = request.headers.get("x-webhook-secret")
    if provider_header:
        return provider_header
    if generic_header:
        return generic_header

    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _verify_webhook_secret(
    request: Request, configured_secret: Optional[str], provider_name: str
) -> None:
    if not configured_secret:
        if settings.is_production_like:
            raise HTTPException(
                status_code=503,
                detail=f"{provider_name} webhook secret is not configured",
            )
        return

    if settings.is_placeholder_secret(configured_secret):
        raise HTTPException(
            status_code=503,
            detail=f"{provider_name} webhook secret is misconfigured",
        )

    presented_secret = _extract_presented_secret(request, provider_name)
    if not presented_secret or not secrets.compare_digest(
        presented_secret, configured_secret
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


@router.post("/postiz")
async def receive_postiz_webhook(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, Any]:
    _verify_webhook_secret(request, settings.POSTIZ_WEBHOOK_SECRET, "postiz")
    normalized_event = PostizService.normalize_webhook_event(payload)
    sync_result = await ContentPersistenceService.sync_postiz_webhook(normalized_event)
    return {
        "provider": "postiz",
        "received": True,
        **sync_result,
    }


@router.post("/growchief")
async def receive_growchief_webhook(
    request: Request, payload: Dict[str, Any]
) -> Dict[str, Any]:
    _verify_webhook_secret(request, settings.GROWCHIEF_WEBHOOK_SECRET, "growchief")
    normalized_event = GrowChiefService.normalize_webhook_event(payload)
    sync_result = await ContentPersistenceService.sync_growchief_webhook(
        normalized_event
    )
    return {
        "provider": "growchief",
        "received": True,
        **sync_result,
    }
