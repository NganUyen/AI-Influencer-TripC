"""
Shared image-generation pipeline for API routes, skills, and activities.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from services.fal_service import FalAIService
from services.media_storage_service import MediaStorageService

logger = logging.getLogger(__name__)


def _content_type_hint_from_url(value: str) -> str:
    path = urlparse(str(value or "")).path.lower()
    if path.endswith(".jpg") or path.endswith(".jpeg"):
        return "image/jpeg"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith(".png"):
        return "image/png"
    return "image/png"


class ImageGenerationService:
    DEFAULT_MODEL = "fal-ai/nano-banana-2"
    DEFAULT_ASPECT_RATIO = "16:9"
    DEFAULT_SAFETY_TOLERANCE = 2
    DEFAULT_NUM_IMAGES = 1

    def __init__(
        self,
        fal_service: Optional[FalAIService] = None,
        media_storage_service: Optional[MediaStorageService] = None,
    ) -> None:
        self.fal_service = fal_service or FalAIService()
        self.media_storage_service = media_storage_service or MediaStorageService()

    async def _persist_image(
        self,
        *,
        image: Dict[str, Any],
        prompt: str,
        model: str,
        image_index: int,
        base_file_name_hint: Optional[str],
        campaign_id: Optional[str],
        user_id: Optional[str],
        owner_key: Optional[str],
        persona_id: Optional[str],
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        source_url = str(image.get("url") or "").strip()
        if not source_url:
            return {
                "storage_url": None,
                "storage_key": None,
                "storage_status": "source_only",
            }

        resolved_user_id = user_id
        destination_path = None
        file_name_hint = base_file_name_hint or "generated-image"
        if metadata.get("requested_num_images", self.DEFAULT_NUM_IMAGES) > 1:
            file_name_hint = f"{file_name_hint}-{image_index + 1:02d}"

        try:
            resolved_user_id = await self.media_storage_service._resolve_user_id(
                user_id=user_id,
                owner_key=owner_key,
                campaign_id=campaign_id,
                persona_id=persona_id,
            )
            destination_path = self.media_storage_service._build_destination_path(
                asset_type="IMAGE",
                user_id=resolved_user_id,
                persona_id=persona_id,
                content_type=_content_type_hint_from_url(source_url),
                file_name_hint=file_name_hint,
            )
        except Exception as exc:
            logger.warning(
                "Could not pre-resolve image storage path for %s: %s",
                source_url,
                exc,
            )

        storage_result = await self.media_storage_service.upload_from_url(
            url=source_url,
            destination_path=destination_path,
            campaign_id=campaign_id,
            asset_type="IMAGE",
            generation_prompt=prompt,
            user_id=resolved_user_id,
            owner_key=owner_key,
            persona_id=persona_id,
            metadata={
                **metadata,
                "provider": "fal_ai",
                "model": model,
                "image_index": image_index,
            },
            file_name_hint=file_name_hint,
        )

        if storage_result:
            if isinstance(storage_result, dict):
                storage_url = storage_result.get("access_url") or storage_result.get("url")
                storage_key = storage_result.get("storage_path") or destination_path
                media_asset_id = storage_result.get("media_asset_id")
            else:
                storage_url = str(storage_result)
                storage_key = destination_path
                media_asset_id = None
            return {
                "storage_url": storage_url,
                "storage_key": storage_key,
                "storage_status": "stored",
                "media_asset_id": media_asset_id,
            }

        logger.warning(
            "Image generation storage fallback engaged for image %s (%s)",
            image_index,
            source_url,
        )
        return {
            "storage_url": None,
            "storage_key": None,
            "storage_status": "source_only",
            "media_asset_id": None,
        }

    async def generate_images(
        self,
        *,
        prompt: str,
        model: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        safety_tolerance: Optional[int] = None,
        num_images: Optional[int] = None,
        campaign_id: Optional[str] = None,
        user_id: Optional[str] = None,
        owner_key: Optional[str] = None,
        persona_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        file_name_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("prompt is required")

        normalized_model = (model or self.DEFAULT_MODEL).strip() or self.DEFAULT_MODEL
        normalized_ratio = (aspect_ratio or self.DEFAULT_ASPECT_RATIO).strip() or self.DEFAULT_ASPECT_RATIO
        normalized_safety = int(safety_tolerance or self.DEFAULT_SAFETY_TOLERANCE)
        normalized_count = max(1, int(num_images or self.DEFAULT_NUM_IMAGES))
        request_metadata = dict(metadata or {})
        request_metadata.setdefault("requested_num_images", normalized_count)
        request_metadata.setdefault("aspect_ratio", normalized_ratio)

        raw = await self.fal_service.generate_image(
            prompt=normalized_prompt,
            model=normalized_model,
            aspect_ratio=normalized_ratio,
            safety_tolerance=normalized_safety,
            num_images=normalized_count,
        )

        raw_images = list(raw.get("images") or [])
        if not raw_images and raw.get("url"):
            raw_images = [
                {
                    "url": raw.get("url"),
                    "width": raw.get("width"),
                    "height": raw.get("height"),
                }
            ]

        if not raw_images:
            raise ValueError("Image provider returned no images")

        persisted = await asyncio.gather(
            *[
                self._persist_image(
                    image=image,
                    prompt=normalized_prompt,
                    model=normalized_model,
                    image_index=index,
                    base_file_name_hint=file_name_hint,
                    campaign_id=campaign_id,
                    user_id=user_id,
                    owner_key=owner_key,
                    persona_id=persona_id,
                    metadata=request_metadata,
                )
                for index, image in enumerate(raw_images)
            ]
        )

        source_images = []
        images = []
        persisted_count = 0

        for index, image in enumerate(raw_images):
            source_url = image.get("url")
            source_item = {
                "url": source_url,
                "width": image.get("width"),
                "height": image.get("height"),
                "index": index,
            }
            source_images.append(source_item)

            persisted_item = persisted[index]
            chosen_url = persisted_item.get("storage_url") or source_url
            if persisted_item.get("storage_url"):
                persisted_count += 1

            images.append(
                {
                    "url": chosen_url,
                    "source_url": source_url,
                    "storage_url": persisted_item.get("storage_url"),
                    "storage_key": persisted_item.get("storage_key"),
                    "media_asset_id": persisted_item.get("media_asset_id"),
                    "width": image.get("width"),
                    "height": image.get("height"),
                    "index": index,
                    "storage_status": persisted_item.get("storage_status"),
                }
            )

        primary = images[0]
        if persisted_count == len(images):
            storage_status = "stored"
        elif persisted_count:
            storage_status = "partial"
        else:
            storage_status = "source_only"

        response_metadata = {
            **request_metadata,
            "user_id": user_id,
            "owner_key": owner_key,
            "persona_id": persona_id,
            "campaign_id": campaign_id,
            "persisted_count": persisted_count,
            "source_count": len(images),
            "storage_status": storage_status,
        }

        return {
            "url": primary.get("url"),
            "source_url": primary.get("source_url"),
            "storage_url": primary.get("storage_url"),
            "storage_key": primary.get("storage_key"),
            "media_asset_id": primary.get("media_asset_id"),
            "width": primary.get("width"),
            "height": primary.get("height"),
            "images": images,
            "source_images": source_images,
            "storage_urls": [item.get("storage_url") for item in images],
            "storage_keys": [item.get("storage_key") for item in images],
            "model": normalized_model,
            "prompt": normalized_prompt,
            "num_images": len(images),
            "storage_status": storage_status,
            "metadata": {key: value for key, value in response_metadata.items() if value is not None},
        }

    async def close(self) -> None:
        await self.fal_service.close()
