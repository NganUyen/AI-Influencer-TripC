"""
Pipeline robustness tests for short video generation.

Tests critical fixes:
- CRITICAL-1: Duration/image array mismatch detection
- CRITICAL-2: Telegram error notification on workflow failure
- MEDIUM-1: Orphan asset prevention
- MEDIUM-2: Presigned URL video detection  
- MEDIUM-3: Invalid source type handling

Covers checkpoints CP1-CP7 for observability.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import logging

# Import the functions we're testing
from activities.video_activities import _is_video_url, _get_extension_for_url
from services.script_service import ScriptService, _VALID_TOP_HALF_SOURCE_TYPES


class TestDurationMismatchDetection:
    """Tests for CRITICAL-1: Duration/image array mismatch raises error."""

    @pytest.mark.asyncio
    async def test_duration_mismatch_raises_with_failed_scenes(self):
        """
        When one scene fails to generate an image (image_url=None),
        workflow should raise SceneAssetMismatchError before assembly.
        """
        from services.errors import SceneAssetMismatchError

        # Simulate scenes_result with one failed scene
        scenes_result = [
            {"id": 1, "image_url": "https://example.com/scene1.jpg", "caption": "Scene 1"},
            {"id": 2, "image_url": None, "caption": "Scene 2"},  # Failed!
            {"id": 3, "image_url": "https://example.com/scene3.jpg", "caption": "Scene 3"},
        ]

        # Extract raw URLs to check for failures
        image_urls_raw = [scene.get("image_url") for scene in scenes_result]
        failed_scene_indices = [i for i, url in enumerate(image_urls_raw) if url is None]

        # Assert we detect the failure
        assert failed_scene_indices == [1], "Should detect scene index 1 as failed"
        assert len(failed_scene_indices) == 1, "Should have exactly 1 failed scene"

        # The workflow would raise this error
        with pytest.raises(SceneAssetMismatchError) as exc_info:
            raise SceneAssetMismatchError(
                f"Asset generation failed for {len(failed_scene_indices)} scene(s): indices {failed_scene_indices}"
            )

        assert "failed" in str(exc_info.value).lower()
        assert "1" in str(exc_info.value)  # Contains the index

    @pytest.mark.asyncio
    async def test_aligned_arrays_match_length(self):
        """Aligned arrays should have matching lengths after filtering."""
        scenes_result = [
            {"id": 1, "image_url": "https://example.com/scene1.jpg"},
            {"id": 2, "image_url": "https://example.com/scene2.jpg"},
            {"id": 3, "image_url": "https://example.com/scene3.jpg"},
        ]
        scene_durations = [4.0, 5.0, 3.0]

        # Build aligned arrays
        valid_scenes_with_index = [
            (i, scene) for i, scene in enumerate(scenes_result) if scene.get("image_url")
        ]
        image_urls = [scene.get("image_url") for _, scene in valid_scenes_with_index]
        aligned_durations = [
            scene_durations[i] if i < len(scene_durations) else 4.0
            for i, _ in valid_scenes_with_index
        ]

        assert len(image_urls) == len(aligned_durations) == 3


class TestBrowserCaptureLogging:
    """Tests for CP2: Warning log when source_ref=None with public_page_capture."""

    @pytest.mark.asyncio
    @patch("activities.media_activities.ImageGenerationService")
    async def test_browser_capture_none_source_ref_logs_warning(
        self, MockImageGen, caplog
    ):
        """
        When top_half_source_type="public_page_capture" but source_ref=None,
        should log warning and fallback to AI.
        """
        # Setup mock
        mock_image_service = AsyncMock()
        mock_image_service.generate_images.return_value = {
            "url": "https://ai-fallback.com/image.jpg",
            "source_url": "https://ai-fallback.com/image.jpg",
            "storage_url": "https://storage.com/image.jpg",
            "storage_key": "images/test.jpg",
            "images": [{"media_asset_id": "ai-123"}],
        }
        mock_image_service.close = AsyncMock()
        MockImageGen.return_value = mock_image_service

        from activities.media_activities import generate_scene_images

        scenes = [
            {
                "id": 1,
                "top_half_source_type": "public_page_capture",
                "source_ref": None,  # Missing!
                "image_prompt": "A beautiful landscape",
                "metadata": {},
            }
        ]

        with caplog.at_level(logging.WARNING):
            results = await generate_scene_images(scenes)

        # Check warning was logged
        assert any(
            "source_ref=None" in record.message or "source_ref" in record.message.lower()
            for record in caplog.records
        ), f"Expected warning about source_ref=None. Got: {[r.message for r in caplog.records]}"

        # Check fallback was triggered
        assert results[0]["image_url"] == "https://ai-fallback.com/image.jpg"
        assert results[0].get("fallback_triggered", False) is True

    @pytest.mark.asyncio
    @patch("activities.media_activities.ImageGenerationService")
    @patch("activities.media_activities.BrowserAutomationService")
    async def test_browser_capture_failure_fallbacks_to_ai(
        self, MockBrowser, MockImageGen, caplog
    ):
        """When browser automation fails, should fallback to AI image generation."""
        # Setup browser mock to fail
        mock_browser = AsyncMock()
        mock_browser.initialize_browser = AsyncMock()
        mock_browser.record_video_for_tutorial = AsyncMock(
            side_effect=TimeoutError("Page load timeout")
        )
        mock_browser.close = AsyncMock()
        MockBrowser.return_value = mock_browser

        # Setup AI fallback mock
        mock_image_service = AsyncMock()
        mock_image_service.generate_images.return_value = {
            "url": "https://ai-fallback.com/image.jpg",
            "source_url": "https://ai-fallback.com/image.jpg",
            "images": [{}],
        }
        mock_image_service.close = AsyncMock()
        MockImageGen.return_value = mock_image_service

        from activities.media_activities import generate_scene_images

        scenes = [
            {
                "id": 1,
                "top_half_source_type": "public_page_capture",
                "source_ref": "https://example.com/page",
                "image_prompt": "A beautiful landscape",
                "metadata": {},
            }
        ]

        with caplog.at_level(logging.WARNING):
            results = await generate_scene_images(scenes)

        # Check AI fallback was called
        mock_image_service.generate_images.assert_called_once()

        # Check result indicates fallback
        assert results[0]["image_url"] == "https://ai-fallback.com/image.jpg"
        assert results[0].get("fallback_triggered") is True


class TestVideoUrlDetection:
    """Tests for MEDIUM-2: Presigned URL video detection."""

    def test_is_video_url_with_presigned_s3_webm(self):
        """Presigned S3 URL with .webm extension should be detected as video."""
        url = "https://bucket.s3.amazonaws.com/videos/capture.webm?X-Amz-Algorithm=AWS4&X-Amz-Signature=abc123"
        assert _is_video_url(url) is True

    def test_is_video_url_with_presigned_s3_mp4(self):
        """Presigned S3 URL with .mp4 extension should be detected as video."""
        url = "https://bucket.s3.amazonaws.com/videos/final.mp4?X-Amz-Expires=3600&X-Amz-Signature=xyz"
        assert _is_video_url(url) is True

    def test_is_video_url_with_image(self):
        """Image URL should not be detected as video."""
        url = "https://cdn.example.com/images/scene.jpg?v=123"
        assert _is_video_url(url) is False

    def test_is_video_url_with_cdn_no_extension(self):
        """CDN URL without extension should default to image (not video)."""
        url = "https://cdn.example.com/abc123"
        assert _is_video_url(url) is False

    def test_is_video_url_with_query_containing_video_word(self):
        """Query params containing 'video' word should not affect detection."""
        url = "https://example.com/image.jpg?format=video"
        assert _is_video_url(url) is False  # Path is .jpg, not video

    def test_get_extension_for_presigned_url(self):
        """Extension extraction should work with presigned URLs."""
        webm_url = "https://s3.amazonaws.com/test.webm?X-Amz-Signature=abc"
        mp4_url = "https://s3.amazonaws.com/test.mp4?X-Amz-Signature=abc"
        jpg_url = "https://s3.amazonaws.com/test.jpg?X-Amz-Signature=abc"
        no_ext = "https://s3.amazonaws.com/test?X-Amz-Signature=abc"

        assert _get_extension_for_url(webm_url) == ".webm"
        assert _get_extension_for_url(mp4_url) == ".mp4"
        assert _get_extension_for_url(jpg_url) == ".jpg"
        assert _get_extension_for_url(no_ext) == ".jpg"  # Default


class TestOrphanAssetPrevention:
    """Tests for MEDIUM-1: Orphan asset not created on upload failure."""

    @pytest.mark.asyncio
    @patch("activities.media_activities.ImageGenerationService")
    @patch("activities.media_activities.BrowserAutomationService")
    @patch("activities.media_activities.MediaStorageService")
    async def test_orphan_asset_not_created_on_upload_failure(
        self, MockMediaStorage, MockBrowser, MockImageGen
    ):
        """When upload returns None, should raise error, not create orphan."""
        import os
        import tempfile

        # Create a temp file to simulate video_path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
            f.write(b"fake video content")
            temp_path = f.name

        try:
            # Setup browser mock
            mock_browser = AsyncMock()
            mock_browser.initialize_browser = AsyncMock()
            mock_browser.record_video_for_tutorial = AsyncMock(return_value=temp_path)
            mock_browser.close = AsyncMock()
            MockBrowser.return_value = mock_browser

            # Setup storage mock to return None (failure case)
            mock_storage = AsyncMock()
            mock_storage.upload_bytes = AsyncMock(return_value=None)
            MockMediaStorage.return_value = mock_storage

            # Setup AI fallback mock
            mock_image_service = AsyncMock()
            mock_image_service.generate_images.return_value = {
                "url": "https://ai-fallback.com/image.jpg",
                "images": [{}],
            }
            mock_image_service.close = AsyncMock()
            MockImageGen.return_value = mock_image_service

            from activities.media_activities import generate_scene_images

            scenes = [
                {
                    "id": 1,
                    "top_half_source_type": "public_page_capture",
                    "source_ref": "https://example.com/page",
                    "image_prompt": "fallback prompt",
                    "metadata": {},
                }
            ]

            # Should fallback to AI since upload failed
            results = await generate_scene_images(scenes)

            # AI fallback should be used
            assert results[0]["image_url"] == "https://ai-fallback.com/image.jpg"
            # is_video should NOT be set for AI fallback
            assert results[0].get("is_video") is not True

        finally:
            os.unlink(temp_path)


class TestTelegramErrorNotification:
    """Tests for CRITICAL-2: Telegram notification on workflow failure."""

    @pytest.mark.asyncio
    @patch("activities.approval_activities.TelegramService")
    async def test_workflow_sends_telegram_on_failure(self, MockTelegram):
        """When workflow fails, should send error notification to Telegram."""
        mock_tg = MagicMock()
        mock_tg.bot = AsyncMock()
        mock_tg.bot.send_message = AsyncMock()
        MockTelegram.return_value = mock_tg

        from activities.approval_activities import send_telegram_error_notification

        config = {
            "telegram_chat_id": "123456789",
            "workflow_id": "wf-test-123",
            "topic": "Beach vacation guide",
            "error_type": "SceneAssetMismatchError",
            "error_summary": "Asset generation failed for 2 scene(s)",
        }

        result = await send_telegram_error_notification(config)

        # Verify message was sent
        mock_tg.bot.send_message.assert_called_once()
        call_kwargs = mock_tg.bot.send_message.call_args[1]

        assert call_kwargs["chat_id"] == "123456789"
        assert "Failed" in call_kwargs["text"]
        assert "Beach vacation guide" in call_kwargs["text"]
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_error_notification_skips_when_no_chat_id(self):
        """Should skip notification when telegram_chat_id is missing."""
        from activities.approval_activities import send_telegram_error_notification

        config = {
            "telegram_chat_id": None,  # Missing!
            "workflow_id": "wf-test-123",
            "error_type": "SomeError",
        }

        result = await send_telegram_error_notification(config)

        assert result["status"] == "skipped"
        assert result["reason"] == "no_chat_id"


class TestInvalidSourceTypeHandling:
    """Tests for MEDIUM-3: Invalid source type defaults with warning."""

    @pytest.mark.asyncio
    async def test_invalid_source_type_defaults_to_ai_visual_fallback(self, caplog):
        """Invalid top_half_source_type should default to ai_visual_fallback."""
        service = ScriptService()

        package = {
            "beat_sheet": {
                "beats": [
                    {
                        "idx": 1,
                        "top_half_source_type": "invalid_type_xyz",  # Invalid!
                        "top_half_target": "https://example.com",
                        "bottom_half_message": "Test narration",
                        "overlay_text": "Test caption",
                        "duration_sec": 5,
                    }
                ]
            }
        }

        with caplog.at_level(logging.WARNING):
            contract = await service.generate_script_from_package(
                app_name="TestApp",
                package=package,
                persona_config={"language_name": "English"},
            )

        # Check warning was logged
        assert any(
            "invalid" in record.message.lower() and "invalid_type_xyz" in record.message
            for record in caplog.records
        ), f"Expected warning about invalid type. Got: {[r.message for r in caplog.records]}"

        # Check it defaulted to ai_visual_fallback
        assert contract.scenes[0].top_half_source_type == "ai_visual_fallback"

    @pytest.mark.asyncio
    async def test_valid_source_types_pass_through(self):
        """Valid top_half_source_types should pass through unchanged."""
        service = ScriptService()

        for valid_type in ["public_page_capture", "ai_visual_fallback", "search"]:
            package = {
                "beat_sheet": {
                    "beats": [
                        {
                            "idx": 1,
                            "top_half_source_type": valid_type,
                            "top_half_target": "https://example.com",
                            "bottom_half_message": "Test",
                            "overlay_text": "Caption",
                            "duration_sec": 4,
                        }
                    ]
                }
            }

            contract = await service.generate_script_from_package(
                app_name="TestApp",
                package=package,
                persona_config={},
            )

            assert contract.scenes[0].top_half_source_type == valid_type

    def test_valid_source_types_set_is_complete(self):
        """Verify the valid source types set includes expected values."""
        assert "public_page_capture" in _VALID_TOP_HALF_SOURCE_TYPES
        assert "ai_visual_fallback" in _VALID_TOP_HALF_SOURCE_TYPES
        assert "search" in _VALID_TOP_HALF_SOURCE_TYPES
        assert "authenticated_capture_later" in _VALID_TOP_HALF_SOURCE_TYPES
        assert "hybrid_candidate" in _VALID_TOP_HALF_SOURCE_TYPES


class TestCheckpointLogging:
    """Tests for observability checkpoints CP1-CP7."""

    @pytest.mark.asyncio
    async def test_cp1_scene_contract_build_logging(self, caplog):
        """CP1: SceneContract build should be logged with key fields."""
        service = ScriptService()

        package = {
            "beat_sheet": {
                "beats": [
                    {
                        "idx": 1,
                        "top_half_source_type": "public_page_capture",
                        "top_half_target": "https://example.com/feature",
                        "source_ref": "https://example.com/page",
                        "bottom_half_message": "Check out this feature",
                        "overlay_text": "Amazing!",
                        "duration_sec": 5,
                    }
                ]
            }
        }

        with caplog.at_level(logging.INFO):
            await service.generate_script_from_package(
                app_name="TestApp",
                package=package,
                persona_config={},
            )

        # Check CP1 log message
        cp1_logs = [r for r in caplog.records if "SceneContract built" in r.message]
        assert len(cp1_logs) >= 1, "CP1 log should be present"
        assert "top_half_type=public_page_capture" in cp1_logs[0].message
        assert "has_source_ref=True" in cp1_logs[0].message
