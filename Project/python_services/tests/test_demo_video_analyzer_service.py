from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.contracts import RecordedDemoEvidenceContract
from services.demo_video_analyzer_service import DemoVideoAnalyzerService


@pytest.mark.asyncio
async def test_analyze_demo_video_passes_user_video_thesis_to_analyze():
    service = DemoVideoAnalyzerService()
    expected = RecordedDemoEvidenceContract(
        demo_video_asset_url="https://example.com/demo.mp4",
        original_filename="",
        duration_sec=1.0,
        width=1080,
        height=1920,
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_response = mock_client.get.return_value
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b"0" * 512

        service.analyze = AsyncMock(return_value=expected)

        result = await service.analyze_demo_video(
            video_url="https://example.com/demo.mp4",
            reference_url="https://example.com",
            video_goal="feature_demo",
            audience="travelers",
            cta="Try it now",
            user_video_thesis="Show collaborative itinerary editing",
        )

    assert result is expected
    service.analyze.assert_awaited_once()
    _, kwargs = service.analyze.await_args
    assert kwargs["user_video_thesis"] == "Show collaborative itinerary editing"
