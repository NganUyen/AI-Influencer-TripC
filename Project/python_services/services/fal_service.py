"""
fal.ai Service Integration
Media generation using 600+ models (Flux.1, SDXL, etc.)
"""

import httpx
import logging
from typing import Dict, Any, Optional
from config.settings import settings
from services.quota_monitor_service import QuotaMonitorService

logger = logging.getLogger(__name__)

class FalAIService:
    """
    Integration with fal.ai for AI-powered image and video generation
    Provides access to models like Flux.1 Pro/Schnell, SDXL, and video models
    """
    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_client(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                base_url="https://fal.run",
                headers={"Authorization": f"Key {settings.FAL_AI_API_KEY}"},
                timeout=300.0,
            )
        return cls._client

    def __init__(self):
        self.api_key = settings.FAL_AI_API_KEY
        self.client = self._get_client()

    @staticmethod
    def _build_image_payload(
        *,
        model: str,
        prompt: str,
        aspect_ratio: str,
        safety_tolerance: int,
        num_images: int,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "safety_tolerance": safety_tolerance,
            "num_images": num_images,
        }
        if "nano-banana" in str(model or ""):
            payload["aspect_ratio"] = aspect_ratio
        else:
            payload["image_size"] = {"aspect_ratio": aspect_ratio}
        return payload

    async def _record_usage(
        self,
        operation: str,
        model: str,
        usage: Dict[str, Any],
        error: Exception | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        quota_metadata = {
            "service": "fal_ai_service",
            "operation": operation,
            "model": model,
            "status": "error" if error else "success",
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="fal_ai",
            usage=usage,
            metadata=quota_metadata,
        )

    async def generate_image(
        self,
        prompt: str,
        model: str = "fal-ai/nano-banana-2",
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

        payload = self._build_image_payload(
            model=model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            safety_tolerance=safety_tolerance,
            num_images=num_images,
        )

        try:
            response = await self.client.post(f"/{model}", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Image generated successfully: {result.get('images', [{}])[0].get('url')}"
            )
            await self._record_usage(
                operation="generate_image",
                model=model,
                usage={"requests": 1, "images": num_images},
                metadata={"aspect_ratio": aspect_ratio},
            )

            images = result.get("images", [])
            first_img = images[0] if images else {}
            
            return {
                "url": first_img.get("url"),
                "width": first_img.get("width"),
                "height": first_img.get("height"),
                "images": images,
                "model": model,
                "prompt": prompt,
            }

        except httpx.HTTPError as e:
            await self._record_usage(
                operation="generate_image",
                model=model,
                usage={"requests": 1, "images": num_images},
                error=e,
                metadata={"aspect_ratio": aspect_ratio},
            )
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
            response = await self.client.post(f"/{model}", json=payload)
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Video generated successfully: {result.get('video', {}).get('url')}"
            )
            await self._record_usage(
                operation="generate_video",
                model=model,
                usage={"requests": 1, "videos": 1, "seconds": duration},
                metadata={"fps": fps},
            )

            return {
                "url": result.get("video", {}).get("url"),
                "duration": duration,
                "fps": fps,
                "model": model,
                "prompt": prompt,
            }

        except httpx.HTTPError as e:
            await self._record_usage(
                operation="generate_video",
                model=model,
                usage={"requests": 1, "videos": 1, "seconds": duration},
                error=e,
                metadata={"fps": fps},
            )
            logger.error(f"Video generation failed: {str(e)}")
            raise

    async def upscale_image(self, image_url: str, scale: int = 2) -> Dict[str, Any]:
        """Upscale an image"""
        logger.info(f"Upscaling image by {scale}x")

        try:
            response = await self.client.post(
                "/fal-ai/creative-upscaler",
                json={"image_url": image_url, "scale": scale},
            )
            response.raise_for_status()
            await self._record_usage(
                operation="upscale_image",
                model="fal-ai/creative-upscaler",
                usage={"requests": 1, "upscales": 1},
                metadata={"scale": scale},
            )

            return response.json()

        except httpx.HTTPError as e:
            await self._record_usage(
                operation="upscale_image",
                model="fal-ai/creative-upscaler",
                usage={"requests": 1, "upscales": 1},
                error=e,
                metadata={"scale": scale},
            )
            logger.error(f"Image upscaling failed: {str(e)}")
            raise

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
