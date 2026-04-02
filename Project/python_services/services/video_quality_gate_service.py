"""
Video Quality Gate Service.

Validates uploaded demo videos before analysis:
- Duration checks (warn 90-180s, reject >180s)
- Resolution checks (minimum 720p height recommended)
- File integrity checks
- Basic blur detection (lightweight)
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class VideoQualityReport(BaseModel):
    """Result of quality gate validation."""

    passed: bool
    duration_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    is_readable: bool = False
    blur_score: Optional[float] = None

    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def resolution_string(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "unknown"


class VideoQualityGateService:
    """Validates demo videos against quality requirements."""

    # Hard limits from spec
    HARD_MAX_DURATION_SEC = 180.0
    RECOMMENDED_MAX_DURATION_SEC = 90.0
    MIN_DURATION_SEC = 1.0  # Too short to be useful

    # Resolution recommendations
    RECOMMENDED_MIN_HEIGHT = 720
    MIN_HEIGHT_ABSOLUTE = 480  # Below this is too low quality

    # Blur detection (simple threshold)
    MIN_BLUR_SCORE = 20.0  # Very blurry if below this

    def __init__(self):
        """Initialize the quality gate service."""
        pass

    async def validate_video_file(
        self,
        video_path: str | Path,
    ) -> VideoQualityReport:
        """
        Run quality gate validation on a video file.

        Args:
            video_path: Path to video file on disk

        Returns:
            VideoQualityReport with validation results
        """
        video_path = Path(video_path)
        report = VideoQualityReport(passed=False)

        # Check file exists and get size
        if not video_path.exists():
            report.errors.append("Video file not found")
            return report

        report.file_size_bytes = video_path.stat().st_size
        if report.file_size_bytes == 0:
            report.errors.append("Video file is empty")
            return report

        # Extract metadata with ffprobe (run in executor to avoid blocking)
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(None, self._extract_metadata, video_path)
        if not metadata:
            report.errors.append(
                "Could not read video file metadata. File may be corrupted."
            )
            return report

        report.is_readable = True
        report.duration_sec = metadata.get("duration")
        report.width = metadata.get("width")
        report.height = metadata.get("height")

        # Validate duration
        if report.duration_sec is None:
            report.errors.append("Could not determine video duration")
        elif report.duration_sec < self.MIN_DURATION_SEC:
            report.errors.append(
                f"Video is too short ({report.duration_sec:.1f}s). Minimum: {self.MIN_DURATION_SEC}s"
            )
        elif report.duration_sec > self.HARD_MAX_DURATION_SEC:
            report.errors.append(
                f"Video exceeds maximum duration ({report.duration_sec:.1f}s). "
                f"Maximum allowed: {self.HARD_MAX_DURATION_SEC}s (3 minutes)"
            )
        elif report.duration_sec > self.RECOMMENDED_MAX_DURATION_SEC:
            report.warnings.append(
                f"Video duration ({report.duration_sec:.1f}s) exceeds recommended maximum "
                f"of {self.RECOMMENDED_MAX_DURATION_SEC}s. Consider trimming to under 90 seconds for best results."
            )

        # Validate resolution
        if report.height is None or report.width is None:
            report.errors.append("Could not determine video resolution")
        elif report.height < self.MIN_HEIGHT_ABSOLUTE:
            report.errors.append(
                f"Video resolution too low ({report.resolution_string}). "
                f"Minimum height: {self.MIN_HEIGHT_ABSOLUTE}p"
            )
        elif report.height < self.RECOMMENDED_MIN_HEIGHT:
            report.warnings.append(
                f"Video resolution ({report.resolution_string}) is below recommended minimum "
                f"of {self.RECOMMENDED_MIN_HEIGHT}p. Quality may be affected."
            )

        # Basic blur check (lightweight - run in executor to avoid blocking)
        blur_score = await loop.run_in_executor(
            None, self._check_blur_simple, video_path
        )
        if blur_score is not None:
            report.blur_score = blur_score
            if blur_score < self.MIN_BLUR_SCORE:
                report.warnings.append(
                    f"Video appears blurry (sharpness score: {blur_score:.1f}). "
                    "Consider using a sharper recording."
                )

        # Final verdict
        report.passed = len(report.errors) == 0

        return report

    def _extract_metadata(self, video_path: Path) -> Optional[dict]:
        """
        Extract video metadata using ffprobe.

        Returns:
            dict with keys: duration, width, height, codec
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,codec_name:format=duration",
                    "-of",
                    "default=noprint_wrappers=1",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning("ffprobe failed: %s", result.stderr)
                return None

            # Parse ffprobe output
            metadata = {}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key == "duration":
                        try:
                            metadata["duration"] = float(value)
                        except ValueError:
                            pass
                    elif key == "width":
                        try:
                            metadata["width"] = int(value)
                        except ValueError:
                            pass
                    elif key == "height":
                        try:
                            metadata["height"] = int(value)
                        except ValueError:
                            pass
                    elif key == "codec_name":
                        metadata["codec"] = value

            return metadata if metadata else None

        except subprocess.TimeoutExpired:
            logger.error("ffprobe timeout for %s", video_path)
            return None
        except FileNotFoundError:
            logger.error(
                "ffprobe not found in PATH. Install ffmpeg to enable video validation."
            )
            return None
        except Exception as exc:
            logger.error("ffprobe failed with unexpected error: %s", exc)
            return None

    def _check_blur_simple(self, video_path: Path) -> Optional[float]:
        """
        Lightweight blur check using Laplacian variance on first frame.

        Uses ffmpeg to extract first frame, then checks sharpness.
        Higher score = sharper image.

        Returns:
            float blur score or None if check failed
        """
        try:
            # Try OpenCV approach if available
            try:
                import cv2
                import numpy as np

                # Extract first frame with ffmpeg
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name

                try:
                    result = subprocess.run(
                        [
                            "ffmpeg",
                            "-i",
                            str(video_path),
                            "-vframes",
                            "1",
                            "-q:v",
                            "2",
                            "-y",
                            tmp_path,
                        ],
                        capture_output=True,
                        timeout=15,
                    )

                    if result.returncode != 0:
                        return None

                    # Calculate Laplacian variance
                    image = cv2.imread(tmp_path)
                    if image is None:
                        return None

                    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

                    return float(laplacian_var)

                finally:
                    Path(tmp_path).unlink(missing_ok=True)

            except ImportError:
                # OpenCV not available - skip blur check
                logger.debug("OpenCV not available, skipping blur check")
                return None

        except Exception as exc:
            logger.debug("Blur check failed (non-critical): %s", exc)
            return None
