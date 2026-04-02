"""
Test suite for capture compositor module.
Tests image composition with mocked Pillow operations.

Run with: pytest tests/test_capture_compositor.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import patch, MagicMock, call

from activities.capture.capture_models import (
    SceneCaptureSpec,
    CaptureTarget,
    HighlightRegion
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST CLASS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCompositorActivity:
    """Test compositor activity with mocked Pillow operations."""

    def test_headline_not_rendered_when_none(self):
        """Khi headline=None thì Pillow không vẽ text headline"""
        with patch("activities.capture.compositor.Image") as mock_img, \
             patch("activities.capture.compositor.ImageDraw") as mock_draw:
            mock_image = MagicMock()
            mock_image.size = (1080, 960)
            mock_img.open.return_value.__enter__ = lambda s: mock_image
            mock_img.open.return_value.__exit__ = MagicMock(return_value=False)

            from activities.capture.compositor import composite_overlay
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="test text",
                headline=None,
                capture_target=CaptureTarget(type="mobile"),
                duration_seconds=3.0
            )
            composite_overlay("fake_input.png", "fake_output.png", spec)
            draw_instance = mock_draw.Draw.return_value
            # Không được gọi text với nội dung headline
            for c in draw_instance.text.call_args_list:
                assert "headline" not in str(c).lower()

    def test_subtitle_NOT_rendered_in_top_half(self):
        """subtitle KHÔNG được vẽ trong top-half compositor"""
        with patch("activities.capture.compositor.Image") as mock_img, \
             patch("activities.capture.compositor.ImageDraw") as mock_draw:
            mock_image = MagicMock()
            mock_image.size = (1080, 960)
            mock_img.open.return_value = mock_image

            from activities.capture.compositor import composite_overlay
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="Subtitle text phải ở bottom half",
                capture_target=CaptureTarget(type="mobile"),
                duration_seconds=3.0
            )
            result = composite_overlay("fake.png", "fake_out.png", spec)
            # subtitle_text phải được trả về để dùng ở assembly
            assert result.subtitle_text == "Subtitle text phải ở bottom half"
            assert result.subtitle_position == "bottom_half"

    def test_highlight_rectangle_drawn_when_region_exists(self):
        """Khi có highlight_region thì ImageDraw.rectangle được gọi"""
        with patch("activities.capture.compositor.Image") as mock_img, \
             patch("activities.capture.compositor.ImageDraw") as mock_draw:
            mock_image = MagicMock()
            mock_image.size = (1080, 960)
            mock_image.crop.return_value = MagicMock()
            mock_img.open.return_value = mock_image

            from activities.capture.compositor import composite_overlay
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="test",
                capture_target=CaptureTarget(type="mobile"),
                highlight_region=HighlightRegion(
                    x=100, y=200, w=300, h=100,
                    zoom_factor=1.5,
                    border_color="#FF4444"
                ),
                duration_seconds=3.0
            )
            composite_overlay("fake.png", "fake_out.png", spec)
            draw_instance = mock_draw.Draw.return_value
            assert draw_instance.rectangle.called

    def test_highlight_NOT_drawn_when_none(self):
        """Khi highlight_region=None thì rectangle KHÔNG được gọi"""
        with patch("activities.capture.compositor.Image") as mock_img, \
             patch("activities.capture.compositor.ImageDraw") as mock_draw:
            mock_image = MagicMock()
            mock_image.size = (1080, 960)
            mock_img.open.return_value = mock_image

            from activities.capture.compositor import composite_overlay
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="test",
                capture_target=CaptureTarget(type="mobile"),
                highlight_region=None,
                duration_seconds=3.0
            )
            composite_overlay("fake.png", "fake_out.png", spec)
            draw_instance = mock_draw.Draw.return_value
            assert not draw_instance.rectangle.called

    def test_output_resolution_always_1080x960(self):
        """Output image phải luôn là 1080x960 dù input khác size"""
        with patch("activities.capture.compositor.Image") as mock_img:
            mock_image = MagicMock()
            mock_image.size = (1920, 1080)  # input sai size
            mock_img.open.return_value = mock_image

            from activities.capture.compositor import composite_overlay
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="test",
                capture_target=CaptureTarget(type="mobile"),
                duration_seconds=3.0
            )
            composite_overlay("fake.png", "fake_out.png", spec)
            # resize phải được gọi với (1080, 960)
            mock_image.resize.assert_called_with((1080, 960))

    def test_output_dir_created_if_not_exists(self, tmp_path):
        """Thư mục output phải được tạo nếu chưa tồn tại"""
        output_path = str(tmp_path / "new_dir" / "output.png")
        with patch("activities.capture.compositor.Image") as mock_img:
            mock_image = MagicMock()
            mock_image.size = (1080, 960)
            mock_img.open.return_value = mock_image

            from activities.capture.compositor import composite_overlay
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="test",
                capture_target=CaptureTarget(type="mobile"),
                duration_seconds=3.0
            )
            composite_overlay("fake.png", output_path, spec)
            assert os.path.exists(os.path.dirname(output_path))

    def test_activity_error_on_corrupt_image(self):
        """Image.open raise OSError phải được bắt thành ActivityError có campaign_id"""
        with patch("activities.capture.compositor.Image") as mock_img:
            mock_img.open.side_effect = OSError("corrupt file")

            from activities.capture.compositor import composite_overlay
            from activities.capture.exceptions import CaptureCompositorError
            spec = SceneCaptureSpec(
                scene_index=0,
                script_text="test",
                capture_target=CaptureTarget(type="mobile"),
                duration_seconds=3.0
            )
            with pytest.raises(CaptureCompositorError) as exc_info:
                composite_overlay("fake.png", "fake_out.png", spec,
                                  campaign_id="camp-001")
            assert "camp-001" in str(exc_info.value)
