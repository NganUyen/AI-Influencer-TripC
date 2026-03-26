import base64
import json

import pytest

from config.settings import Settings
from services import storage_service as storage_service_module


class _StubResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.content = (
            b""
            if payload is None
            else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"storage request failed: {self.status_code}")

    def json(self):
        return self._payload


class _StubAsyncClient:
    def __init__(self, calls, responses, timeout=None):
        self.calls = calls
        self.responses = responses
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def request(self, method, url, headers=None, content=None, json=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "content": content,
                "json": json,
                "timeout": self.timeout,
            }
        )
        return self.responses.pop(0)


def _configure_supabase_settings(monkeypatch):
    monkeypatch.setattr(storage_service_module.settings, "STORAGE_PROVIDER", "supabase")
    monkeypatch.setattr(storage_service_module.settings, "STORAGE_BUCKET_NAME", "ai-influencer-media")
    monkeypatch.setattr(
        storage_service_module.settings,
        "STORAGE_PUBLIC_URL",
        "http://supabase.test/storage/v1/object/public/ai-influencer-media",
    )
    monkeypatch.setattr(storage_service_module.settings, "SUPABASE_URL", "http://supabase.test")
    monkeypatch.setattr(
        storage_service_module.settings,
        "SUPABASE_SERVICE_ROLE_KEY",
        "test_service_role_key",
    )
    monkeypatch.setattr(storage_service_module.settings, "STORAGE_CACHE_CONTROL_SECONDS", 3600)
    monkeypatch.setattr(storage_service_module.settings, "STORAGE_HTTP_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(storage_service_module.settings, "STORAGE_UPSERT", True)


def test_settings_default_to_supabase_storage_with_bucket_fallback():
    settings = Settings(
        DATABASE_URL="postgresql://test:test@localhost:5432/test",
        SUPABASE_URL="http://supabase.test",
        SUPABASE_KEY="test_supabase_key",
        SUPABASE_SERVICE_ROLE_KEY="test_service_role_key",
        OPENAI_API_KEY="test_openai_key",
        ANTHROPIC_API_KEY="test_anthropic_key",
        FAL_AI_API_KEY="test_fal_key",
        IPROYAL_USERNAME="test_ipro_user",
        IPROYAL_PASSWORD="test_ipro_password",
        TELEGRAM_BOT_TOKEN="test_telegram_token",
        TELEGRAM_CHAT_ID="test_telegram_chat",
        SUPABASE_STORAGE_BUCKET="",
        R2_BUCKET_NAME="legacy-media-bucket",
    )

    assert settings.STORAGE_PROVIDER == "supabase"
    assert settings.STORAGE_BUCKET_NAME == "legacy-media-bucket"
    assert (
        settings.STORAGE_PUBLIC_URL
        == "http://supabase.test/storage/v1/object/public/legacy-media-bucket"
    )


def test_settings_s3_prefers_legacy_bucket_over_supabase_bucket():
    settings = Settings(
        DATABASE_URL="postgresql://test:test@localhost:5432/test",
        SUPABASE_URL="http://supabase.test",
        SUPABASE_KEY="test_supabase_key",
        SUPABASE_SERVICE_ROLE_KEY="test_service_role_key",
        SUPABASE_STORAGE_BUCKET="supabase-media-bucket",
        STORAGE_PROVIDER="r2",
        OPENAI_API_KEY="test_openai_key",
        ANTHROPIC_API_KEY="test_anthropic_key",
        FAL_AI_API_KEY="test_fal_key",
        IPROYAL_USERNAME="test_ipro_user",
        IPROYAL_PASSWORD="test_ipro_password",
        TELEGRAM_BOT_TOKEN="test_telegram_token",
        TELEGRAM_CHAT_ID="test_telegram_chat",
        R2_BUCKET_NAME="legacy-media-bucket",
        R2_ENDPOINT_URL="http://r2.test",
        R2_ACCESS_KEY_ID="test_r2_access",
        R2_SECRET_ACCESS_KEY="test_r2_secret",
        R2_PUBLIC_DOMAIN="http://cdn.example",
    )

    assert settings.STORAGE_PROVIDER == "s3"
    assert settings.STORAGE_BUCKET_NAME == "legacy-media-bucket"
    assert settings.STORAGE_PUBLIC_URL == "http://cdn.example"


@pytest.mark.asyncio
async def test_upload_bytes_supabase_uses_storage_rest_api(monkeypatch):
    _configure_supabase_settings(monkeypatch)

    calls = []
    responses = [_StubResponse({"Id": "file-1", "Key": "ai-influencer-media/path/to/file.png"})]
    monkeypatch.setattr(
        storage_service_module.httpx,
        "AsyncClient",
        lambda timeout=None: _StubAsyncClient(calls, responses, timeout=timeout),
    )

    service = storage_service_module.StorageService()
    public_url = await service.upload_bytes(
        data=b"png-bytes",
        filename="/path/to/file.png",
        content_type="image/png",
        metadata={"topic": "TripC", "slide_num": "1"},
    )

    assert public_url == (
        "http://supabase.test/storage/v1/object/public/ai-influencer-media/path/to/file.png"
    )
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == (
        "http://supabase.test/storage/v1/object/ai-influencer-media/path/to/file.png"
    )
    assert calls[0]["headers"]["Authorization"] == "Bearer test_service_role_key"
    assert calls[0]["headers"]["apikey"] == "test_service_role_key"
    assert calls[0]["headers"]["content-type"] == "image/png"
    assert calls[0]["headers"]["cache-control"] == "max-age=3600"
    assert calls[0]["headers"]["x-upsert"] == "true"
    assert json.loads(base64.b64decode(calls[0]["headers"]["x-metadata"]).decode("utf-8")) == {
        "topic": "TripC",
        "slide_num": "1",
    }
    assert calls[0]["content"] == b"png-bytes"


@pytest.mark.asyncio
async def test_get_presigned_url_supabase_formats_full_url(monkeypatch):
    _configure_supabase_settings(monkeypatch)

    calls = []
    responses = [
        _StubResponse(
            {"signedURL": "/object/sign/ai-influencer-media/private/video.mp4?token=abc123"}
        )
    ]
    monkeypatch.setattr(
        storage_service_module.httpx,
        "AsyncClient",
        lambda timeout=None: _StubAsyncClient(calls, responses, timeout=timeout),
    )

    service = storage_service_module.StorageService()
    signed_url = await service.get_presigned_url("private/video.mp4", expiration=90)

    assert signed_url == (
        "http://supabase.test/storage/v1/object/sign/ai-influencer-media/private/video.mp4?token=abc123"
    )
    assert calls[0]["method"] == "POST"
    assert calls[0]["json"] == {"expiresIn": 90}


@pytest.mark.asyncio
async def test_list_files_supabase_recurses_nested_folders(monkeypatch):
    _configure_supabase_settings(monkeypatch)

    calls = []
    responses = [
        _StubResponse(
            [
                {"name": "slide_01.png", "id": "file-1"},
                {"name": "batch_1", "id": None},
            ]
        ),
        _StubResponse([{"name": "slide_02.png", "id": "file-2"}]),
    ]
    monkeypatch.setattr(
        storage_service_module.httpx,
        "AsyncClient",
        lambda timeout=None: _StubAsyncClient(calls, responses, timeout=timeout),
    )

    service = storage_service_module.StorageService()
    files = await service.list_files("carousels")

    assert files == [
        "carousels/slide_01.png",
        "carousels/batch_1/slide_02.png",
    ]
    assert calls[0]["json"]["prefix"] == "carousels"
    assert calls[1]["json"]["prefix"] == "carousels/batch_1"
