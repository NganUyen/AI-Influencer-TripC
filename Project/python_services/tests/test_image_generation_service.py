import pytest

from services.image_generation_service import ImageGenerationService


class _StubFalService:
    def __init__(self, images):
        self.images = images
        self.calls = []
        self.closed = False

    async def generate_image(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "images": self.images,
            "model": kwargs["model"],
            "prompt": kwargs["prompt"],
        }

    async def close(self):
        self.closed = True


class _StubMediaStorageService:
    def __init__(self, persisted_urls):
        self.persisted_urls = list(persisted_urls)
        self.calls = []

    async def _resolve_user_id(self, *, user_id, owner_key, campaign_id, persona_id):
        return user_id or "derived-user-id"

    def _build_destination_path(self, *, asset_type, user_id, persona_id, content_type, file_name_hint):
        extension = "jpg" if content_type == "image/jpeg" else "png"
        return (
            f"users/{user_id}/personas/{persona_id or 'unassigned'}/"
            f"{asset_type.lower()}/2026-03/{file_name_hint}.{extension}"
        )

    async def upload_from_url(self, **kwargs):
        self.calls.append(kwargs)
        return self.persisted_urls.pop(0)


@pytest.mark.asyncio
async def test_generate_images_prefers_storage_urls_and_keeps_source_urls():
    fal = _StubFalService(
        [
            {"url": "https://fal.example/one.png", "width": 1080, "height": 1080},
            {"url": "https://fal.example/two.jpg", "width": 1080, "height": 1080},
        ]
    )
    storage = _StubMediaStorageService(
        [
            {
                "url": "https://storage.example/one.png",
                "access_url": "https://storage.example/one.png",
                "storage_path": "users/derived-user-id/personas/hero/image/2026-03/tripc-hero-01.png",
                "media_asset_id": "asset-1",
            },
            {
                "url": "https://storage.example/two.jpg",
                "access_url": "https://storage.example/two.jpg",
                "storage_path": "users/derived-user-id/personas/hero/image/2026-03/tripc-hero-02.jpg",
                "media_asset_id": "asset-2",
            },
        ]
    )
    service = ImageGenerationService(fal_service=fal, media_storage_service=storage)

    result = await service.generate_images(
        prompt="TripC city skyline",
        model="fal-ai/nano-banana-2",
        num_images=2,
        owner_key="telegram:123",
        persona_id="hero",
        metadata={"source": "test"},
        file_name_hint="tripc-hero",
    )

    assert result["url"] == "https://storage.example/one.png"
    assert result["source_url"] == "https://fal.example/one.png"
    assert result["storage_url"] == "https://storage.example/one.png"
    assert result["media_asset_id"] == "asset-1"
    assert result["storage_status"] == "stored"
    assert result["images"][0]["media_asset_id"] == "asset-1"
    assert result["images"][1]["url"] == "https://storage.example/two.jpg"
    assert result["images"][1]["source_url"] == "https://fal.example/two.jpg"
    assert result["images"][1]["storage_status"] == "stored"
    assert result["images"][1]["media_asset_id"] == "asset-2"
    assert storage.calls[0]["owner_key"] == "telegram:123"
    assert storage.calls[0]["persona_id"] == "hero"
    assert fal.calls[0]["num_images"] == 2


@pytest.mark.asyncio
async def test_generate_images_falls_back_to_source_urls_when_storage_fails():
    fal = _StubFalService(
        [{"url": "https://fal.example/fallback.png", "width": 1080, "height": 1080}]
    )
    storage = _StubMediaStorageService([None])
    service = ImageGenerationService(fal_service=fal, media_storage_service=storage)

    result = await service.generate_images(prompt="Fallback image")

    assert result["url"] == "https://fal.example/fallback.png"
    assert result["source_url"] == "https://fal.example/fallback.png"
    assert result["storage_url"] is None
    assert result["media_asset_id"] is None
    assert result["storage_status"] == "source_only"
    assert result["images"][0]["storage_status"] == "source_only"
