"""
Analytics API Routes
Endpoints for engagement metrics and performance tracking
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

from api.security import require_internal_api_token
from services import GrowChiefService, PostizService, ContentPersistenceService

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


@router.get("/engagement/{platform}/{post_id}")
async def get_engagement_metrics(platform: str, post_id: str):
    """
    Get engagement metrics for a post

    Args:
        platform: Social platform
        post_id: Post identifier
    """
    growchief = GrowChiefService()
    try:
        metrics = await growchief.get_engagement_metrics(
            platform=platform, post_id=post_id
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to get engagement metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await growchief.close()


@router.get("/post/{post_id}")
async def get_post_analytics(post_id: str):
    """Get analytics for a specific post via Postiz"""
    postiz = PostizService()
    try:
        analytics = await postiz.get_analytics(post_id)
        return analytics
    except Exception as e:
        logger.error(f"Failed to get post analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await postiz.close()


@router.get("/summary")
async def get_analytics_summary():
    """Get overall analytics summary"""
    try:
        return await ContentPersistenceService.get_analytics_summary(days=30)
    except Exception as exc:
        logger.warning("Falling back to empty analytics summary: %s", exc)
        return ContentPersistenceService.empty_analytics_summary(days=30)
