import pytest

from activities import distribution_activities as da


@pytest.fixture(autouse=True)
def stub_content_persistence(monkeypatch):
    async def fake_persist_scheduled_post(*_args, **_kwargs):
        return {"content_record_id": "content-1", "workflow_id": "wf-1"}

    async def fake_update_publish_result(*_args, **_kwargs):
        return None

    async def fake_record_engagement_result(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        da.ContentPersistenceService,
        "persist_scheduled_post",
        fake_persist_scheduled_post,
    )
    monkeypatch.setattr(
        da.ContentPersistenceService,
        "update_publish_result",
        fake_update_publish_result,
    )
    monkeypatch.setattr(
        da.ContentPersistenceService,
        "record_engagement_result",
        fake_record_engagement_result,
    )


@pytest.mark.asyncio
async def test_publish_to_platforms_uses_postiz_and_closes_services(monkeypatch):
    events = {"postiz_closed": False, "browser_closed": False}

    class StubPostiz:
        async def publish(self, **kwargs):
            assert kwargs["platform"] == "twitter"
            assert kwargs["scheduled_time"] is None
            return {
                "platform_post_id": "postiz-1",
                "provider_post_id": "provider-1",
                "post_url": "https://twitter.com/post/1",
                "status": "published",
                "raw": {"id": "provider-1"},
            }

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
            "scheduled_time": "2026-03-01T00:00:00Z",
            "media": [{"storage_url": "https://cdn.example/x.jpg"}],
            "user_id": "user-1",
            "content_record_id": "content-1",
            "workflow_id": "wf-1",
        }
    )

    assert result["status"] == "published"
    assert result["method"] == "postiz_oauth"
    assert result["platform_post_id"] == "postiz-1"
    assert result["provider_post_id"] == "provider-1"
    assert result["post_url"] == "https://twitter.com/post/1"
    assert result["content_record_id"] == "content-1"
    assert events["postiz_closed"] is True
    assert events["browser_closed"] is True


@pytest.mark.asyncio
async def test_publish_to_platforms_preserves_future_schedule_for_postiz(monkeypatch):
    captured = {}

    class StubPostiz:
        async def publish(self, **kwargs):
            captured.update(kwargs)
            return {
                "platform_post_id": "postiz-2",
                "provider_post_id": "provider-2",
                "status": "scheduled",
                "raw": {"id": "provider-2"},
            }

        async def close(self):
            return None

    class StubBrowser:
        async def close(self):
            return None

    monkeypatch.setattr(da, "PostizService", StubPostiz)
    monkeypatch.setattr(da, "BrowserAutomationService", StubBrowser)

    result = await da.publish_to_platforms(
        {
            "id": "post-future",
            "platform": "twitter",
            "content": "test",
            "scheduled_time": "2099-03-01T00:00:00Z",
            "media": [],
            "user_id": "user-1",
        }
    )

    assert captured["scheduled_time"] == "2099-03-01T00:00:00+00:00"
    assert result["status"] == "scheduled"
    assert result["published_at"] is None


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

    assert result["status"] == "completed"
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

    assert result["status"] == "completed"
    assert result["syndicate_triggered"] is False


@pytest.mark.asyncio
async def test_track_engagement_returns_failed_state_and_persists(monkeypatch):
    recorded = {}

    async def fake_record_engagement_result(**kwargs):
        recorded.update(kwargs)

    class StubGrowchief:
        async def get_engagement_metrics(self, **_kwargs):
            raise RuntimeError("metrics unavailable")

        async def close(self):
            return None

    monkeypatch.setattr(da, "GrowChiefService", StubGrowchief)
    monkeypatch.setattr(
        da.ContentPersistenceService,
        "record_engagement_result",
        fake_record_engagement_result,
    )

    result = await da.track_engagement(
        {
            "post_id": "post-1",
            "workflow_id": "wf-1",
            "platform": "twitter",
            "platform_post_id": "post-1",
        }
    )

    assert result["status"] == "failed"
    assert "metrics unavailable" in result["error"]
    assert recorded["workflow_id"] == "wf-1"
    assert recorded["engagement_result"]["status"] == "failed"
