import base64
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from api import media
from services.carousel_service import CarouselService


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(media.router, prefix="/api/media")
    return TestClient(app)


class _StubGoogleTTSService:
    def __init__(self):
        self.calls = []

    async def generate_audio(self, text: str, voice: str):
        self.calls.append({"text": text, "voice": voice})
        return b"mp3-bytes"

    def get_voices(self):
        return {
            "male_friendly": "vi-VN-Wavenet-D",
            "female_warm": "vi-VN-Wavenet-A",
        }


@pytest.mark.asyncio
async def test_generate_audio_maps_named_voice(monkeypatch):
    stub_service = _StubGoogleTTSService()
    monkeypatch.setattr(media, "GoogleTTSService", lambda: stub_service)

    result = await media.generate_audio(
        media.AudioGenerateRequest(text="Xin chao", voice_id="male_friendly")
    )

    assert stub_service.calls == [
        {"text": "Xin chao", "voice": "vi-VN-Wavenet-D"}
    ]
    assert result["voice"] == "vi-VN-Wavenet-D"
    assert result["format"] == "mp3"
    assert result["byte_length"] == len(b"mp3-bytes")
    assert base64.b64decode(result["audio_base64"]) == b"mp3-bytes"


@pytest.mark.asyncio
async def test_generate_audio_accepts_direct_voice_name(monkeypatch):
    stub_service = _StubGoogleTTSService()
    monkeypatch.setattr(media, "GoogleTTSService", lambda: stub_service)

    result = await media.generate_audio(
        media.AudioGenerateRequest(text="Xin chao", voice_id="vi-VN-Wavenet-C")
    )

    assert stub_service.calls == [
        {"text": "Xin chao", "voice": "vi-VN-Wavenet-C"}
    ]
    assert result["voice"] == "vi-VN-Wavenet-C"


@pytest.mark.asyncio
async def test_list_voices_filters_by_language(monkeypatch):
    monkeypatch.setattr(media, "GoogleTTSService", lambda: _StubGoogleTTSService())

    result = await media.list_voices(language="vi-vn")

    assert result == {
        "voices": {
            "male_friendly": "vi-VN-Wavenet-D",
            "female_warm": "vi-VN-Wavenet-A",
        }
    }


@pytest.mark.asyncio
async def test_generate_audio_converts_errors(monkeypatch):
    class _FailingGoogleTTSService:
        async def generate_audio(self, text: str, voice: str):
            raise RuntimeError("tts unavailable")

        def get_voices(self):
            return {}

    monkeypatch.setattr(media, "GoogleTTSService", lambda: _FailingGoogleTTSService())

    with pytest.raises(HTTPException) as exc:
        await media.generate_audio(
            media.AudioGenerateRequest(text="Xin chao", voice_id="voice")
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

    service = CarouselService()
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


def test_generate_carousel_endpoint_returns_artifact(monkeypatch):
    client = _build_client()

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

    response = client.post(
        "/api/media/carousel",
        json={
            "topic": "Launch smart route planning",
            "platform": "instagram",
            "num_slides": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "carousel"
    assert payload["slides"][0]["image_url"] == "https://cdn.example/slide-1.png"
    assert payload["manifest_url"].endswith("/manifest.json")
