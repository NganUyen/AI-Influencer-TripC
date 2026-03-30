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

        # Scene 1: Used browser
        assert results[0]["status"] == "completed"
        assert (
            results[0]["image_url"] == "https://mocked.com/browser_captures/fake.webm"
        )
        assert results[0]["media_asset_id"] == "asset-browser-123"
        mock_browser_instance.record_video_for_tutorial.assert_called_once_with(
            "https://example.com", capture_hint="scroll"
        )
        mock_media_storage_instance.upload_bytes.assert_called_once()

    print("Browser top-half automation test passed successfully!")
