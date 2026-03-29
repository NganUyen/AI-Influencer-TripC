from io import BytesIO

import pytest
import httpx
from fastapi import FastAPI
from fastapi import HTTPException
from PIL import Image

from api import media


class _StubImageGenerationService:
    def __init__(self, response):
        self.calls = []
        self.response = response
        self.closed = False

    async def generate_images(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def close(self):
        self.closed = True


class _StubGoogleTTSService:
    def __init__(self):
        self.calls = []

    @staticmethod
    def resolve_voice_name(voice: str, language: str | None = None):
        mapping = {
            "male_friendly": "vi-VN-Wavenet-D",
            "female_warm": "vi-VN-Wavenet-A",
        }
        return mapping.get(voice, voice)

    async def generate_audio(
        self,
        text: str,
        voice: str,
        speaking_rate: float = 1.0,
        pitch: float = 0.0,
    ):
        self.calls.append(
            {
                "text": text,
                "voice": voice,
                "speaking_rate": speaking_rate,
                "pitch": pitch,
            }
        )
        return b"mp3-bytes"

    def get_voices(self):
        return {
            "male_friendly": "vi-VN-Wavenet-D",
            "female_warm": "vi-VN-Wavenet-A",
        }


@pytest.mark.asyncio
async def test_generate_image_route_uses_shared_service_and_preserves_contract(monkeypatch):
    stub = _StubImageGenerationService(
        {
            "url": "https://storage.example/images/primary.png",
            "source_url": "https://fal.example/images/primary.png",
            "storage_url": "https://storage.example/images/primary.png",
            "storage_key": "users/demo/personas/hero/image/2026-03/primary.png",
            "images": [
                {
                    "url": "https://storage.example/images/primary.png",
                    "source_url": "https://fal.example/images/primary.png",
                    "storage_url": "https://storage.example/images/primary.png",
                    "storage_key": "users/demo/personas/hero/image/2026-03/primary.png",
                    "storage_status": "stored",
                }
            ],
            "source_images": [{"url": "https://fal.example/images/primary.png"}],
            "model": "fal-ai/nano-banana-2",
            "prompt": "TripC hero image",
            "storage_status": "stored",
            "metadata": {"owner_key": "telegram:123", "persona_id": "hero"},
        }
    )

    monkeypatch.setattr(media, "ImageGenerationService", lambda: stub)

    result = await media.generate_image(
        media.ImageGenerateRequest(
            prompt="TripC hero image",
            owner_key="telegram:123",
            persona_id="hero",
            num_images=1,
            metadata={"source": "test"},
        )
    )

    assert result["url"] == "https://storage.example/images/primary.png"
    assert result["source_url"] == "https://fal.example/images/primary.png"
    assert result["storage_url"] == "https://storage.example/images/primary.png"
    assert result["images"][0]["storage_status"] == "stored"
    assert stub.calls[0]["owner_key"] == "telegram:123"
    assert stub.calls[0]["persona_id"] == "hero"
    assert stub.calls[0]["metadata"] == {"source": "test"}
    assert stub.closed is True


@pytest.mark.asyncio
async def test_generate_image_route_returns_source_url_when_storage_falls_back(monkeypatch):
    stub = _StubImageGenerationService(
        {
            "url": "https://fal.example/images/fallback.png",
            "source_url": "https://fal.example/images/fallback.png",
            "storage_url": None,
            "storage_key": None,
            "images": [
                {
                    "url": "https://fal.example/images/fallback.png",
                    "source_url": "https://fal.example/images/fallback.png",
                    "storage_url": None,
                    "storage_key": None,
                    "storage_status": "source_only",
                }
            ],
            "source_images": [{"url": "https://fal.example/images/fallback.png"}],
            "model": "fal-ai/nano-banana-2",
            "prompt": "Fallback image",
            "storage_status": "source_only",
            "metadata": {"persisted_count": 0},
        }
    )

    monkeypatch.setattr(media, "ImageGenerationService", lambda: stub)

    result = await media.generate_image(
        media.ImageGenerateRequest(prompt="Fallback image")
    )

    assert result["url"] == "https://fal.example/images/fallback.png"
    assert result["storage_url"] is None
    assert result["images"][0]["storage_status"] == "source_only"
    assert stub.closed is True


@pytest.mark.asyncio
async def test_generate_audio_returns_summary(monkeypatch):
    stub_service = _StubGoogleTTSService()
    monkeypatch.setattr(media, "GoogleTTSService", lambda: stub_service)

    result = await media.generate_audio(
        media.AudioGenerateRequest(text="Xin chao", voice="male_friendly")
    )

    assert stub_service.calls == [
        {
            "text": "Xin chao",
            "voice": "vi-VN-Wavenet-D",
            "speaking_rate": 1.05,
            "pitch": 0.0,
        }
    ]
    assert result["voice"] == "vi-VN-Wavenet-D"
    assert result["audio_bytes_length"] == len(b"mp3-bytes")
    assert result["text_length"] == len("Xin chao")


@pytest.mark.asyncio
async def test_generate_audio_converts_errors(monkeypatch):
    class _FailingGoogleTTSService:
        async def generate_audio(
            self,
            text: str,
            voice: str,
            speaking_rate: float = 1.0,
            pitch: float = 0.0,
        ):
            raise RuntimeError("tts unavailable")

        def get_voices(self):
            return {}

    monkeypatch.setattr(media, "GoogleTTSService", lambda: _FailingGoogleTTSService())

    with pytest.raises(HTTPException) as exc:
        await media.generate_audio(
            media.AudioGenerateRequest(text="Xin chao", voice="vi-VN-Wavenet-D")
        )

    assert exc.value.status_code == 500
    assert "tts unavailable" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_carousel_service_builds_slide_assets(monkeypatch):
    planning_calls = []
    uploaded = []

    async def fake_generate_carousel_strategy(config):
        planning_calls.append(config)
        return {
            "slides": [
                {
                    "slide_num": 1,
                    "image_prompt": "Feature hero prompt",
                    "caption": "One tap planning",
                    "cta_overlay": "Swipe for more",
                },
                {
                    "slide_num": 2,
                    "image_prompt": "Workflow prompt",
                    "caption": "Auto schedule routes",
                    "cta_overlay": "",
                },
            ],
            "platform_caption": "Meet the TripC workflow lane",
            "hashtags": ["#tripc", "#traveltools"],
        }

    class _StubFalService:
        async def generate_image(self, prompt: str, model: str, aspect_ratio: str, safety_tolerance: int):
            return {
                "url": f"https://fal.example/{prompt.replace(' ', '_')}.png",
                "model": model,
            }

        async def close(self):
            return None

    class _StubStorageService:
        async def upload_bytes(self, data, filename, content_type="application/octet-stream", metadata=None):
            uploaded.append(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "metadata": metadata,
                    "size": len(data),
                }
            )
            return f"https://cdn.example/{filename}"

    class _StubResponse:
        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self):
            return None

    class _StubDownloadClient:
        async def get(self, url):
            image = Image.new("RGB", (1080, 1350), color=(32, 64, 128))
            output = BytesIO()
            image.save(output, format="PNG")
            return _StubResponse(output.getvalue())

        async def aclose(self):
            return None

    async def fake_get_persona(persona_id: str):
        return {
            "persona_id": persona_id,
            "language": "Vietnamese",
            "display_name": "Minh",
        }

    monkeypatch.setattr(
        "activities.strategy_activities.generate_carousel_strategy",
        fake_generate_carousel_strategy,
    )
    monkeypatch.setattr("services.carousel_service.FalAIService", _StubFalService)
    monkeypatch.setattr("services.carousel_service.StorageService", _StubStorageService)
    monkeypatch.setattr("services.carousel_service.httpx.AsyncClient", lambda **_: _StubDownloadClient())
    monkeypatch.setattr("services.carousel_service.PersonaRegistryService.get_persona", fake_get_persona)

    service = media.CarouselService()
    result = await service.generate_carousel(
        {
            "app_name": "TripC",
            "topic": "Showcase smart itinerary planner",
            "platform": "instagram",
            "persona_id": "minh_vn",
            "tone": "confident",
            "style": "clean product storytelling",
            "num_slides": 2,
            "freeform_brief": "Focus on product features",
            "creative_notes": "Use concise punchy copy",
        }
    )

    assert planning_calls[0]["persona_config"]["language_name"] == "Vietnamese"
    assert planning_calls[0]["tone"] == "confident"
    assert planning_calls[0]["style"] == "clean product storytelling"
    assert result["type"] == "carousel"
    assert result["platform_caption"] == "Meet the TripC workflow lane"
    assert result["slides"][0]["caption"] == "One tap planning"
    assert result["slides"][0]["image_url"].startswith("https://cdn.example/carousels/")
    assert result["slides"][0]["source_image_url"].startswith("https://fal.example/")
    assert result["metadata"]["slide_count"] == 2
    assert result["manifest_url"].endswith("/manifest.json")
    assert len(uploaded) == 3
    assert uploaded[0]["filename"].endswith("slide_01.png")
    assert uploaded[1]["filename"].endswith("slide_02.png")
    assert uploaded[2]["filename"].endswith("manifest.json")


@pytest.mark.asyncio
async def test_generate_carousel_endpoint_returns_artifact(monkeypatch):
    async def fake_generate_carousel(self, payload):
        return {
            "type": "carousel",
            "topic": payload["topic"],
            "platform": payload["platform"],
            "slides": [
                {
                    "slide_num": 1,
                    "image_prompt": "Feature prompt",
                    "caption": "Fast route planning",
                    "cta_overlay": "Swipe",
                    "image_url": "https://cdn.example/slide-1.png",
                    "source_image_url": "https://fal.example/source-1.png",
                    "storage_key": "carousels/test/slide_01.png",
                    "metadata": {"overlay_applied": True},
                }
            ],
            "platform_caption": "Try the new route planner",
            "hashtags": ["#tripc"],
            "status": "completed",
            "metadata": {"slide_count": 1},
            "manifest_url": "https://cdn.example/carousels/test/manifest.json",
        }

    monkeypatch.setattr(media.CarouselService, "generate_carousel", fake_generate_carousel)

    app = FastAPI()
    app.include_router(media.router, prefix="/api/media")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/media/carousel",
            json={
                "topic": "Launch smart route planning",
                "platform": "instagram",
                "num_slides": 3,
            },
            headers={"x-internal-api-token": "test-internal-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "carousel"
    assert payload["slides"][0]["image_url"] == "https://cdn.example/slide-1.png"
    assert payload["manifest_url"].endswith("/manifest.json")
