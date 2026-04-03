"""
Browser Capture Health API

Provides health check and metrics endpoints for browser capture subsystem.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

from api.security import require_internal_api_token

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


@router.get("/browser-capture")
async def browser_capture_health() -> Dict[str, Any]:
    """
    Health check for browser capture subsystem.

    Performs a test capture against a known-good URL (playwright.dev)
    and returns capture metrics and status.

    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "checked_at": "2024-01-01T00:00:00",
            "url": "https://playwright.dev",
            "duration_sec": 5.2,
            "file_size_bytes": 3500000,
            "error": null,
            "metrics_summary": { ... }
        }
    """
    try:
        from services.browser_capture_metrics import check_browser_capture_health

        result = await check_browser_capture_health()
        return result
    except Exception as e:
        logger.exception("Health check failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser-capture/metrics")
async def browser_capture_metrics() -> Dict[str, Any]:
    """
    Get browser capture metrics summary.

    Returns aggregated metrics without performing a health check.
    """
    try:
        from services.browser_capture_metrics import capture_metrics

        return capture_metrics.get_summary()
    except Exception as e:
        logger.error("Failed to get metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser-capture/metrics/prometheus")
async def browser_capture_metrics_prometheus():
    """
    Get browser capture metrics in Prometheus text format.

    Suitable for scraping by Prometheus server.
    """
    from fastapi.responses import PlainTextResponse

    try:
        from services.browser_capture_metrics import capture_metrics

        return PlainTextResponse(
            content=capture_metrics.prometheus_format(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )
    except Exception as e:
        logger.error("Failed to export Prometheus metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browser-capture/domains")
async def browser_capture_domain_stats() -> Dict[str, Any]:
    """
    Get domain-specific capture statistics.

    Shows success rates per domain to identify problematic sites.
    """
    try:
        from services.browser_capture_metrics import domain_tracker

        domains = await domain_tracker.get_all_domain_stats()

        # Sort by failure rate (highest first)
        sorted_domains = dict(
            sorted(
                domains.items(),
                key=lambda x: (x[1]["total"], 100 - x[1]["success_rate"]),
                reverse=True,
            )
        )

        return {
            "domain_count": len(sorted_domains),
            "domains": sorted_domains,
        }
    except Exception as e:
        logger.error("Failed to get domain stats: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
