import httpx
import pytest

from services.growchief_service import GrowChiefService
from services.postiz_service import PostizService


@pytest.mark.asyncio
async def test_postiz_publish_builds_payload(monkeypatch):
    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "post-1", "post_id": "platform-post-1"}

    captured = {}

    class StubClient:
        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return StubResponse()

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.postiz_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = PostizService()
    result = await service.publish(
        platform="twitter",
        content="hello",
        media_urls=["https://cdn.example/test.jpg"],
        scheduled_time="2026-03-16T10:00:00Z",
    )

    assert result["id"] == "post-1"
    assert captured["url"] == "/api/posts"
    assert captured["json"]["status"] == "scheduled"
    assert captured["json"]["scheduled_at"] == "2026-03-16T10:00:00Z"
    await service.close()


@pytest.mark.asyncio
async def test_postiz_publish_raises_http_error(monkeypatch):
    class StubClient:
        async def post(self, _url, json):
            raise httpx.HTTPError("postiz error")

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.postiz_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = PostizService()
    with pytest.raises(httpx.HTTPError):
        await service.publish(platform="twitter", content="hello")
    await service.close()


@pytest.mark.asyncio
async def test_growchief_trigger_engagement_builds_payload(monkeypatch):
    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"job_id": "job-123"}

    captured = {}

    class StubClient:
        async def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return StubResponse()

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.growchief_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = GrowChiefService()
    result = await service.trigger_engagement(
        post_url="https://platform/post/1",
        platform="twitter",
        engagement_type=["like", "comment"],
        account_count=3,
        delay_minutes=15,
    )

    assert result["job_id"] == "job-123"
    assert captured["url"] == "/api/engagements/trigger"
    assert captured["json"]["account_count"] == 3
    assert captured["json"]["delay_between_actions"] == 15
    await service.close()


@pytest.mark.asyncio
async def test_growchief_metrics_raises_http_error(monkeypatch):
    class StubClient:
        async def get(self, _url, params):
            assert params["platform"] == "twitter"
            raise httpx.HTTPError("metrics unavailable")

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.growchief_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = GrowChiefService()
    with pytest.raises(httpx.HTTPError):
        await service.get_engagement_metrics(platform="twitter", post_id="abc")
    await service.close()
