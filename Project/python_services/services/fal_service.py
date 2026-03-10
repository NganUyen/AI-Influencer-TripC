"""
fal.ai Service Integration
Media generation using 600+ models (Flux.1, SDXL, etc.)
"""

import httpx
import logging
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class FalAIService:
    """
    Integration with fal.ai for AI-powered image and video generation
    Provides access to models like Flux.1 Pro/Schnell, SDXL, and video models
    """

    def __init__(self):
        self.api_key = settings.FAL_API_KEY
        self.client = httpx.AsyncClient(
            base_url="https://fal.run",
            headers={"Authorization": f"Key {self.api_key}"},
            timeout=300.0,  # 5 minutes for generation
        )

    async def generate_image(
        self,
        prompt: str,
        model: str = "fal-ai/flux-pro",
        aspect_ratio: str = "16:9",
        safety_tolerance: int = 2,
        num_images: int = 1,
    ) -> Dict[str, Any]:
        """
        Generate images using fal.ai models

        Args:
            prompt: Image generation prompt
            model: Model to use (flux-pro, flux-schnell, sdxl, etc.)
            aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, etc.)
            safety_tolerance: Safety filter tolerance (1-6)
            num_images: Number of images to generate
        """
        logger.info(f"Generating image with {model}")

        payload = {
            "prompt": prompt,
            "image_size": {"aspect_ratio": aspect_ratio},
            "safety_tolerance": safety_tolerance,
            "num_images": num_images,
        }

        try:
            response = await self.client.post(f"/api/{model}", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Image generated successfully: {result.get('images', [{}])[0].get('url')}"
            )

            return {
                "url": result.get("images", [{}])[0].get("url"),
                "width": result.get("images", [{}])[0].get("width"),
                "height": result.get("images", [{}])[0].get("height"),
                "model": model,
                "prompt": prompt,
            }

        except httpx.HTTPError as e:
            logger.error(f"Image generation failed: {str(e)}")
            raise

    async def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        fps: int = 24,
        model: str = "fal-ai/runway-gen3",
    ) -> Dict[str, Any]:
        """
        Generate video using fal.ai video models

        Args:
            prompt: Video generation prompt
            duration: Video duration in seconds
            fps: Frames per second
            model: Video model to use
        """
        logger.info(f"Generating video with {model}")

        payload = {"prompt": prompt, "duration": duration, "fps": fps}

        try:
            response = await self.client.post(f"/api/{model}", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Video generated successfully: {result.get('video', {}).get('url')}"
            )

            return {
                "url": result.get("video", {}).get("url"),
                "duration": duration,
                "fps": fps,
                "model": model,
                "prompt": prompt,
            }

        except httpx.HTTPError as e:
            logger.error(f"Video generation failed: {str(e)}")
            raise

    async def upscale_image(self, image_url: str, scale: int = 2) -> Dict[str, Any]:
        """Upscale an image"""
        logger.info(f"Upscaling image by {scale}x")

        try:
            response = await self.client.post(
                "/api/fal-ai/creative-upscaler",
                json={"image_url": image_url, "scale": scale},
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Image upscaling failed: {str(e)}")
            raise

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
