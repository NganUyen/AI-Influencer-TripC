import base64

import pytest
from fastapi import HTTPException

from api import media


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
