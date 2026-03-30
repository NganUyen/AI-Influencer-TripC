import pytest
import os
import uuid
from unittest.mock import AsyncMock, patch

from activities.media_activities import generate_scene_images


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

    with (
        patch("builtins.open", mock_open(read_data=b"fake_image_data")),
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
        mock_browser_instance.record_video_for_tutorial.assert_called_once_with(
            "https://example.com", capture_hint="scroll"
        )

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
