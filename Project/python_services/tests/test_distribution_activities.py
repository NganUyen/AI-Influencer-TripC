import pytest

from activities import distribution_activities as da


@pytest.mark.asyncio
async def test_publish_to_platforms_uses_postiz_and_closes_services(monkeypatch):
    events = {"postiz_closed": False, "browser_closed": False}

    class StubPostiz:
        async def publish(self, **kwargs):
            assert kwargs["platform"] == "twitter"
            return {"post_id": "postiz-1"}

        async def close(self):
            events["postiz_closed"] = True

    class StubBrowser:
        async def publish(self, **kwargs):
            return {"post_id": "browser-1"}

        async def close(self):
            events["browser_closed"] = True

    monkeypatch.setattr(da, "PostizService", StubPostiz)
    monkeypatch.setattr(da, "BrowserAutomationService", StubBrowser)

    result = await da.publish_to_platforms(
        {
            "id": "post-1",
            "platform": "twitter",
            "content": "test",
            "media": [{"storage_url": "https://cdn.example/x.jpg"}],
            "user_id": "user-1",
        }
    )

    assert result["status"] == "published"
    assert result["method"] == "postiz_oauth"
    assert result["platform_post_id"] == "postiz-1"
    assert events["postiz_closed"] is True
    assert events["browser_closed"] is True


@pytest.mark.asyncio
async def test_publish_to_platforms_handles_failure(monkeypatch):
    class StubPostiz:
        async def publish(self, **_kwargs):
            raise RuntimeError("publish failed")

        async def close(self):
            return None

    class StubBrowser:
        async def close(self):
            return None

    monkeypatch.setattr(da, "PostizService", StubPostiz)
    monkeypatch.setattr(da, "BrowserAutomationService", StubBrowser)

    result = await da.publish_to_platforms(
        {
            "id": "post-2",
            "platform": "twitter",
            "content": "test",
            "media": [],
            "user_id": "user-1",
        }
    )

    assert result["status"] == "failed"
    assert "publish failed" in result["error"]


@pytest.mark.asyncio
async def test_track_engagement_triggers_syndicate_below_threshold(monkeypatch):
    class StubGrowchief:
        async def get_engagement_metrics(self, **_kwargs):
            return {"engagement_rate": 0.5}

        async def trigger_engagement(self, **kwargs):
            assert kwargs["platform"] == "twitter"
            return {"job_id": "job-1"}

        async def close(self):
            return None

    monkeypatch.setattr(da, "GrowChiefService", StubGrowchief)
    monkeypatch.setattr(da.settings, "SYNDICATE_ENGAGEMENT_THRESHOLD", 2.0)
    monkeypatch.setattr(da.settings, "STEALTH_ACCOUNT_COUNT", 5)

    result = await da.track_engagement(
        {
            "platform": "twitter",
            "platform_post_id": "post-1",
            "post_url": "https://twitter.com/post/1",
        }
    )

    assert result["syndicate_triggered"] is True
    assert result["syndicate_result"]["job_id"] == "job-1"


@pytest.mark.asyncio
async def test_track_engagement_no_syndicate_above_threshold(monkeypatch):
    class StubGrowchief:
        async def get_engagement_metrics(self, **_kwargs):
            return {"engagement_rate": 5.0}

        async def close(self):
            return None

    monkeypatch.setattr(da, "GrowChiefService", StubGrowchief)
    monkeypatch.setattr(da.settings, "SYNDICATE_ENGAGEMENT_THRESHOLD", 2.0)

    result = await da.track_engagement(
        {
            "platform": "twitter",
            "platform_post_id": "post-1",
            "post_url": "https://twitter.com/post/1",
        }
    )

    assert result["syndicate_triggered"] is False
