"""
Demo Video Analyzer Service (Phase 4).

Analyzes uploaded demo videos to extract:
- Metadata (duration, resolution)
- Representative keyframes (not every frame)
- Timeline segments via scene detection
- OCR text from keyframes
- Feature candidates from OCR evidence
- Confidence scoring from available signals

This is a lightweight analysis skeleton that uses:
- ffprobe for metadata
- ffmpeg scene detection for segmentation
- ffmpeg for keyframe extraction
- pytesseract for OCR (if available)

No vision model is used in this phase - OCR-only fallback is the default.
"""

from __future__ import annotations

import asyncio
import logging
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel

from services.contracts import (
    ExtractedFeatureContract,
    KeyframeContract,
    RecordedDemoEvidenceContract,
    TimelineSegmentContract,
)

logger = logging.getLogger(__name__)


class VideoMetadata(BaseModel):
    """Video metadata from ffprobe."""

    duration_sec: float
    width: int
    height: int
    codec: Optional[str] = None
    fps: Optional[float] = None


class SceneChange(BaseModel):
    """A detected scene change point."""

    timestamp_sec: float
    score: float  # Scene change confidence 0-1


class DemoVideoAnalyzerService:
    """
    Analyzes demo videos to extract evidence for recorded_demo_video mode.

    This is a lightweight skeleton implementation for Phase 4.
    Uses representative frames only (not every frame).
    Falls back to OCR-only if no vision model is available.
    """

    # Configuration
    MAX_KEYFRAMES = 10  # Maximum keyframes to extract
    MIN_SEGMENT_DURATION_SEC = 2.0  # Minimum segment length
    SCENE_THRESHOLD = 0.3  # FFmpeg scene detection threshold
    DEFAULT_KEYFRAME_INTERVAL_SEC = 10.0  # Fallback if no scene changes

    # OCR config
    OCR_CONFIDENCE_THRESHOLD = 60  # Minimum tesseract confidence

    def __init__(self):
        """Initialize the analyzer service."""
        self._ocr_available: Optional[bool] = None

    async def analyze_demo_video(
        self,
        video_url: str,
        reference_url: str = "",
        video_goal: str = "feature_demo",
        audience: str = "",
        cta: str = "",
    ) -> RecordedDemoEvidenceContract:
        """
        Download and analyze a demo video from a storage URL.

        This is a convenience wrapper that downloads the video, runs analysis,
        and enriches the evidence with contextual metadata.

        Args:
            video_url: Storage URL of the uploaded demo video
            reference_url: Optional reference website URL (stored in evidence)
            video_goal: Video goal/intent (stored in evidence)
            audience: Target audience (stored in evidence)
            cta: Call-to-action (stored in evidence)

        Returns:
            RecordedDemoEvidenceContract with analysis results
        """
        import httpx

        # Download video to temp file
        temp_video_path = None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".mp4", prefix="demo_video_"
            ) as tmp:
                temp_video_path = Path(tmp.name)

            logger.info("Downloading demo video from %s", video_url)
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(video_url, follow_redirects=True)
                response.raise_for_status()
                content = response.content

            if len(content) < 256:
                raise ValueError(
                    f"Downloaded video is too small ({len(content)} bytes)"
                )

            with open(temp_video_path, "wb") as f:
                f.write(content)

            # Run analysis on local file
            evidence = await self.analyze(
                video_path=temp_video_path,
                video_url=video_url,
                original_filename="",
            )

            # Store contextual metadata in confidence_signals for downstream use
            # (these will be transferred to ConceptBrief in Phase 6)
            evidence.confidence_signals["video_goal"] = video_goal
            evidence.confidence_signals["audience"] = audience
            evidence.confidence_signals["cta"] = cta
            if reference_url:
                evidence.confidence_signals["reference_url"] = reference_url

            return evidence

        finally:
            # Clean up temp file
            if temp_video_path and temp_video_path.exists():
                try:
                    temp_video_path.unlink()
                except Exception as exc:
                    logger.warning("Failed to clean up temp video file: %s", exc)

    async def analyze(
        self,
        video_path: str | Path,
        video_url: str,
        original_filename: str = "",
    ) -> RecordedDemoEvidenceContract:
        """
        Run full analysis pipeline on a demo video.

        Args:
            video_path: Local path to video file
            video_url: Storage URL for the video (for evidence contract)
            original_filename: Original uploaded filename

        Returns:
            RecordedDemoEvidenceContract with analysis results
        """
        video_path = Path(video_path)
        logger.info("Starting demo video analysis: %s", video_path.name)

        # Step 1: Extract metadata
        metadata = await self._extract_metadata(video_path)
        if metadata is None:
            logger.error("Failed to extract video metadata")
            return self._build_empty_evidence(video_url, original_filename)

        logger.info(
            "Video metadata: %.1fs, %dx%d",
            metadata.duration_sec,
            metadata.width,
            metadata.height,
        )

        # Step 2: Detect scene changes for segmentation
        scene_changes = await self._detect_scene_changes(video_path, metadata)
        logger.info("Detected %d scene changes", len(scene_changes))

        # Step 3: Build segments from scene changes
        segments = self._build_segments(scene_changes, metadata)
        logger.info("Built %d segments", len(segments))

        # Step 4: Extract representative keyframes
        keyframes = await self._extract_keyframes(video_path, segments, metadata)
        logger.info("Extracted %d keyframes", len(keyframes))

        # Step 5: Run OCR on keyframes
        ocr_results = await self._run_ocr_on_keyframes(keyframes)
        logger.info(
            "OCR completed: %d frames with text",
            sum(1 for texts in ocr_results.values() if texts),
        )

        # Step 6: Update segments with OCR results
        segments = self._attach_ocr_to_segments(segments, keyframes, ocr_results)

        # Step 7: Extract feature candidates from OCR
        features = self._extract_features_from_ocr(segments, keyframes, ocr_results)
        logger.info("Extracted %d feature candidates", len(features))

        # Step 8: Generate timeline narrative (human-readable summary)
        timeline_narrative = self._generate_timeline_narrative(segments, metadata)

        # Step 9: Generate feature candidates list
        feature_candidates = self._generate_feature_candidates(features)

        # Step 10: Compute confidence
        confidence, confidence_signals = self._compute_confidence(
            metadata, segments, keyframes, ocr_results, features
        )

        # Build final evidence contract
        evidence = RecordedDemoEvidenceContract(
            demo_video_asset_url=video_url,
            original_filename=original_filename,
            duration_sec=metadata.duration_sec,
            width=metadata.width,
            height=metadata.height,
            keyframes=keyframes,
            segments=segments,
            extracted_features=features,
            timeline_narrative=timeline_narrative,
            feature_candidates=feature_candidates,
            analysis_confidence_overall=confidence,
            confidence_signals=confidence_signals,
            analysis_version="1.0",
            ocr_enabled=self._check_ocr_available(),
            vision_model_used=None,  # OCR-only in Phase 4
        )

        logger.info(
            "Analysis complete: confidence=%s, features=%d, segments=%d",
            confidence,
            len(features),
            len(segments),
        )

        return evidence

    def _build_empty_evidence(
        self, video_url: str, original_filename: str
    ) -> RecordedDemoEvidenceContract:
        """Build an empty evidence contract when analysis fails."""
        return RecordedDemoEvidenceContract(
            demo_video_asset_url=video_url,
            original_filename=original_filename,
            duration_sec=0.0,
            width=0,
            height=0,
            timeline_narrative="Unable to analyze video.",
            feature_candidates=[],
            analysis_confidence_overall="low",
            confidence_signals={"error": "metadata_extraction_failed"},
        )

    async def _extract_metadata(self, video_path: Path) -> Optional[VideoMetadata]:
        """Extract video metadata using ffprobe."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        "stream=width,height,codec_name,r_frame_rate:format=duration",
                        "-of",
                        "default=noprint_wrappers=1",
                        str(video_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                ),
            )

            if result.returncode != 0:
                logger.warning("ffprobe failed: %s", result.stderr)
                return None

            # Parse output
            data: dict[str, Any] = {}
            for line in result.stdout.split("\n"):
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    data[key] = value

            duration = float(data.get("duration", 0))
            width = int(data.get("width", 0))
            height = int(data.get("height", 0))
            codec = data.get("codec_name")

            # Parse frame rate (format: "30/1" or "30000/1001")
            fps = None
            fps_str = data.get("r_frame_rate", "")
            if "/" in fps_str:
                try:
                    num, den = fps_str.split("/")
                    fps = float(num) / float(den)
                except (ValueError, ZeroDivisionError):
                    pass

            if duration <= 0 or width <= 0 or height <= 0:
                return None

            return VideoMetadata(
                duration_sec=duration,
                width=width,
                height=height,
                codec=codec,
                fps=fps,
            )

        except subprocess.TimeoutExpired:
            logger.error("ffprobe timeout")
            return None
        except FileNotFoundError:
            logger.error("ffprobe not found in PATH")
            return None
        except Exception as exc:
            logger.error("Metadata extraction failed: %s", exc)
            return None

    async def _detect_scene_changes(
        self, video_path: Path, metadata: VideoMetadata
    ) -> list[SceneChange]:
        """
        Detect scene changes using ffmpeg's scene filter.

        Returns list of timestamps where scene changes occur.
        """
        try:
            # Use ffmpeg scene detection filter
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ffmpeg",
                        "-i",
                        str(video_path),
                        "-vf",
                        f"select='gt(scene,{self.SCENE_THRESHOLD})',showinfo",
                        "-f",
                        "null",
                        "-",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                ),
            )

            # Parse scene change timestamps from stderr
            # Format: [Parsed_showinfo_1 ...] n:123 pts:4567 pts_time:12.345 ...
            scene_changes: list[SceneChange] = []
            for line in result.stderr.split("\n"):
                if "pts_time:" in line:
                    match = re.search(r"pts_time:(\d+\.?\d*)", line)
                    if match:
                        timestamp = float(match.group(1))
                        # Extract scene score if available
                        score_match = re.search(r"scene:(\d+\.?\d*)", line)
                        score = float(score_match.group(1)) if score_match else 0.5
                        scene_changes.append(
                            SceneChange(timestamp_sec=timestamp, score=score)
                        )

            # Always include start (0) and end
            if not scene_changes or scene_changes[0].timestamp_sec > 1.0:
                scene_changes.insert(0, SceneChange(timestamp_sec=0.0, score=1.0))

            return scene_changes

        except subprocess.TimeoutExpired:
            logger.warning("Scene detection timeout, using fallback intervals")
            return self._fallback_scene_changes(metadata)
        except Exception as exc:
            logger.warning("Scene detection failed: %s, using fallback", exc)
            return self._fallback_scene_changes(metadata)

    def _fallback_scene_changes(self, metadata: VideoMetadata) -> list[SceneChange]:
        """Generate fallback scene changes at fixed intervals."""
        changes = []
        t = 0.0
        while t < metadata.duration_sec:
            changes.append(SceneChange(timestamp_sec=t, score=0.3))
            t += self.DEFAULT_KEYFRAME_INTERVAL_SEC
        return changes

    def _build_segments(
        self, scene_changes: list[SceneChange], metadata: VideoMetadata
    ) -> list[TimelineSegmentContract]:
        """
        Build timeline segments from scene change points.

        Merges very short segments and limits total count.
        """
        if not scene_changes:
            # Single segment for entire video
            return [
                TimelineSegmentContract(
                    segment_id=f"seg_{uuid4().hex[:8]}",
                    start_sec=0.0,
                    end_sec=metadata.duration_sec,
                    segment_type="unknown",
                    description="Full video",
                )
            ]

        segments: list[TimelineSegmentContract] = []
        sorted_changes = sorted(scene_changes, key=lambda x: x.timestamp_sec)

        for i, change in enumerate(sorted_changes):
            start = change.timestamp_sec
            # End is either next scene or video end
            if i + 1 < len(sorted_changes):
                end = sorted_changes[i + 1].timestamp_sec
            else:
                end = metadata.duration_sec

            duration = end - start

            # Skip very short segments
            if duration < self.MIN_SEGMENT_DURATION_SEC and segments:
                # Extend previous segment instead
                segments[-1] = TimelineSegmentContract(
                    segment_id=segments[-1].segment_id,
                    start_sec=segments[-1].start_sec,
                    end_sec=end,
                    segment_type=segments[-1].segment_type,
                    description=segments[-1].description,
                    keyframe_ids=segments[-1].keyframe_ids,
                    ocr_texts=segments[-1].ocr_texts,
                )
                continue

            # Infer segment type based on position
            segment_type = self._infer_segment_type(
                start, end, metadata.duration_sec, len(segments)
            )

            segments.append(
                TimelineSegmentContract(
                    segment_id=f"seg_{uuid4().hex[:8]}",
                    start_sec=start,
                    end_sec=end,
                    segment_type=segment_type,
                    description=f"Segment {len(segments) + 1} ({end - start:.1f}s)",
                )
            )

        return segments

    def _infer_segment_type(
        self, start: float, end: float, total_duration: float, segment_index: int
    ) -> str:
        """Infer segment type based on position in video."""
        relative_start = start / total_duration if total_duration > 0 else 0

        if segment_index == 0 and relative_start < 0.1:
            return "intro"
        elif start > total_duration * 0.85:
            return "outro"
        elif (end - start) < 3.0:
            return "transition"
        else:
            return "feature_demo"

    async def _extract_keyframes(
        self,
        video_path: Path,
        segments: list[TimelineSegmentContract],
        metadata: VideoMetadata,
    ) -> list[KeyframeContract]:
        """
        Extract representative keyframes from video.

        Takes one frame per segment, up to MAX_KEYFRAMES total.
        Uses middle of each segment for best representation.
        """
        keyframes: list[KeyframeContract] = []

        # Calculate timestamps for keyframe extraction
        timestamps: list[float] = []
        for segment in segments[: self.MAX_KEYFRAMES]:
            # Use middle of segment
            mid = (segment.start_sec + segment.end_sec) / 2
            timestamps.append(mid)

        # If fewer segments than MAX_KEYFRAMES, add evenly spaced frames
        if len(timestamps) < self.MAX_KEYFRAMES:
            interval = metadata.duration_sec / (self.MAX_KEYFRAMES + 1)
            for i in range(1, self.MAX_KEYFRAMES + 1):
                t = interval * i
                if t not in timestamps and t < metadata.duration_sec:
                    timestamps.append(t)
                    if len(timestamps) >= self.MAX_KEYFRAMES:
                        break

        timestamps = sorted(set(timestamps))[: self.MAX_KEYFRAMES]

        # Extract each keyframe
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            for i, timestamp in enumerate(timestamps):
                frame_id = f"kf_{uuid4().hex[:8]}"
                output_path = tmp_path / f"{frame_id}.jpg"

                success = await self._extract_single_frame(
                    video_path, timestamp, output_path
                )

                if success:
                    keyframes.append(
                        KeyframeContract(
                            frame_id=frame_id,
                            timestamp_sec=timestamp,
                            image_path=str(output_path),
                        )
                    )

            # Link keyframes to segments
            for segment in segments:
                for kf in keyframes:
                    if segment.start_sec <= kf.timestamp_sec < segment.end_sec:
                        segment.keyframe_ids.append(kf.frame_id)

            return keyframes

    async def _extract_single_frame(
        self, video_path: Path, timestamp: float, output_path: Path
    ) -> bool:
        """Extract a single frame at given timestamp."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    [
                        "ffmpeg",
                        "-ss",
                        str(timestamp),
                        "-i",
                        str(video_path),
                        "-frames:v",
                        "1",
                        "-q:v",
                        "2",
                        "-y",
                        str(output_path),
                    ],
                    capture_output=True,
                    timeout=15,
                ),
            )
            return result.returncode == 0 and output_path.exists()
        except Exception as exc:
            logger.debug("Frame extraction failed at %.1fs: %s", timestamp, exc)
            return False

    def _check_ocr_available(self) -> bool:
        """Check if pytesseract/tesseract is available."""
        if self._ocr_available is not None:
            return self._ocr_available

        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._ocr_available = True
        except Exception:
            self._ocr_available = False

        return self._ocr_available

    async def _run_ocr_on_keyframes(
        self, keyframes: list[KeyframeContract]
    ) -> dict[str, list[str]]:
        """
        Run OCR on extracted keyframes.

        Returns dict mapping frame_id to list of detected text strings.
        """
        if not self._check_ocr_available():
            logger.info("OCR not available (pytesseract/tesseract not installed)")
            return {}

        results: dict[str, list[str]] = {}

        try:
            import pytesseract
            from PIL import Image

            for kf in keyframes:
                if not kf.image_path or not Path(kf.image_path).exists():
                    continue

                try:
                    # Run OCR with confidence data
                    image = Image.open(kf.image_path)
                    ocr_data = pytesseract.image_to_data(
                        image, output_type=pytesseract.Output.DICT
                    )

                    # Extract high-confidence text
                    texts: list[str] = []
                    for i, conf in enumerate(ocr_data.get("conf", [])):
                        try:
                            confidence = int(conf)
                        except (ValueError, TypeError):
                            continue

                        if confidence >= self.OCR_CONFIDENCE_THRESHOLD:
                            text = ocr_data["text"][i].strip()
                            if text and len(text) > 1:  # Skip single chars
                                texts.append(text)

                    results[kf.frame_id] = texts

                except Exception as exc:
                    logger.debug("OCR failed for %s: %s", kf.frame_id, exc)
                    results[kf.frame_id] = []

        except ImportError:
            logger.info("PIL or pytesseract not available for OCR")

        return results

    def _attach_ocr_to_segments(
        self,
        segments: list[TimelineSegmentContract],
        keyframes: list[KeyframeContract],
        ocr_results: dict[str, list[str]],
    ) -> list[TimelineSegmentContract]:
        """Attach OCR results to their corresponding segments."""
        kf_by_id = {kf.frame_id: kf for kf in keyframes}

        for segment in segments:
            all_texts: list[str] = []
            for kf_id in segment.keyframe_ids:
                texts = ocr_results.get(kf_id, [])
                all_texts.extend(texts)
            segment.ocr_texts = list(set(all_texts))  # Dedupe

        return segments

    def _extract_features_from_ocr(
        self,
        segments: list[TimelineSegmentContract],
        keyframes: list[KeyframeContract],
        ocr_results: dict[str, list[str]],
    ) -> list[ExtractedFeatureContract]:
        """
        Extract feature candidates from OCR text.

        Uses simple heuristics:
        - Capitalized words/phrases
        - Button labels (common UI patterns)
        - Repeated terms across segments
        """
        # Collect all OCR texts with their timestamps
        text_occurrences: dict[str, list[tuple[float, float]]] = {}

        for segment in segments:
            for text in segment.ocr_texts:
                # Normalize text
                normalized = text.strip()
                if len(normalized) < 2:
                    continue

                if normalized not in text_occurrences:
                    text_occurrences[normalized] = []
                text_occurrences[normalized].append(
                    (segment.start_sec, segment.end_sec)
                )

        # Score and filter candidates
        features: list[ExtractedFeatureContract] = []
        seen_names: set[str] = set()

        # Patterns that suggest UI features
        feature_patterns = [
            r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$",  # Title Case
            r"^[A-Z]{2,}$",  # ALL CAPS (buttons)
            r"^(?:Settings|Dashboard|Profile|Home|Menu|Search|Login|Sign)",  # Common UI
        ]

        for text, occurrences in text_occurrences.items():
            # Skip very common/generic words
            if text.lower() in {"the", "and", "for", "with", "this", "that", "from"}:
                continue

            # Check if matches feature patterns
            is_feature = any(re.match(p, text) for p in feature_patterns)

            # Also consider repeated terms (appear in multiple segments)
            if len(occurrences) >= 2:
                is_feature = True

            if not is_feature:
                continue

            # Avoid duplicates
            name_key = text.lower()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            # Calculate time range
            all_starts = [o[0] for o in occurrences]
            all_ends = [o[1] for o in occurrences]
            start_sec = min(all_starts)
            end_sec = max(all_ends)

            # Confidence based on occurrence count
            if len(occurrences) >= 3:
                confidence = "high"
            elif len(occurrences) >= 2:
                confidence = "medium"
            else:
                confidence = "low"

            # Find associated keyframes
            kf_ids = []
            for segment in segments:
                if any(
                    segment.start_sec <= o[0] <= segment.end_sec for o in occurrences
                ):
                    kf_ids.extend(segment.keyframe_ids)

            features.append(
                ExtractedFeatureContract(
                    feature_id=f"feat_{uuid4().hex[:8]}",
                    name=text,
                    description=f"Detected via OCR in {len(occurrences)} segment(s)",
                    timestamp_start_sec=start_sec,
                    timestamp_end_sec=end_sec,
                    confidence=confidence,
                    ocr_evidence=[text],
                    keyframe_ids=list(set(kf_ids)),
                )
            )

        # Sort by confidence and occurrence
        features.sort(
            key=lambda f: (
                {"high": 0, "medium": 1, "low": 2}.get(f.confidence, 3),
                f.timestamp_start_sec,
            )
        )

        return features[:20]  # Limit to top 20

    def _generate_timeline_narrative(
        self, segments: list[TimelineSegmentContract], metadata: VideoMetadata
    ) -> str:
        """
        Generate human-readable timeline narrative.

        Note: Structured timeline data is in segments list.
        This narrative is for preview/debugging only.
        """
        if not segments:
            return "Unable to segment video timeline."

        lines = [f"Video duration: {metadata.duration_sec:.1f}s"]

        for i, segment in enumerate(segments):
            duration = segment.end_sec - segment.start_sec
            type_label = segment.segment_type.replace("_", " ").title()

            line = f"{i + 1}. [{type_label}] {segment.start_sec:.1f}s - {segment.end_sec:.1f}s ({duration:.1f}s)"

            if segment.ocr_texts:
                # Show first few OCR texts
                preview = ", ".join(segment.ocr_texts[:3])
                if len(segment.ocr_texts) > 3:
                    preview += f" (+{len(segment.ocr_texts) - 3} more)"
                line += f" | Text: {preview}"

            lines.append(line)

        return "\n".join(lines)

    def _generate_feature_candidates(
        self, features: list[ExtractedFeatureContract]
    ) -> list[str]:
        """Generate top feature names for downstream use."""
        # Prioritize high-confidence features
        high_conf = [f.name for f in features if f.confidence == "high"]
        medium_conf = [f.name for f in features if f.confidence == "medium"]

        candidates = high_conf[:5] + medium_conf[:3]
        return candidates[:8]  # Max 8 candidates

    def _compute_confidence(
        self,
        metadata: VideoMetadata,
        segments: list[TimelineSegmentContract],
        keyframes: list[KeyframeContract],
        ocr_results: dict[str, list[str]],
        features: list[ExtractedFeatureContract],
    ) -> tuple[str, dict[str, Any]]:
        """
        Compute overall analysis confidence from available signals.

        Returns (confidence_level, signals_dict).
        """
        signals: dict[str, Any] = {}

        # Phase 8: Explicit OCR availability signals
        ocr_available = self._check_ocr_available()
        signals["ocr_available"] = ocr_available

        # Signal 1: Resolution quality
        min_dim = min(metadata.width, metadata.height)
        if min_dim >= 1080:
            signals["resolution"] = "high"
            res_score = 1.0
        elif min_dim >= 720:
            signals["resolution"] = "medium"
            res_score = 0.7
        else:
            signals["resolution"] = "low"
            res_score = 0.3

        # Signal 2: Duration appropriateness
        if 15 <= metadata.duration_sec <= 90:
            signals["duration"] = "optimal"
            dur_score = 1.0
        elif 10 <= metadata.duration_sec <= 180:
            signals["duration"] = "acceptable"
            dur_score = 0.7
        else:
            signals["duration"] = "suboptimal"
            dur_score = 0.4

        # Signal 3: Segment detection quality
        if len(segments) >= 3:
            signals["segmentation"] = "good"
            seg_score = 1.0
        elif len(segments) >= 2:
            signals["segmentation"] = "limited"
            seg_score = 0.6
        else:
            signals["segmentation"] = "minimal"
            seg_score = 0.3

        # Signal 4: OCR success (Phase 8: distinguish unavailable vs weak)
        frames_with_text = sum(1 for texts in ocr_results.values() if texts)
        total_text_count = sum(len(texts) for texts in ocr_results.values())

        signals["frames_with_text"] = frames_with_text
        signals["total_ocr_texts"] = total_text_count

        if not ocr_available:
            # OCR unavailable (tesseract not installed)
            signals["ocr_quality"] = "unavailable"
            signals["ocr_useful"] = False
            signals["ocr_text_found"] = False
            ocr_score = 0.0  # No OCR contribution
        elif frames_with_text >= 5 and total_text_count >= 10:
            signals["ocr_quality"] = "good"
            signals["ocr_useful"] = True
            signals["ocr_text_found"] = True
            ocr_score = 1.0
        elif frames_with_text >= 2 and total_text_count >= 3:
            signals["ocr_quality"] = "moderate"
            signals["ocr_useful"] = True
            signals["ocr_text_found"] = True
            ocr_score = 0.6
        elif frames_with_text >= 1 or total_text_count >= 1:
            # OCR ran but found minimal text
            signals["ocr_quality"] = "weak"
            signals["ocr_useful"] = False
            signals["ocr_text_found"] = True
            ocr_score = 0.3
        else:
            # OCR ran but found no text at all
            signals["ocr_quality"] = "none"
            signals["ocr_useful"] = False
            signals["ocr_text_found"] = False
            ocr_score = 0.2

        # Signal 5: Feature extraction quality
        high_conf_features = sum(1 for f in features if f.confidence == "high")
        if high_conf_features >= 3:
            signals["feature_extraction"] = "strong"
            feat_score = 1.0
        elif len(features) >= 3:
            signals["feature_extraction"] = "moderate"
            feat_score = 0.6
        else:
            signals["feature_extraction"] = "weak"
            feat_score = 0.3

        signals["feature_count"] = len(features)
        signals["high_confidence_features"] = high_conf_features

        # Compute weighted average
        # Phase 8: Adjust weights when OCR unavailable to not penalize unfairly
        if ocr_available:
            weights = {
                "resolution": 0.15,
                "duration": 0.10,
                "segmentation": 0.20,
                "ocr": 0.30,
                "features": 0.25,
            }
        else:
            # Redistribute OCR weight when unavailable
            weights = {
                "resolution": 0.20,
                "duration": 0.15,
                "segmentation": 0.30,
                "ocr": 0.0,
                "features": 0.35,
            }

        weighted_score = (
            weights["resolution"] * res_score
            + weights["duration"] * dur_score
            + weights["segmentation"] * seg_score
            + weights["ocr"] * ocr_score
            + weights["features"] * feat_score
        )

        signals["weighted_score"] = round(weighted_score, 3)

        # Map to confidence level
        if weighted_score >= 0.7:
            confidence = "high"
        elif weighted_score >= 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        return confidence, signals
