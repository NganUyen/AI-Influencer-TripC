"""
Tests for FrameUnderstandingService (V3.1 vision-based frame analysis).

Tests:
- 10-frame cap enforcement
- Per-frame fallback handling
- Frame sampling strategy
- Contract validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.contracts import FrameUnderstandingContract
from services.frame_understanding_service import FrameUnderstandingService


@pytest.fixture
def mock_ai_service():
    """Mock AIService for testing."""
    mock = MagicMock()
    mock.analyze_image_structured = AsyncMock()
    return mock


@pytest.fixture
def service(mock_ai_service):
    """Create FrameUnderstandingService with mocked AIService."""
    return FrameUnderstandingService(ai_service=mock_ai_service)


class TestFrameCap:
    """Test 10-frame cap enforcement."""

    @pytest.mark.asyncio
    async def test_short_video_all_frames(self, service, mock_ai_service):
        """Videos ≤10s should sample every second."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "Test UI",
            "text_visible": "Sample text",
            "ui_elements": ["button", "textbox"],
            "activity_description": "User clicks button",
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/short.mp4",
            duration_sec=8.0,
        )

        # 8 second video = 8 frames (0, 1, 2, 3, 4, 5, 6, 7)
        assert len(frames) == 8
        assert mock_ai_service.analyze_image_structured.call_count == 8

    @pytest.mark.asyncio
    async def test_long_video_capped_at_10(self, service, mock_ai_service):
        """Videos >10s should be capped at 10 frames."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "Test UI",
            "text_visible": "Sample text",
            "ui_elements": ["button"],
            "activity_description": "User interaction",
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/long.mp4",
            duration_sec=30.0,
        )

        # 30 second video should be capped at 10 frames
        assert len(frames) == 10
        assert mock_ai_service.analyze_image_structured.call_count == 10

        # Check sampling interval (30s / 10 = 3s apart)
        timestamps = [f.timestamp_sec for f in frames]
        assert timestamps[0] == 0.0
        assert timestamps[-1] == pytest.approx(27.0, abs=1.0)  # Last frame near end

    @pytest.mark.asyncio
    async def test_very_long_video_even_sampling(self, service, mock_ai_service):
        """60s video should have evenly distributed 10 frames."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "Test",
            "text_visible": "",
            "ui_elements": [],
            "activity_description": "Activity",
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/verylong.mp4",
            duration_sec=60.0,
        )

        assert len(frames) == 10

        # Frames should be ~6 seconds apart (60 / 10)
        timestamps = [f.timestamp_sec for f in frames]
        for i in range(1, len(timestamps)):
            interval = timestamps[i] - timestamps[i - 1]
            assert 5.0 <= interval <= 7.0


class TestPerFrameFallback:
    """Test per-frame fallback handling."""

    @pytest.mark.asyncio
    async def test_single_frame_failure_continues(self, service, mock_ai_service):
        """Single frame failure should not abort entire analysis."""
        call_count = 0

        async def mock_analyze_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Fail on 3rd frame
                raise Exception("API timeout")
            return {
                "screen_content": f"Frame {call_count}",
                "text_visible": "Text",
                "ui_elements": ["button"],
                "activity_description": "Activity",
            }

        mock_ai_service.analyze_image_structured = mock_analyze_with_failure

        frames = await service.analyze_frames(
            video_url="https://test.com/video.mp4",
            duration_sec=5.0,
        )

        # Should have 4 frames (5 total - 1 failed)
        assert len(frames) == 4
        assert all(isinstance(f, FrameUnderstandingContract) for f in frames)

    @pytest.mark.asyncio
    async def test_all_frames_fail_returns_empty(self, service, mock_ai_service):
        """All frames failing should return empty list, not crash."""
        mock_ai_service.analyze_image_structured.side_effect = Exception(
            "All frames failed"
        )

        frames = await service.analyze_frames(
            video_url="https://test.com/video.mp4",
            duration_sec=3.0,
        )

        assert frames == []

    @pytest.mark.asyncio
    async def test_partial_response_handled(self, service, mock_ai_service):
        """Incomplete vision response should use default values."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "UI visible",
            # Missing text_visible, ui_elements, activity_description
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/video.mp4",
            duration_sec=2.0,
        )

        assert len(frames) == 2
        assert frames[0].screen_content == "UI visible"
        assert frames[0].text_visible == ""  # Default
        assert frames[0].ui_elements == []  # Default
        assert frames[0].activity_description == ""  # Default


class TestContractValidation:
    """Test FrameUnderstandingContract validation."""

    @pytest.mark.asyncio
    async def test_contract_fields_populated(self, service, mock_ai_service):
        """All contract fields should be properly populated."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "Dashboard with charts",
            "text_visible": "Total Sales: $1.2M",
            "ui_elements": ["chart", "table", "button"],
            "activity_description": "User navigates to analytics dashboard",
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/video.mp4",
            duration_sec=1.0,
        )

        frame = frames[0]
        assert isinstance(frame, FrameUnderstandingContract)
        assert frame.timestamp_sec == 0.0
        assert frame.screen_content == "Dashboard with charts"
        assert frame.text_visible == "Total Sales: $1.2M"
        assert frame.ui_elements == ["chart", "table", "button"]
        assert frame.activity_description == "User navigates to analytics dashboard"

    @pytest.mark.asyncio
    async def test_timestamp_sequence(self, service, mock_ai_service):
        """Timestamps should be in ascending order."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "Test",
            "text_visible": "",
            "ui_elements": [],
            "activity_description": "Test",
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/video.mp4",
            duration_sec=5.0,
        )

        timestamps = [f.timestamp_sec for f in frames]
        assert timestamps == sorted(timestamps)
        assert timestamps[0] == 0.0


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_zero_duration_video(self, service, mock_ai_service):
        """0-second video should return empty list."""
        frames = await service.analyze_frames(
            video_url="https://test.com/empty.mp4",
            duration_sec=0.0,
        )

        assert frames == []
        mock_ai_service.analyze_image_structured.assert_not_called()

    @pytest.mark.asyncio
    async def test_negative_duration_raises_error(self, service, mock_ai_service):
        """Negative duration should raise ValueError."""
        with pytest.raises(ValueError, match="duration_sec must be positive"):
            await service.analyze_frames(
                video_url="https://test.com/video.mp4",
                duration_sec=-5.0,
            )

    @pytest.mark.asyncio
    async def test_empty_video_url_raises_error(self, service, mock_ai_service):
        """Empty video URL should raise ValueError."""
        with pytest.raises(ValueError, match="video_url cannot be empty"):
            await service.analyze_frames(
                video_url="",
                duration_sec=10.0,
            )

    @pytest.mark.asyncio
    async def test_very_short_video_subsecond(self, service, mock_ai_service):
        """Sub-second videos should still produce 1 frame at 0.0s."""
        mock_ai_service.analyze_image_structured.return_value = {
            "screen_content": "Brief flash",
            "text_visible": "",
            "ui_elements": [],
            "activity_description": "Quick transition",
        }

        frames = await service.analyze_frames(
            video_url="https://test.com/flash.mp4",
            duration_sec=0.5,
        )

        assert len(frames) == 1
        assert frames[0].timestamp_sec == 0.0
