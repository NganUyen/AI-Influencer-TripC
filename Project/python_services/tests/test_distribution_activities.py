import pytest
from temporalio.exceptions import ApplicationError

from activities import distribution_activities as da
from services.errors import GrowChiefAuthError, PostizRetryableError


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
    events = {"publisher_closed": False, "browser_closed": False}

    class StubPublisher:
        async def publish(self, post_config):
            assert post_config["platform"] == "twitter"
            assert post_config["scheduled_time"] is None
            return {
                "platform_post_id": "postiz-1",
                "provider_post_id": "provider-1",
                "post_url": "https://twitter.com/post/1",
                "status": "published",
                "raw": {"id": "provider-1"},
            }

        async def close(self):
            events["publisher_closed"] = True

    class StubBrowser:
        async def publish(self, **kwargs):
            return {"post_id": "browser-1"}

        async def close(self):
            events["browser_closed"] = True

    monkeypatch.setattr(da, "PublisherService", StubPublisher)
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
    assert events["publisher_closed"] is True
    assert events["browser_closed"] is True


@pytest.mark.asyncio
async def test_publish_to_platforms_routes_tiktok_to_browser_automation_strategy(
    monkeypatch,
):
    events = {"browser_closed": False}

    class StubPublisher:
        async def publish(self, _post_config):
            raise AssertionError("PublisherService should not handle TikTok here")

        async def close(self):
            return None

    class StubTikTok:
        async def publish_post(self, post_config):
            assert post_config["platform"] == "tiktok"
            return {
                "status": "published",
                "method": "tiktok_browser_automation",
                "raw": {"account_handle": "creator-1"},
            }

    class StubBrowser:
        async def publish(self, **_kwargs):
            raise AssertionError("Generic browser automation should not handle TikTok")

        async def close(self):
            events["browser_closed"] = True

    monkeypatch.setattr(da, "PublisherService", StubPublisher)
    monkeypatch.setattr(da, "TikTokAutomationService", StubTikTok)
    monkeypatch.setattr(da, "BrowserAutomationService", StubBrowser)

    result = await da.publish_to_platforms(
        {
            "id": "post-tiktok-1",
            "platform": "tiktok",
            "content": "test",
            "media": [{"storage_url": "https://cdn.example/video.mp4"}],
            "user_id": "user-1",
        }
    )

    assert result["status"] == "published"
    assert result["method"] == "tiktok_browser_automation"
    assert result["provider_response"]["account_handle"] == "creator-1"
    assert events["browser_closed"] is True


@pytest.mark.asyncio
async def test_publish_to_platforms_preserves_future_schedule_for_postiz(monkeypatch):
    captured = {}

    class StubPublisher:
        async def publish(self, post_config):
            captured.update(post_config)
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

    monkeypatch.setattr(da, "PublisherService", StubPublisher)
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
async def test_publish_to_platforms_raises_application_error_for_unexpected_failure(
    monkeypatch,
):
    recorded = {}

    async def fake_update_publish_result(**kwargs):
        recorded.update(kwargs)

    class StubPublisher:
        async def publish(self, _post_config):
            raise RuntimeError("publish failed")

        async def close(self):
            return None

    class StubBrowser:
        async def close(self):
            return None

    monkeypatch.setattr(da, "PublisherService", StubPublisher)
    monkeypatch.setattr(da, "BrowserAutomationService", StubBrowser)
    monkeypatch.setattr(
        da.ContentPersistenceService,
        "update_publish_result",
        fake_update_publish_result,
    )

    with pytest.raises(ApplicationError) as exc_info:
        await da.publish_to_platforms(
            {
                "id": "post-2",
                "platform": "twitter",
                "content": "test",
                "media": [],
                "user_id": "user-1",
                "workflow_id": "wf-2",
            }
        )

    assert exc_info.value.non_retryable is False
    assert recorded["publish_result"]["status"] == "failed"
    assert "publish failed" in recorded["publish_result"]["error"]


@pytest.mark.asyncio
async def test_publish_to_platforms_raises_retryable_application_error(monkeypatch):
    recorded = {}

    async def fake_update_publish_result(**kwargs):
        recorded.update(kwargs)

    class StubPublisher:
        async def publish(self, _post_config):
            raise PostizRetryableError("postiz unavailable")

        async def close(self):
            return None

    class StubBrowser:
        async def close(self):
            return None

    monkeypatch.setattr(da, "PublisherService", StubPublisher)
    monkeypatch.setattr(da, "BrowserAutomationService", StubBrowser)
    monkeypatch.setattr(
        da.ContentPersistenceService,
        "update_publish_result",
        fake_update_publish_result,
    )

    with pytest.raises(ApplicationError) as exc_info:
        await da.publish_to_platforms(
            {
                "id": "post-retry",
                "platform": "twitter",
                "content": "test",
                "media": [],
                "user_id": "user-1",
                "workflow_id": "wf-1",
            }
        )

    assert exc_info.value.non_retryable is False
    assert recorded["publish_result"]["status"] == "failed"
    assert recorded["publish_result"]["error"] == "postiz unavailable"


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


@pytest.mark.asyncio
async def test_track_engagement_raises_non_retryable_application_error(monkeypatch):
    recorded = {}

    async def fake_record_engagement_result(**kwargs):
        recorded.update(kwargs)

    class StubGrowchief:
        async def get_engagement_metrics(self, **_kwargs):
            return {"engagement_rate": 0.1}

        async def trigger_engagement(self, **_kwargs):
            raise GrowChiefAuthError("growchief bootstrap incomplete")

        async def close(self):
            return None

    monkeypatch.setattr(da, "GrowChiefService", StubGrowchief)
    monkeypatch.setattr(
        da.ContentPersistenceService,
        "record_engagement_result",
        fake_record_engagement_result,
    )
    monkeypatch.setattr(da.settings, "SYNDICATE_ENGAGEMENT_THRESHOLD", 2.0)

    with pytest.raises(ApplicationError) as exc_info:
        await da.track_engagement(
            {
                "post_id": "post-auth",
                "workflow_id": "wf-1",
                "platform": "twitter",
                "platform_post_id": "post-auth",
                "post_url": "https://twitter.com/post/1",
            }
        )

    assert exc_info.value.non_retryable is True
    assert recorded["engagement_result"]["status"] == "failed"
    assert recorded["engagement_result"]["error"] == "growchief bootstrap incomplete"
