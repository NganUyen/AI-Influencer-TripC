import httpx
import pytest
from types import SimpleNamespace

from services.ai_service import AIService
from services.errors import GrowChiefAuthError, PostizRetryableError
from services.fal_service import FalAIService
from services.google_tts_service import GoogleTTSService
from services.growchief_service import GrowChiefService
from services.heygen_service import HeyGenService
from services.postiz_service import PostizService


@pytest.mark.asyncio
async def test_postiz_publish_builds_payload(monkeypatch):
    monkeypatch.setenv("POSTIZ_INTEGRATION_MAP", '{"twitter":"integration-1"}')

    class StubResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    captured = []

    class StubClient:
        async def post(self, url, json):
            captured.append((url, json))
            if url == "/upload-from-url":
                return StubResponse({"id": "upload-1", "path": "/uploads/test.jpg"})
            return StubResponse([{"id": "post-1", "postId": "platform-post-1"}])

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

    assert result["provider_post_id"] == "post-1"
    assert result["platform_post_id"] == "platform-post-1"
    assert result["status"] == "scheduled"
    assert result["raw"][0]["id"] == "post-1"
    assert captured[0][0] == "/upload-from-url"
    assert captured[0][1] == {"url": "https://cdn.example/test.jpg"}
    assert captured[1][0] == "/posts"
    assert captured[1][1]["type"] == "schedule"
    assert captured[1][1]["date"] == "2026-03-16T10:00:00Z"
    assert captured[1][1]["posts"][0]["integration"]["id"] == "integration-1"
    assert captured[1][1]["posts"][0]["value"][0]["image"] == [
        {"id": "upload-1", "path": "/uploads/test.jpg"}
    ]
    await service.close()


@pytest.mark.asyncio
async def test_postiz_publish_raises_retryable_error_on_transport_failure(monkeypatch):
    monkeypatch.setenv("POSTIZ_INTEGRATION_MAP", '{"twitter":"integration-1"}')

    class StubClient:
        async def post(self, _url, json):
            raise httpx.HTTPError("postiz error")

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.postiz_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = PostizService()
    with pytest.raises(PostizRetryableError):
        await service.publish(platform="twitter", content="hello")
    await service.close()


@pytest.mark.asyncio
async def test_postiz_publish_treats_html_response_as_retryable(monkeypatch):
    monkeypatch.setenv("POSTIZ_INTEGRATION_MAP", '{"twitter":"integration-1"}')

    class StubResponse:
        status_code = 200
        headers = {"content-type": "text/html"}
        text = "<html>bad gateway</html>"

        def json(self):
            raise ValueError("invalid json")

    class StubClient:
        async def post(self, _url, json):
            return StubResponse()

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.postiz_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = PostizService()
    with pytest.raises(PostizRetryableError):
        await service.publish(platform="twitter", content="hello")
    await service.close()


@pytest.mark.asyncio
async def test_growchief_trigger_engagement_builds_payload(monkeypatch):
    monkeypatch.setenv("GROWCHIEF_WORKFLOW_MAP", '{"twitter":"wf-1"}')

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"status": "queued", "message": "accepted"}]

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

    assert result["job_id"].startswith("growchief_")
    assert result["workflow_id"] == "wf-1"
    assert result["status"] == "pending"
    assert captured["url"] == "/workflows/wf-1"
    assert captured["json"] == {"urls": ["https://platform/post/1"]}
    assert result["account_count"] == 3
    assert result["delay_between_actions"] == 15
    await service.close()


@pytest.mark.asyncio
async def test_growchief_trigger_engagement_raises_auth_error(monkeypatch):
    monkeypatch.setenv("GROWCHIEF_WORKFLOW_MAP", '{"twitter":"wf-1"}')

    class StubResponse:
        status_code = 401
        headers = {"content-type": "application/json"}
        text = '{"msg":"Invalid API key"}'

        def json(self):
            return {"msg": "Invalid API key"}

    class StubClient:
        async def post(self, url, json):
            return StubResponse()

        async def aclose(self):
            return None

    monkeypatch.setattr(
        "services.growchief_service.httpx.AsyncClient", lambda **_: StubClient()
    )

    service = GrowChiefService()
    with pytest.raises(GrowChiefAuthError):
        await service.trigger_engagement(
            post_url="https://platform/post/1",
            platform="twitter",
            engagement_type=["like"],
        )
    await service.close()


@pytest.mark.asyncio
async def test_growchief_metrics_returns_fallback():
    service = GrowChiefService()
    result = await service.get_engagement_metrics(platform="twitter", post_id="abc")
    assert result["platform"] == "twitter"
    assert result["post_id"] == "abc"
    assert result["engagement_rate"] == 0.0
    assert result["source"] == "growchief_public_api_fallback"
    await service.close()


def test_postiz_normalize_webhook_event():
    result = PostizService.normalize_webhook_event(
        {
            "event": "post.published",
            "data": {
                "id": "provider-1",
                "post_id": "platform-1",
                "platform": "twitter",
                "status": "completed",
                "url": "https://twitter.com/post/1",
                "metadata": {
                    "workflow_id": "wf-1",
                    "logical_post_id": "logical-1",
                },
            },
        }
    )

    assert result["status"] == "published"
    assert result["provider_status"] == "completed"
    assert result["provider_post_id"] == "provider-1"
    assert result["platform_post_id"] == "platform-1"
    assert result["post_url"] == "https://twitter.com/post/1"
    assert result["workflow_id"] == "wf-1"
    assert result["logical_post_id"] == "logical-1"


def test_growchief_normalize_webhook_event():
    result = GrowChiefService.normalize_webhook_event(
        {
            "data": {
                "job_id": "job-1",
                "platform": "twitter",
                "status": "success",
                "post_url": "https://twitter.com/post/1",
                "engagement_types": ["like", "comment"],
                "metrics": {"likes": 12, "engagement_rate": 3.2},
                "metadata": {
                    "content_id": "content-1",
                    "workflow_id": "wf-1",
                },
            }
        }
    )

    assert result["status"] == "completed"
    assert result["provider_status"] == "success"
    assert result["provider_job_id"] == "job-1"
    assert result["target_url"] == "https://twitter.com/post/1"
    assert result["action_types"] == ["like", "comment"]
    assert result["metrics"]["likes"] == 12
    assert result["content_id"] == "content-1"
    assert result["workflow_id"] == "wf-1"


@pytest.mark.asyncio
async def test_ai_service_records_openai_usage(monkeypatch):
    captured = {}

    class _StubRawResponse:
        headers = {
            "x-ratelimit-limit-tokens": "10000",
            "x-ratelimit-remaining-tokens": "9750",
            "x-ratelimit-reset-tokens": "8m0s",
            "x-ratelimit-limit-requests": "60",
            "x-ratelimit-remaining-requests": "59",
            "x-ratelimit-reset-requests": "1m0s",
        }

        def parse(self):
            return SimpleNamespace(
                usage=SimpleNamespace(
                    prompt_tokens=20,
                    completion_tokens=5,
                    total_tokens=25,
                ),
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Generated text")
                    )
                ],
            )

    class _StubRawCompletions:
        async def create(self, **kwargs):
            return _StubRawResponse()

    class _StubCompletions:
        def __init__(self):
            self.with_raw_response = _StubRawCompletions()

    class _StubOpenAIClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=_StubCompletions())

    class _StubAnthropicClient:
        pass

    async def fake_record_runtime_usage(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "services.ai_service.AsyncOpenAI",
        lambda **_: _StubOpenAIClient(),
    )
    monkeypatch.setattr(
        "services.ai_service.AsyncAnthropic",
        lambda **_: _StubAnthropicClient(),
    )
    monkeypatch.setattr(
        "services.ai_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )

    service = AIService()
    result = await service.generate_text(prompt="Hello world", model="gpt-4")

    assert result == "Generated text"
    assert captured["provider"] == "openai"
    assert captured["usage"]["requests"] == 1
    assert captured["usage"]["tokens"] == 25
    assert captured["usage"]["input_tokens"] == 20
    assert captured["usage"]["output_tokens"] == 5
    assert captured["quota"]["remaining"] == 9750
    assert captured["quota"]["limit"] == 10000
    assert captured["quota"]["requests_remaining"] == 59
    assert captured["quota"]["exact"] is True
    assert captured["metadata"]["operation"] == "generate_text"


@pytest.mark.asyncio
async def test_fal_service_records_generation_usage(monkeypatch):
    captured = {}
    requests = []

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"images": [{"url": "https://fal.example/image.png"}]}

    class StubClient:
        async def post(self, url, json):
            requests.append((url, json))
            return StubResponse()

        async def aclose(self):
            return None

    async def fake_record_runtime_usage(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "services.fal_service.httpx.AsyncClient", lambda **_: StubClient()
    )
    monkeypatch.setattr(
        "services.fal_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )

    service = FalAIService()
    result = await service.generate_image(prompt="Sunset beach", num_images=2)

    assert result["url"] == "https://fal.example/image.png"
    assert captured["provider"] == "fal_ai"
    assert captured["usage"]["requests"] == 1
    assert captured["usage"]["images"] == 2
    assert captured["metadata"]["operation"] == "generate_image"
    assert requests[0][0] == "/fal-ai/nano-banana-2"
    assert requests[0][1]["aspect_ratio"] == "16:9"
    assert "image_size" not in requests[0][1]
    await service.close()


@pytest.mark.asyncio
async def test_google_tts_service_records_usage(monkeypatch):
    captured = {}
    requests = []

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"audioContent": "aGVsbG8="}

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            requests.append((url, json))
            return StubResponse()

    async def fake_record_runtime_usage(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "services.google_tts_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.google_tts_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )
    monkeypatch.setattr(
        "services.google_tts_service.settings.GOOGLE_TTS_API_KEY",
        "test_google_tts_key",
    )

    service = GoogleTTSService()
    audio = await service.generate_audio(text="Hello there", voice="male_friendly", language="English")

    assert audio == b"hello"
    assert captured["provider"] == "google_tts"
    assert captured["usage"]["requests"] == 1
    assert captured["usage"]["characters"] == len("Hello there")
    assert captured["usage"]["bytes"] == len(b"hello")
    assert captured["metadata"]["operation"] == "generate_audio"
    assert captured["metadata"]["voice"] == "en-US-Studio-O"
    assert requests[0][1]["voice"]["name"] == "en-US-Studio-O"
    assert requests[0][1]["voice"]["languageCode"] == "en-US"


@pytest.mark.asyncio
async def test_heygen_service_create_avatar_uses_upload_asset_and_photo_avatar_group(
    monkeypatch,
):
    captured = {"get": [], "post": []}

    class StubResponse:
        def __init__(self, payload=None, *, content=b"", headers=None):
            self._payload = payload or {}
            self.content = content
            self.headers = headers or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, follow_redirects=False):
            captured["get"].append(
                {"url": url, "follow_redirects": follow_redirects}
            )
            return StubResponse(
                content=b"\xff\xd8\xffavatar",
                headers={"content-type": "image/jpeg"},
            )

        async def post(self, url, headers=None, json=None, content=None):
            captured["post"].append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "content": content,
                }
            )
            if url.endswith("/v1/asset"):
                return StubResponse(
                    {"data": {"id": "asset-123", "image_key": "image/demo/original"}}
                )
            return StubResponse(
                {"data": {"id": "photo-avatar-123", "group_id": "group-123"}}
            )

    usage = {}

    async def fake_record_runtime_usage(**kwargs):
        usage.update(kwargs)

    monkeypatch.setattr(
        "services.heygen_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.heygen_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )
    monkeypatch.setattr(
        "services.heygen_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )

    service = HeyGenService()
    avatar_id = await service.create_avatar(
        image_url="https://cdn.example/avatar.jpg",
        avatar_name="hero-host",
    )

    assert avatar_id == "photo-avatar-123"
    assert captured["get"] == [
        {"url": "https://cdn.example/avatar.jpg", "follow_redirects": True}
    ]
    assert captured["post"][0]["url"] == "https://upload.heygen.com/v1/asset"
    assert captured["post"][0]["headers"]["Content-Type"] == "image/jpeg"
    assert captured["post"][0]["content"] == b"\xff\xd8\xffavatar"
    assert (
        captured["post"][1]["url"]
        == "https://api.heygen.com/v2/photo_avatar/avatar_group/create"
    )
    assert captured["post"][1]["json"] == {
        "name": "hero-host",
        "image_key": "image/demo/original",
    }
    assert usage["provider"] == "heygen"
    assert usage["metadata"]["operation"] == "create_avatar"
    assert usage["metadata"]["avatar_name"] == "hero-host"


@pytest.mark.asyncio
async def test_heygen_service_waits_until_avatar_is_ready(monkeypatch):
    captured = {"urls": []}

    class StubResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    responses = iter(
        [
            {"data": {"id": "photo-avatar-123", "status": "pending"}},
            {"data": {"id": "photo-avatar-123", "status": "ready"}},
        ]
    )

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers=None):
            captured["urls"].append(url)
            return StubResponse(next(responses))

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    async def fake_record_runtime_usage(**_kwargs):
        return None

    monkeypatch.setattr(
        "services.heygen_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.heygen_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )
    monkeypatch.setattr("services.heygen_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "services.heygen_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )

    service = HeyGenService()
    payload = await service.wait_for_avatar_ready(
        "photo-avatar-123",
        timeout_seconds=10,
        poll_interval=3,
    )

    assert payload["data"]["status"] == "ready"
    assert captured["urls"] == [
        "https://api.heygen.com/v2/photo_avatar/photo-avatar-123",
        "https://api.heygen.com/v2/photo_avatar/photo-avatar-123",
    ]
    assert sleep_calls == [3]


@pytest.mark.asyncio
async def test_heygen_service_times_out_when_avatar_stays_pending(monkeypatch):
    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"id": "photo-avatar-123", "status": "pending"}}

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers=None):
            return StubResponse()

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    async def fake_record_runtime_usage(**_kwargs):
        return None

    monkeypatch.setattr(
        "services.heygen_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.heygen_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )
    monkeypatch.setattr("services.heygen_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "services.heygen_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )

    service = HeyGenService()
    with pytest.raises(Exception, match="still processing this avatar"):
        await service.wait_for_avatar_ready(
            "photo-avatar-123",
            timeout_seconds=5,
            poll_interval=2,
        )

    assert sleep_calls == [2, 2, 2]


@pytest.mark.asyncio
async def test_heygen_service_records_video_job_usage(monkeypatch):
    captured = {}

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"video_id": "video-123"}}

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return StubResponse()

    async def fake_record_runtime_usage(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "services.heygen_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.heygen_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )
    monkeypatch.setattr(
        "services.heygen_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )

    service = HeyGenService()
    result = await service.create_video(
        avatar_id="avatar-1",
        audio_url="https://cdn.example/audio.mp3",
    )

    assert result["video_id"] == "video-123"
    assert captured["url"] == "https://api.heygen.com/v2/videos"
    assert captured["json"]["avatar_id"] == "avatar-1"
    assert captured["json"]["audio_url"] == "https://cdn.example/audio.mp3"
    assert captured["json"]["aspect_ratio"] == "9:16"
    assert captured["json"]["resolution"] == "1080p"
    assert captured["json"]["background"] == {"type": "color", "value": "#ffffff"}
    assert captured["provider"] == "heygen"
    assert captured["usage"]["requests"] == 1
    assert captured["usage"]["jobs"] == 1
    assert captured["metadata"]["operation"] == "create_video"


@pytest.mark.asyncio
async def test_heygen_service_prefers_v2_video_status(monkeypatch):
    captured = {}

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "video_id": "video-123",
                "status": "completed",
                "video_url": "https://cdn.example/video.mp4",
            }

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers=None, params=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return StubResponse()

    usage = {}

    async def fake_record_runtime_usage(**kwargs):
        usage.update(kwargs)

    monkeypatch.setattr(
        "services.heygen_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.heygen_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )
    monkeypatch.setattr(
        "services.heygen_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )

    service = HeyGenService()
    result = await service.get_video_status("video-123")

    assert captured["url"] == "https://api.heygen.com/v2/videos/video-123"
    assert captured["params"] is None
    assert result["status"] == "completed"
    assert usage["metadata"]["provider_status"] == "completed"


@pytest.mark.asyncio
async def test_heygen_service_records_remaining_quota(monkeypatch):
    captured = {}

    class StubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": {"remaining_quota": 42, "details": {"api": 42}}}

    class StubClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            return StubResponse()

    async def fake_record_runtime_usage(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "services.heygen_service.httpx.AsyncClient",
        lambda **_: StubClient(),
    )
    monkeypatch.setattr(
        "services.heygen_service.QuotaMonitorService.record_runtime_usage",
        fake_record_runtime_usage,
    )
    monkeypatch.setattr(
        "services.heygen_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )

    service = HeyGenService()
    result = await service.get_remaining_quota()

    assert result["data"]["remaining_quota"] == 42
    assert captured["provider"] == "heygen"
    assert captured["quota"]["remaining"] == 42
    assert captured["quota"]["source"] == "provider_live_endpoint"
    assert captured["quota"]["exact"] is True
    assert captured["metadata"]["operation"] == "get_remaining_quota"
