"""
Frame Understanding Service (Phase 3b - V3.1)

Analyzes keyframes using GPT-4o mini vision model to understand screen content.
"""

import logging
import base64
from typing import List, Optional

from services.contracts import (
    FrameUnderstandingContract,
    KeyframeContract,
    TimelineSegmentContract,
)
from services.ai_service import AIService

logger = logging.getLogger(__name__)


class FrameUnderstandingService:
    """
    Analyzes video keyframes to understand screen content and user journey.

    Uses GPT-4o mini vision model for structured frame analysis.
    """

    MAX_FRAMES_TOTAL = 10  # Hard cap across all segments
    MAX_FRAMES_PER_SEGMENT = 2

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def analyze_frames(
        self,
        keyframes: List[KeyframeContract],
        segments: List[TimelineSegmentContract],
        user_video_thesis: Optional[str] = None,
    ) -> List[FrameUnderstandingContract]:
        """
        Analyze keyframes to understand screen content.

        Args:
            keyframes: List of extracted keyframes
            segments: Timeline segments
            user_video_thesis: User's description of what video demonstrates

        Returns:
            List of FrameUnderstandingContract (may have gaps for failed segments)
        """
        if not keyframes:
            logger.warning("No keyframes to analyze")
            return []

        # Sample frames: max 2 per segment, hard cap 10 total
        sampled_frames = self._sample_frames(keyframes, segments)

        if not sampled_frames:
            logger.warning("No frames after sampling")
            return []

        logger.info(
            f"Analyzing {len(sampled_frames)} frames (from {len(keyframes)} total)"
        )

        understandings = []

        for frame_info in sampled_frames:
            frame = frame_info["frame"]
            segment_idx = frame_info["segment_idx"]

            try:
                understanding = await self._analyze_single_frame(
                    frame, segment_idx, user_video_thesis
                )
                understandings.append(understanding)

            except Exception as e:
                logger.warning(
                    f"Failed to analyze frame {frame.frame_id} for segment {segment_idx}: {e}"
                )
                # Skip this frame, continue with others
                continue

        logger.info(f"Successfully analyzed {len(understandings)} frames")
        return understandings

    def _sample_frames(
        self,
        keyframes: List[KeyframeContract],
        segments: List[TimelineSegmentContract],
    ) -> List[dict]:
        """
        Sample frames: max 2 per segment, max 10 total.

        Returns:
            List of {frame, segment_idx} dicts
        """
        # Map keyframes to segments
        frame_to_segment = {}
        for idx, segment in enumerate(segments):
            for frame in keyframes:
                if segment.start_sec <= frame.timestamp_sec < segment.end_sec:
                    if frame.frame_id not in frame_to_segment:
                        frame_to_segment[frame.frame_id] = idx

        # Group frames by segment
        segment_frames = {}
        for frame in keyframes:
            segment_idx = frame_to_segment.get(frame.frame_id)
            if segment_idx is not None:
                if segment_idx not in segment_frames:
                    segment_frames[segment_idx] = []
                segment_frames[segment_idx].append(frame)

        # Sample up to 2 frames per segment
        sampled = []
        for segment_idx in sorted(segment_frames.keys()):
            frames = segment_frames[segment_idx][: self.MAX_FRAMES_PER_SEGMENT]
            for frame in frames:
                sampled.append({"frame": frame, "segment_idx": segment_idx})

        # Hard cap at 10 total
        if len(sampled) > self.MAX_FRAMES_TOTAL:
            # Distribute evenly across segments
            step = len(sampled) / self.MAX_FRAMES_TOTAL
            indices = [int(i * step) for i in range(self.MAX_FRAMES_TOTAL)]
            sampled = [sampled[i] for i in indices]

        return sampled

    async def _analyze_single_frame(
        self,
        frame: KeyframeContract,
        segment_idx: int,
        user_video_thesis: Optional[str],
    ) -> FrameUnderstandingContract:
        """
        Analyze a single frame using GPT-4o mini vision.

        Returns:
            FrameUnderstandingContract
        """
        # Read image and encode to base64
        image_base64 = self._load_frame_image(frame)

        context = (
            f"Context about the video: {user_video_thesis}"
            if user_video_thesis
            else "No context provided"
        )

        system_prompt = f"""Analyze this mobile app screen recording frame.
{context}
Return ONLY valid JSON, no markdown, no explanation."""

        user_prompt = """Return JSON:
{
  "screen_type": "dashboard|form|modal|confirmation|onboarding|list|other",
  "primary_action": "short description of what user is doing",
  "feature_demonstrated": "feature name if clear, else null",
  "journey_stage": "discover|configure|confirm|complete|unclear",
  "key_ui_text": ["visible button/label text relevant to feature"],
  "confidence": 0.0-1.0
}"""

        result = await self.ai_service.analyze_image_structured(
            image_base64=image_base64,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return FrameUnderstandingContract(
            segment_idx=segment_idx,
            screen_type=result.get("screen_type", "other"),
            primary_action=result.get("primary_action", ""),
            feature_demonstrated=result.get("feature_demonstrated"),
            journey_stage=result.get("journey_stage", "unclear"),
            key_ui_text=result.get("key_ui_text", []),
            confidence=float(result.get("confidence", 0.0)),
        )

    @staticmethod
    def _load_frame_image(frame: KeyframeContract) -> str:
        """
        Load frame image and encode to base64.

        Returns:
            Base64-encoded image string
        """
        # Priority: use image_path if available, otherwise image_url
        if frame.image_path:
            with open(frame.image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        elif frame.image_url:
            # For remote URLs, download and encode
            import httpx
            import asyncio

            async def fetch_url():
                async with httpx.AsyncClient() as client:
                    response = await client.get(frame.image_url)
                    response.raise_for_status()
                    return base64.b64encode(response.content).decode("utf-8")

            return asyncio.run(fetch_url())
        else:
            raise ValueError(f"Frame {frame.frame_id} has no image_path or image_url")
