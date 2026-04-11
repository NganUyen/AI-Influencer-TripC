from unittest.mock import AsyncMock

import pytest

from activities.media_activities import generate_audio


@pytest.mark.asyncio
async def test_generate_audio_uses_user_id_before_storage(monkeypatch):
    captured = {}

    class _FakeGoogleTTSService:
        @staticmethod
        def resolve_voice_name(requested, language=None):
            return requested

        async def generate_audio(self, text, voice, language=None, user_id=None):
            captured["user_id"] = user_id
            return b"audio-bytes"

    class _FakeMediaStorageService:
        async def upload_bytes(self, **kwargs):
            return {"access_url": "https://cdn.example/audio.mp3"}

    monkeypatch.setattr("activities.media_activities.GoogleTTSService", _FakeGoogleTTSService)
    monkeypatch.setattr("activities.media_activities.MediaStorageService", lambda: _FakeMediaStorageService())

    result = await generate_audio(
        {
            "script": "Hello there",
            "metadata": {
                "day": 1,
                "platform": "tiktok",
                "persona_id": "persona-1",
                "owner_key": "telegram:555",
                "user_id": "user-1",
            },
            "persona_id": "persona-1",
            "owner_key": "telegram:555",
            "user_id": "user-1",
            "config": {"voice": "en-US-Neural2-A"},
        }
    )

    assert captured["user_id"] == "user-1"
    assert result["url"] == "https://cdn.example/audio.mp3"
