"""
Shared authentication guards for the internal FastAPI surface.
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException

from config.settings import settings


def _normalize_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _extract_presented_token(
    authorization: Optional[str],
    x_internal_api_token: Optional[str],
) -> Optional[str]:
    if x_internal_api_token:
        return _normalize_token(x_internal_api_token)

    normalized_authorization = _normalize_token(authorization)
    if not normalized_authorization:
        return None

    if normalized_authorization.lower().startswith("bearer "):
        return _normalize_token(normalized_authorization.split(" ", 1)[1])

    return normalized_authorization


async def require_internal_api_token(
    authorization: Optional[str] = Header(default=None),
    x_internal_api_token: Optional[str] = Header(
        default=None,
        alias="x-internal-api-token",
    ),
) -> None:
    configured_token = _normalize_token(settings.INTERNAL_API_TOKEN)
    if not configured_token:
        if settings.is_production_like:
            raise HTTPException(
                status_code=503,
                detail="Internal API authentication is not configured",
            )
        return

    if settings.is_placeholder_secret(configured_token):
        raise HTTPException(
            status_code=503,
            detail="Internal API authentication is misconfigured",
        )

    presented_token = _extract_presented_token(
        authorization=authorization,
        x_internal_api_token=x_internal_api_token,
    )
    if not presented_token or not secrets.compare_digest(
        presented_token,
        configured_token,
    ):
        raise HTTPException(status_code=401, detail="Invalid internal API token")
