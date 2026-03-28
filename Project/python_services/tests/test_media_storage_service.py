from unittest.mock import AsyncMock

import pytest

from services import media_storage_service as media_storage_service_module


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _StubConn:
    def __init__(self):
        self.execute_calls = []
        self.fetchrow_calls = []

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return {
            "id": "asset-123",
            "user_id": args[1],
            "persona_id": args[3],
            "bucket_name": args[8],
            "storage_path": args[9],
            "storage_provider": args[10],
            "visibility": args[11],
            "status": args[13],
        }


class _StubPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


class _ProductionConn(_StubConn):
    async def fetchrow(self, query, *args):
        normalized = " ".join(query.split()).lower()
        if normalized.startswith("select id from public.users"):
            return {"id": args[0]}
        return await super().fetchrow(query, *args)


@pytest.mark.asyncio
async def test_record_asset_writes_explicit_persona_storage_columns(monkeypatch):
    conn = _StubConn()
    pool = _StubPool(conn)

    class _StubStorage:
        bucket_name = media_storage_service_module.MEDIA_BUCKET
        provider = "supabase"

        async def get_access_url(self, filename):
            return f"https://storage.example/{filename}"

        def signed_url_expires_at(self):
            return None

    monkeypatch.setattr(
        media_storage_service_module.DatabaseService,
        "get_pool",
        AsyncMock(return_value=pool),
    )
    monkeypatch.setattr(
        media_storage_service_module,
        "StorageService",
        _StubStorage,
    )

    service = media_storage_service_module.MediaStorageService()
    await service.record_asset(
        campaign_id=None,
        asset_type="IMAGE",
        generation_prompt="persona avatar",
        storage_path="users/demo/personas/hero/image/2026-03/avatar.png",
        public_url="https://cdn.example/avatar.png",
        mime_type="image/png",
        file_size=182044,
        provider_job_id="job-123",
        user_id="550e8400-e29b-41d4-a716-446655440000",
        owner_key="telegram:123456",
        persona_id="hero",
        metadata={"source_url": "https://fal.example/avatar.png", "source": "test"},
    )

    assert len(conn.execute_calls) == 1
    assert len(conn.fetchrow_calls) == 1

    media_insert_query, media_insert_args = conn.fetchrow_calls[0]
    assert "persona_id" in media_insert_query
    assert "bucket_name" in media_insert_query
    assert "storage_path" in media_insert_query
    assert media_insert_args[3] == "hero"
    assert media_insert_args[4] == "telegram:123456"
    assert media_insert_args[5] == "https://fal.example/avatar.png"
    assert media_insert_args[8] == media_storage_service_module.MEDIA_BUCKET
    assert media_insert_args[9] == "users/demo/personas/hero/image/2026-03/avatar.png"
    assert media_insert_args[10] == "supabase"
    assert media_insert_args[11] == "private"
    assert media_insert_args[12] == "generated"
    assert media_insert_args[14] == "job-123"
    assert media_insert_args[17]["persona_id"] == "hero"
    assert media_insert_args[17]["owner_key"] == "telegram:123456"
    assert media_insert_args[17]["storage_bucket"] == media_storage_service_module.MEDIA_BUCKET


@pytest.mark.asyncio
async def test_record_asset_rejects_non_canonical_storage_path_in_production(monkeypatch):
    conn = _ProductionConn()
    pool = _StubPool(conn)

    class _StubStorage:
        bucket_name = media_storage_service_module.MEDIA_BUCKET
        provider = "supabase"

        def get_public_url(self, filename):
            return f"https://storage.example/{filename}"

    monkeypatch.setattr(
        media_storage_service_module.DatabaseService,
        "get_pool",
        AsyncMock(return_value=pool),
    )
    monkeypatch.setattr(
        media_storage_service_module,
        "StorageService",
        _StubStorage,
    )
    monkeypatch.setattr(media_storage_service_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(media_storage_service_module.settings, "DEBUG", False)

    service = media_storage_service_module.MediaStorageService()
    result = await service.record_asset(
        campaign_id=None,
        asset_type="IMAGE",
        generation_prompt="persona avatar",
        storage_path="persona/avatar.png",
        public_url="https://cdn.example/avatar.png",
        mime_type="image/png",
        file_size=182044,
        provider_job_id="job-123",
        user_id="550e8400-e29b-41d4-a716-446655440000",
        owner_key=None,
        persona_id="hero",
        metadata={"source_url": "https://fal.example/avatar.png"},
    )

    assert result is None
    assert not any(
        "insert into public.media_assets" in " ".join(query.split()).lower()
        for query, _ in conn.fetchrow_calls
    )
