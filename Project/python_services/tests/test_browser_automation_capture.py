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
