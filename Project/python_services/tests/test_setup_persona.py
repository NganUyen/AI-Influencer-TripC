import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import setup_persona as setup_persona_script
from services.persona_registry_service import _SYSTEM_PERSONA_USER_ID


class _FakeFalService:
    def __init__(self, image_url: str):
        self.image_url = image_url
        self.generate_image = AsyncMock(return_value={"url": image_url})
        self.close = AsyncMock(return_value=None)


class _FakeMediaStorageService:
    def __init__(self, result: dict):
        self.result = result
        self.upload_from_url = AsyncMock(return_value=result)


class _FakeHeyGenService:
    def __init__(self, avatar_id: str):
        self.avatar_id = avatar_id
        self.create_avatar = AsyncMock(return_value=avatar_id)
        self.wait_for_avatar_ready = AsyncMock(return_value={"status": "ready"})


@pytest.mark.asyncio
async def test_setup_persona_persists_media_asset_and_marks_ready(monkeypatch):
    persona = {
        "persona_id": "global-us-alex",
        "user_id": _SYSTEM_PERSONA_USER_ID,
        "display_name": "Alex Rivera",
        "tts_voice": "en-US-Standard-F",
        "avatar_prompt": "Confident US creator portrait",
        "avatar_image_url": None,
        "avatar_media_asset_id": None,
        "avatar_source_type": "fal_ai",
        "status": "draft",
    }
    update_calls = []
    fal = _FakeFalService("https://fal.example.com/alex.jpg")
    media_storage = _FakeMediaStorageService(
        {
            "access_url": "https://storage.example.com/alex.jpg",
            "media_asset_id": "asset-123",
        }
    )
    heygen = _FakeHeyGenService("heygen-123")

    monkeypatch.setattr(
        setup_persona_script,
        "load_persona",
        AsyncMock(return_value=persona),
    )

    async def fake_update_persona(persona_id, fields, *, user_id=None, owner_key=None):
        update_calls.append((persona_id, fields, user_id))
        return {"persona_id": persona_id, "user_id": user_id, **fields}

    monkeypatch.setattr(
        setup_persona_script.PersonaRegistryService,
        "update_persona",
        fake_update_persona,
    )
    monkeypatch.setattr(setup_persona_script, "FalAIService", lambda: fal)
    monkeypatch.setattr(
        setup_persona_script,
        "MediaStorageService",
        lambda: media_storage,
    )
    monkeypatch.setattr(setup_persona_script, "HeyGenService", lambda: heygen)

    await setup_persona_script.setup_persona("global-us-alex")

    assert update_calls == [
        (
            "global-us-alex",
            {"status": "generating"},
            _SYSTEM_PERSONA_USER_ID,
        ),
        (
            "global-us-alex",
            {
                "avatar_image_url": "https://storage.example.com/alex.jpg",
                "avatar_media_asset_id": "asset-123",
                "avatar_source_type": "fal_ai",
            },
            _SYSTEM_PERSONA_USER_ID,
        ),
        (
            "global-us-alex",
            {
                "avatar_image_url": "https://storage.example.com/alex.jpg",
                "avatar_media_asset_id": "asset-123",
                "avatar_source_type": "fal_ai",
                "heygen_avatar_id": "heygen-123",
                "status": "ready",
            },
            _SYSTEM_PERSONA_USER_ID,
        ),
    ]
    fal.generate_image.assert_awaited_once()
    fal.close.assert_awaited_once()
    media_storage.upload_from_url.assert_awaited_once_with(
        "https://fal.example.com/alex.jpg",
        asset_type="IMAGE",
        asset_kind="avatar",
        asset_origin="generated",
        generation_prompt="Confident US creator portrait",
        user_id=_SYSTEM_PERSONA_USER_ID,
        persona_id="global-us-alex",
        metadata={
            "operator": "setup_persona",
            "persona_id": "global-us-alex",
            "display_name": "Alex Rivera",
        },
        file_name_hint="avatar",
    )
    heygen.create_avatar.assert_awaited_once_with(
        image_url="https://storage.example.com/alex.jpg",
        avatar_name="global-us-alex-avatar",
        user_id=_SYSTEM_PERSONA_USER_ID,
    )
    heygen.wait_for_avatar_ready.assert_awaited_once_with(
        "heygen-123",
        timeout_seconds=120,
        poll_interval=10,
        user_id=_SYSTEM_PERSONA_USER_ID,
    )


@pytest.mark.asyncio
async def test_setup_persona_skips_ready_persona_with_media_asset(monkeypatch):
    persona = {
        "persona_id": "global-mx-valeria",
        "user_id": _SYSTEM_PERSONA_USER_ID,
        "display_name": "Valeria Cruz",
        "tts_voice": "es-US-Standard-B",
        "avatar_prompt": "Warm Mexican Spanish creator portrait",
        "avatar_image_url": "https://storage.example.com/valeria.jpg",
        "avatar_media_asset_id": "asset-ready",
        "heygen_avatar_id": "heygen-ready",
        "status": "ready",
    }

    monkeypatch.setattr(
        setup_persona_script,
        "load_persona",
        AsyncMock(return_value=persona),
    )
    monkeypatch.setattr(
        setup_persona_script.PersonaRegistryService,
        "update_persona",
        AsyncMock(side_effect=AssertionError("update_persona should not be called")),
    )
    monkeypatch.setattr(
        setup_persona_script,
        "FalAIService",
        lambda: (_ for _ in ()).throw(AssertionError("FalAIService should not be used")),
    )
    monkeypatch.setattr(
        setup_persona_script,
        "MediaStorageService",
        lambda: (_ for _ in ()).throw(
            AssertionError("MediaStorageService should not be used")
        ),
    )
    monkeypatch.setattr(
        setup_persona_script,
        "HeyGenService",
        lambda: (_ for _ in ()).throw(AssertionError("HeyGenService should not be used")),
    )

    await setup_persona_script.setup_persona("global-mx-valeria")
