"""
Carousel generation service.

Builds a complete carousel artifact by generating slide strategy, creating slide
images, overlaying text, and uploading the finalized assets to storage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

from services.contracts import CarouselArtifact, CarouselSlideContract
from services.fal_service import FalAIService
from services.persona_registry_service import PersonaRegistryService
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


def _slugify(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    normalized = normalized.strip("_")
    return normalized or fallback


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    font_names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
    ]
    for font_name in font_names:
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> List[str]:
    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines


def _render_text_overlay(
    image_bytes: bytes,
    caption: str,
    cta_overlay: Optional[str],
) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = image.size

    if not caption and not cta_overlay:
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    footer_height = max(int(height * 0.28), 220)
    footer_top = height - footer_height
    draw.rounded_rectangle(
        [(int(width * 0.05), footer_top), (int(width * 0.95), int(height * 0.96))],
        radius=28,
        fill=(12, 16, 24, 205),
    )

    caption_font = _load_font(max(int(width * 0.055), 26), bold=True)
    cta_font = _load_font(max(int(width * 0.028), 18), bold=False)
    max_text_width = int(width * 0.78)
    caption_lines = _wrap_text(draw, caption, caption_font, max_text_width)

    if caption_lines:
        line_heights = [
            draw.textbbox((0, 0), line, font=caption_font)[3]
            - draw.textbbox((0, 0), line, font=caption_font)[1]
            for line in caption_lines
        ]
        line_gap = max(int(width * 0.012), 10)
        total_height = sum(line_heights) + line_gap * max(len(caption_lines) - 1, 0)
        text_y = footer_top + max(int(footer_height * 0.15), 24)
        text_x = int(width * 0.11)
        for index, line in enumerate(caption_lines):
            draw.text(
                (text_x, text_y),
                line,
                font=caption_font,
                fill=(255, 255, 255, 255),
            )
            text_y += line_heights[index] + line_gap

    if cta_overlay:
        cta_text = cta_overlay.strip()
        cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        cta_width = cta_bbox[2] - cta_bbox[0]
        cta_height = cta_bbox[3] - cta_bbox[1]
        pill_padding_x = max(int(width * 0.025), 18)
        pill_padding_y = 10
        pill_x2 = int(width * 0.89)
        pill_x1 = pill_x2 - cta_width - pill_padding_x * 2
        pill_y1 = int(height * 0.08)
        pill_y2 = pill_y1 + cta_height + pill_padding_y * 2
        draw.rounded_rectangle(
            [(pill_x1, pill_y1), (pill_x2, pill_y2)],
            radius=22,
            fill=(255, 255, 255, 230),
        )
        draw.text(
            (pill_x1 + pill_padding_x, pill_y1 + pill_padding_y - 1),
            cta_text,
            font=cta_font,
            fill=(18, 24, 33, 255),
        )

    final_image = Image.alpha_composite(image, overlay).convert("RGB")
    output = BytesIO()
    final_image.save(output, format="PNG")
    return output.getvalue()


class CarouselService:
    """Generate complete carousel artifacts for feature/post workflows."""

    async def _resolve_persona(self, persona_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not persona_id:
            return None
        persona = await PersonaRegistryService.get_persona(persona_id)
        if not persona:
            raise ValueError(f"Persona '{persona_id}' was not found.")
        return persona

    def _build_persona_config(
        self,
        persona: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        language = payload.get("language")
        if not language and persona:
            language = persona.get("language")
        return {
            "language_name": language or "English",
            "skin_color": payload.get("skin_color") or "diverse",
            "display_name": persona.get("display_name") if persona else None,
        }

    async def generate_carousel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from activities.strategy_activities import generate_carousel_strategy

        persona = await self._resolve_persona(payload.get("persona_id"))
        persona_config = self._build_persona_config(persona, payload)

        planning_input = {
            "app_name": payload.get("app_name") or "TripC",
            "topic": payload["topic"],
            "platform": payload.get("platform", "instagram"),
            "num_slides": int(payload.get("num_slides", 8)),
            "tone": payload.get("tone"),
            "style": payload.get("style"),
            "freeform_brief": payload.get("freeform_brief"),
            "creative_notes": payload.get("creative_notes"),
            "persona_config": persona_config,
            "model": payload.get("planning_model", "models/gemini-2.0-flash"),
        }
        plan = await generate_carousel_strategy(planning_input)
        slides = list(plan.get("slides") or [])
        if not slides:
            raise ValueError("Carousel strategy did not return any slides.")

        storage = StorageService()
        fal = FalAIService()
        download_client = httpx.AsyncClient(timeout=120.0)
        batch_id = _utc_timestamp()
        topic_slug = _slugify(payload["topic"], "carousel")
        app_slug = _slugify(payload.get("app_name") or "tripc", "tripc")
        platform_slug = _slugify(payload.get("platform", "instagram"), "platform")
        storage_prefix = f"carousels/{app_slug}/{platform_slug}/{topic_slug}/{batch_id}"

        async def process_slide(slide: Dict[str, Any]) -> CarouselSlideContract:
            slide_num = int(slide.get("slide_num") or 0)
            if slide_num <= 0:
                raise ValueError("Carousel slide is missing a valid slide_num.")
            image_prompt = str(slide.get("image_prompt") or "").strip()
            if not image_prompt:
                raise ValueError(f"Carousel slide {slide_num} is missing image_prompt.")

            image_result = await fal.generate_image(
                prompt=image_prompt,
                model=payload.get("image_model", "fal-ai/nano-banana-2"),
                aspect_ratio=payload.get("aspect_ratio", "4:5"),
                safety_tolerance=int(payload.get("safety_tolerance", 2)),
            )

            response = await download_client.get(image_result["url"])
            response.raise_for_status()
            overlay_enabled = bool(payload.get("include_text_overlay", True))
            final_bytes = (
                _render_text_overlay(
                    response.content,
                    caption=str(slide.get("caption") or "").strip(),
                    cta_overlay=(slide.get("cta_overlay") or "").strip() or None,
                )
                if overlay_enabled
                else response.content
            )

            storage_key = f"{storage_prefix}/slide_{slide_num:02d}.png"
            image_url = await storage.upload_bytes(
                data=final_bytes,
                filename=storage_key,
                content_type="image/png",
                metadata={
                    "topic": topic_slug,
                    "platform": platform_slug,
                    "slide_num": str(slide_num),
                },
            )

            return CarouselSlideContract(
                slide_num=slide_num,
                image_prompt=image_prompt,
                caption=str(slide.get("caption") or "").strip(),
                cta_overlay=(slide.get("cta_overlay") or "").strip() or None,
                image_url=image_url,
                source_image_url=image_result["url"],
                storage_key=storage_key,
                metadata={
                    "model": image_result.get("model"),
                    "aspect_ratio": payload.get("aspect_ratio", "4:5"),
                    "overlay_applied": overlay_enabled,
                },
            )

        try:
            rendered_slides = await asyncio.gather(*(process_slide(slide) for slide in slides))
        finally:
            await fal.close()
            await download_client.aclose()

        artifact = CarouselArtifact(
            app_name=planning_input["app_name"],
            topic=payload["topic"],
            platform=planning_input["platform"],
            persona_id=payload.get("persona_id"),
            slides=rendered_slides,
            platform_caption=str(plan.get("platform_caption") or "").strip(),
            hashtags=[str(item) for item in (plan.get("hashtags") or []) if str(item).strip()],
            metadata={
                "slide_count": len(rendered_slides),
                "tone": payload.get("tone"),
                "style": payload.get("style"),
                "freeform_brief": payload.get("freeform_brief"),
                "creative_notes": payload.get("creative_notes"),
                "storage_prefix": storage_prefix,
                "persona_config": persona_config,
            },
        )

        manifest_key = f"{storage_prefix}/manifest.json"
        manifest_payload = artifact.model_dump(mode="json")
        manifest_url = await storage.upload_bytes(
            data=json.dumps(manifest_payload, ensure_ascii=False, indent=2).encode("utf-8"),
            filename=manifest_key,
            content_type="application/json",
            metadata={"topic": topic_slug, "platform": platform_slug},
        )
        manifest_payload["manifest_url"] = manifest_url
        manifest_payload["metadata"]["manifest_storage_key"] = manifest_key
        return manifest_payload
