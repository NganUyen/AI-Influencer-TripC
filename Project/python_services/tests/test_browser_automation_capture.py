import pytest

from activities import media_activities
from services.browser_automation import BrowserAutomationService


@pytest.mark.asyncio
async def test_capture_with_retry_skips_warmup_after_first_failure(tmp_path):
    video_path = tmp_path / "capture.webm"
    video_path.write_bytes(b"WEBM" + (b"\x00" * 5000))
    calls = []

    class FakeBrowser:
        async def record_video_for_tutorial(self, _url, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise TimeoutError("Page load timeout")
            return str(video_path), {"capture_duration_ms": 123}

    result_path, metrics = await media_activities._capture_with_retry(
        browser=FakeBrowser(),
        source_ref="https://example.com",
        capture_hint="scroll",
        target_selector="Hero",
        action_text="Scroll the hero section",
        visual_success_criteria="Hero headline visible",
        max_capture_seconds=20,
        follow_relevant_links=True,
        scene_duration_sec=6.0,
        scene_id="scene-1",
    )

    assert result_path == str(video_path)
    assert metrics == {"capture_duration_ms": 123}
    assert calls[0]["warmup_enabled"] is True
    assert calls[0]["follow_relevant_links"] is True
    assert calls[1]["warmup_enabled"] is False
    assert calls[1]["follow_relevant_links"] is False


@pytest.mark.asyncio
async def test_pre_validate_url_does_not_flag_root_homepage_as_robots_blocked(
    monkeypatch,
):
    class FakeResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, _url):
            return FakeResponse(200)

        async def get(self, _url):
            return FakeResponse(200, "User-agent: *\nDisallow: /\n")

    monkeypatch.setattr(media_activities.httpx, "AsyncClient", FakeAsyncClient)

    result = await media_activities._pre_validate_url("https://www.coursera.org")

    assert result["accessible"] is True
    assert result["robots_blocked"] is False


@pytest.mark.asyncio
async def test_capture_browser_video_retries_without_proxy_after_http_response_failure(
    monkeypatch, tmp_path
):
    video_path = tmp_path / "capture.webm"
    video_path.write_bytes(b"WEBM" + (b"\x00" * 5000))
    browser_instances = []

    class FakeMetrics:
        def to_dict(self):
            return {"capture_duration_ms": 123}

    class FakeBrowser:
        def __init__(self):
            self.init_calls = []
            self.closed = 0
            self.record_attempts = 0
            browser_instances.append(self)

        async def initialize_browser(self, **kwargs):
            self.init_calls.append(kwargs)

        async def record_video_for_tutorial(self, _url, **kwargs):
            self.record_attempts += 1
            proxy_config = self.init_calls[-1].get("proxy_config")
            if proxy_config:
                raise RuntimeError(
                    "net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://www.coursera.org"
                )
            return str(video_path), FakeMetrics()

        async def close(self):
            self.closed += 1

    class FakeRegionService:
        async def build_region_profile(self):
            return {"country": "Vietnam", "countryCode": "VN", "locale": "vi-VN"}

    class FakeProxyManagerService:
        @staticmethod
        async def lease_proxy(**kwargs):
            return {"proxy": {"server": "http://proxy.example:8080"}}

    class FakeMediaStorage:
        async def upload_bytes(self, **kwargs):
            return {
                "url": "https://mocked.com/browser_captures/fake.webm",
                "storage_url": "https://mocked.com/browser_captures/fake.webm",
                "storage_key": "browser_captures/test/capture.webm",
                "media_asset_id": "asset-browser-123",
            }

    async def fake_prevalidate(_url, timeout_seconds=10.0):
        return {
            "accessible": True,
            "status_code": 200,
            "has_bot_detection": False,
            "requires_auth": False,
            "robots_blocked": False,
        }

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(media_activities, "BrowserAutomationService", FakeBrowser)
    monkeypatch.setattr(media_activities, "MediaStorageService", lambda: FakeMediaStorage())
    monkeypatch.setattr(media_activities, "_pre_validate_url", fake_prevalidate)
    monkeypatch.setattr(media_activities.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr("services.region_service.RegionService", FakeRegionService)
    monkeypatch.setattr(
        "services.proxy_manager_service.ProxyManagerService", FakeProxyManagerService
    )

    with (
        monkeypatch.context() as m,
    ):
        m.setattr("os.makedirs", lambda *args, **kwargs: None)
        m.setattr("os.path.exists", lambda _path: True)
        m.setattr("os.path.getsize", lambda _path: 5000)

        import builtins
        from unittest.mock import mock_open

        m.setattr(builtins, "open", mock_open(read_data=b"WEBM" + (b"\x00" * 5000)))

        result = await media_activities._capture_browser_video(
            scene={"id": 4, "top_half_source_type": "public_page_capture"},
            scene_metadata={"user_id": "user-123", "workflow_id": "run-1"},
            source_ref="https://www.coursera.org",
        )

    assert result["url"] == "https://mocked.com/browser_captures/fake.webm"
    assert len(browser_instances) == 2
    assert browser_instances[0].init_calls[0]["proxy_config"] == {
        "server": "http://proxy.example:8080"
    }
    assert browser_instances[1].init_calls[0]["proxy_config"] is None


@pytest.mark.asyncio
async def test_ensure_page_has_rendered_content_tolerates_navigation_error(
    monkeypatch,
):
    service = BrowserAutomationService()

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr("services.browser_automation.asyncio.sleep", fake_sleep)

    class FakePage:
        def __init__(self):
            self.goto_calls = []
            self.reload_calls = []

        async def goto(self, _url, wait_until, timeout):
            self.goto_calls.append((wait_until, timeout))
            raise RuntimeError(
                "net::ERR_HTTP_RESPONSE_CODE_FAILURE at https://example.com/"
            )

        async def reload(self, wait_until, timeout):
            self.reload_calls.append((wait_until, timeout))
            raise AssertionError("reload should not be needed")

        async def evaluate(self, _script):
            return {
                "readyState": "interactive",
                "hasMedia": True,
                "hasText": True,
                "mediaCount": 2,
                "childCount": 24,
                "textLength": 120,
                "looksBlank": False,
                "bgColor": "rgb(255, 255, 255)",
                "isWhiteBg": True,
            }

    page = FakePage()

    await service._ensure_page_has_rendered_content(
        page=page,
        url="https://example.com",
    )

    assert page.goto_calls == [("networkidle", 30000)]
    assert page.reload_calls == []


@pytest.mark.asyncio
async def test_record_video_for_tutorial_salvages_existing_video_after_late_failure(
    monkeypatch, tmp_path
):
    service = BrowserAutomationService()
    video_path = tmp_path / "capture.webm"
    video_path.write_bytes(b"WEBM" + (b"\x00" * 5000))

    class FakeVideo:
        async def path(self):
            return str(video_path)

    class FakePage:
        def __init__(self):
            self.video = FakeVideo()
            self.closed = False

        async def evaluate(self, _script):
            return {
                "bodyChildCount": 5,
                "documentHeight": 1200,
                "hasImages": 2,
                "title": "Example",
            }

        async def set_viewport_size(self, _size):
            return None

        async def close(self):
            self.closed = True

    class FakeContext:
        async def new_page(self):
            return FakePage()

    async def fake_sleep(_seconds):
        return None

    async def fake_ensure_page(*, page, url):
        return None

    async def fail_build_scroll_plan(**_kwargs):
        raise RuntimeError("late navigation failure after recording started")

    monkeypatch.setattr("services.browser_automation.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(service, "_ensure_page_has_rendered_content", fake_ensure_page)
    monkeypatch.setattr(service, "_build_scroll_plan", fail_build_scroll_plan)

    service.context = FakeContext()

    path, metrics = await service.record_video_for_tutorial(
        "https://example.com",
        capture_hint="scroll",
        warmup_enabled=False,
    )

    assert path == str(video_path)
    assert metrics["file_size_bytes"] >= 2000 if isinstance(metrics, dict) else metrics.file_size_bytes >= 2000
