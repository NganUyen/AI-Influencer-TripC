import pytest

from api import analytics


@pytest.mark.asyncio
async def test_get_analytics_summary_uses_persistence(monkeypatch):
    async def fake_get_analytics_summary(days: int = 30):
        assert days == 30
        return {
            "total_posts": 4,
            "published_posts": 2,
            "scheduled_posts": 1,
            "failed_posts": 1,
            "total_engagement": 12,
            "average_engagement_rate": 3.4,
            "tracked_posts": 2,
            "syndicate_jobs": {"triggered": 1, "completed": 1, "failed": 0},
            "platforms": {"twitter": {"posts": 2}},
            "time_period": "30_days",
        }

    monkeypatch.setattr(
        analytics.ContentPersistenceService,
        "get_analytics_summary",
        fake_get_analytics_summary,
    )

    result = await analytics.get_analytics_summary()

    assert result["total_posts"] == 4
    assert result["average_engagement_rate"] == 3.4


@pytest.mark.asyncio
async def test_get_analytics_summary_falls_back_when_persistence_fails(monkeypatch):
    async def fake_get_analytics_summary(days: int = 30):
        raise RuntimeError("asyncpg missing")

    monkeypatch.setattr(
        analytics.ContentPersistenceService,
        "get_analytics_summary",
        fake_get_analytics_summary,
    )

    result = await analytics.get_analytics_summary()

    assert result == analytics.ContentPersistenceService.empty_analytics_summary(
        days=30
    )
