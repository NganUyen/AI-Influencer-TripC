import pytest
import os
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

from activities.media_activities import generate_scene_images
from temporalio.exceptions import ApplicationError


@pytest.mark.asyncio
@patch("activities.media_activities.BrowserAutomationService")
@patch("services.media_storage_service.MediaStorageService")
async def test_top_half_browser_capture(MockMediaStorage, MockBrowser):
    # Setup mocks
    mock_browser_instance = AsyncMock()
    # Mock the NEW video recording method:
    mock_browser_instance.record_video_for_tutorial.return_value = "/fake/path.webm"
    MockBrowser.return_value = mock_browser_instance

    mock_media_storage_instance = AsyncMock()
    mock_media_storage_instance.upload_bytes.return_value = {
        "url": "https://mocked.com/browser_captures/fake.webm",
        "storage_url": "https://mocked.com/browser_captures/fake.webm",
        "storage_key": "browser_captures/test/capture.webm",
        "media_asset_id": "asset-browser-123",
    }
    MockMediaStorage.return_value = mock_media_storage_instance

    # We mock out `open` because it will try to read `/fake/path.webm`
    import builtins
    from unittest.mock import mock_open

    # Create fake video data that's large enough to pass validation (> 2000 bytes)
    fake_video_data = b"WEBM" + b"\x00" * 5000
    
    with (
        patch("builtins.open", mock_open(read_data=fake_video_data)),
        patch("os.makedirs"),
        patch("os.path.exists", return_value=True),
        patch("os.path.getsize", return_value=5000), # Mock 5KB file
    ):
        # The fake scenes coming from ScriptContract
        scenes = [
            {
                "id": 1,
                "image_prompt": "Hero sec",
                "caption": "Look",
                "top_half_source_type": "public_page_capture",
                "source_ref": "https://example.com",
            },
        ]

        results = await generate_scene_images(scenes)

        # Assertions
        assert len(results) == 1
        assert results[0]["status"] == "completed"
        assert results[0]["is_video"] == True
        assert results[0]["generation_method"] == "browser_capture"

    print("Browser top-half automation test (success) passed!")


@pytest.mark.asyncio
@patch("activities.media_activities.BrowserAutomationService")
async def test_top_half_browser_capture_too_small(MockBrowser):
    """Test that it fails when the browser capture is too small (e.g. 0 bytes)."""
    mock_browser_instance = AsyncMock()
    mock_browser_instance.record_video_for_tutorial.return_value = "/fake/empty.webm"
    MockBrowser.return_value = mock_browser_instance

    with (
        patch("os.makedirs"),
        patch("os.path.exists", return_value=True),
        patch("os.path.getsize", return_value=150), # Mock tiny file (< 2000)
    ):
        scenes = [{"id": 2, "top_half_source_type": "public_page_capture", "source_ref": "https://fail.com"}]
        
        from temporalio.exceptions import ApplicationError
        with pytest.raises(ApplicationError) as exc:
            await generate_scene_images(scenes)
        
        assert "invalid/tiny file" in str(exc.value)
    
    # Ensure browser was still closed even on failure
    mock_browser_instance.close.assert_called()
    print("Browser top-half automation test (size guard) passed!")


@pytest.mark.asyncio
@patch("activities.media_activities.ImageGenerationService")
async def test_top_half_ai_visual_fallback(MockImageService):
    """Test that ai_visual_fallback scenes use AI image generation."""
    mock_image_service = AsyncMock()
    mock_image_service.generate_images.return_value = {
        "images": [
            {
                "url": "https://mocked.com/ai_images/generated.png",
                "storage_url": "https://mocked.com/ai_images/generated.png",
                "storage_key": "ai_images/test/generated.png",
                "media_asset_id": "asset-ai-123",
            }
        ]
    }
    MockImageService.return_value = mock_image_service

    scenes = [
        {
            "id": 1,
            "top_half_source_type": "ai_visual_fallback",
            "top_half_target": "Futuristic code editor",
            "top_half_capture_hint": "cinematic",
            "image_prompt": "Abstract technology background",
        },
    ]

    results = await generate_scene_images(scenes)

    assert len(results) == 1
    assert results[0]["status"] == "completed"
    assert results[0]["is_video"] == False
    assert results[0]["generation_method"] == "ai_visual"
    assert "ai_images" in results[0]["image_url"]
    
    # Verify ImageGenerationService was called
    mock_image_service.generate_images.assert_called_once()
    call_kwargs = mock_image_service.generate_images.call_args
    assert "Futuristic code editor" in call_kwargs.kwargs["prompt"]
    
    print("AI visual fallback test passed!")


@pytest.mark.asyncio
@patch("activities.media_activities.BrowserAutomationService")
async def test_hybrid_candidate_fails_without_fallback(MockBrowser):
    """Test that hybrid_candidate fails with error when browser capture fails (no fallback)."""
    # Make browser capture fail
    mock_browser_instance = AsyncMock()
    mock_browser_instance.record_video_for_tutorial.side_effect = RuntimeError("Browser capture failed")
    MockBrowser.return_value = mock_browser_instance

    scenes = [
        {
            "id": 1,
            "top_half_source_type": "hybrid_candidate",
            "source_ref": "https://example.com",
            "top_half_target": "Product demo",
            "top_half_capture_hint": "scroll",
        },
    ]

    with (
        patch("os.makedirs"),
    ):
        from temporalio.exceptions import ApplicationError
        with pytest.raises(ApplicationError) as exc:
            await generate_scene_images(scenes)
        
        assert "Browser capture failed" in str(exc.value) or "failed for scene 1" in str(exc.value)
    
    print("Hybrid candidate failure test passed!")


@pytest.mark.asyncio
@patch("activities.media_activities.ImageGenerationService")
async def test_hybrid_candidate_without_source_ref_uses_ai_directly(MockImageService):
    """Test that hybrid_candidate without source_ref goes directly to AI."""
    mock_image_service = AsyncMock()
    mock_image_service.generate_images.return_value = {
        "images": [
            {
                "url": "https://mocked.com/ai_direct/image.png",
                "storage_url": "https://mocked.com/ai_direct/image.png",
                "storage_key": "ai_direct/test/image.png",
                "media_asset_id": "asset-direct-123",
            }
        ]
    }
    MockImageService.return_value = mock_image_service

    scenes = [
        {
            "id": 1,
            "top_half_source_type": "hybrid_candidate",
            "source_ref": None,  # No source_ref
            "top_half_target": "Abstract visual",
            "top_half_capture_hint": "static",
        },
    ]

    results = await generate_scene_images(scenes)

    assert len(results) == 1
    assert results[0]["status"] == "completed"
    assert results[0]["generation_method"] == "ai_visual"
    # Should not have fallback_reason since it went directly to AI
    assert results[0].get("fallback_reason") is None
    
    print("Hybrid candidate direct AI test passed!")


@pytest.mark.asyncio
async def test_public_page_capture_requires_source_ref():
    """Test that public_page_capture fails without source_ref."""
    scenes = [
        {
            "id": 1,
            "top_half_source_type": "public_page_capture",
            "source_ref": None,  # Missing source_ref
            "top_half_target": "Landing page",
        },
    ]

    from temporalio.exceptions import ApplicationError
    with pytest.raises(ApplicationError) as exc:
        await generate_scene_images(scenes)
    
    assert "source_ref" in str(exc.value).lower()
    
    print("Public page capture source_ref requirement test passed!")


@pytest.mark.asyncio
async def test_convert_image_to_video_timeout_is_retryable_and_uses_low_cpu_flags(
    monkeypatch,
):
    import subprocess

    from activities import media_activities

    captured = {}

    class FakeResponse:
        content = b"\x89PNG" + (b"\x00" * 4096)

        def raise_for_status(self):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url):
            return FakeResponse()

    async def fake_to_thread(fn, *args, **kwargs):
        assert fn is subprocess.run
        captured["cmd"] = list(args[0])
        captured["timeout"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setenv("AI_VISUAL_VIDEO_FFMPEG_TIMEOUT_SEC", "90")
    monkeypatch.setattr(media_activities.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(media_activities.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(ApplicationError) as exc:
        await media_activities._convert_image_to_video(
            image_url="https://cdn.example.com/fallback.png",
            scene_id="scene-1",
            scene_metadata={},
            duration_sec=5.0,
        )

    error = exc.value
    assert error.non_retryable is False
    assert captured["timeout"] == 90
    assert "-preset" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("-preset") + 1] == "ultrafast"
    assert "-tune" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("-tune") + 1] == "stillimage"
    assert "-threads" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("-threads") + 1] == "1"
