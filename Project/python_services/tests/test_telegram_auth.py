import os
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


_TEST_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN",
    "DATABASE_URL": "postgresql://localhost/test",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "STORAGE_PROVIDER": "supabase",
    "SUPABASE_STORAGE_BUCKET": "media",
    "OPENAI_API_KEY": "sk-test",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "FAL_AI_API_KEY": "fal-test",
    "IPROYAL_USERNAME": "test",
    "IPROYAL_PASSWORD": "test",
    "ENVIRONMENT": "development",
    "DEBUG": "true",
    "CORS_ORIGINS": "http://localhost:3000",
    "JWT_SECRET_KEY": "test-jwt-secret",
}

with patch.dict(os.environ, _TEST_ENV, clear=False):
    from api import telegram_auth


class _Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _AuthConn:
    def __init__(self, row=None):
        self.row = row
        self.executed = []

    async def fetchrow(self, query, *args):
        return self.row

    async def execute(self, query, *args):
        self.executed.append((" ".join(query.split()), args))

    def transaction(self):
        return _Transaction()


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _StubPool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(telegram_auth.router, prefix="/api/auth/telegram")
    return TestClient(app)


def test_start_link_returns_db_backed_token(monkeypatch):
    async def fake_create_public_auth_link_token(*, expires_in_minutes):
        assert expires_in_minutes == 15
        return {
            "start_token": "db-backed-token",
            "expires_at": "2026-03-29T12:00:00+00:00",
        }

    monkeypatch.setattr(
        telegram_auth.TelegramLinkService,
        "create_public_auth_link_token",
        fake_create_public_auth_link_token,
    )

    client = _build_client()
    response = client.post(
        "/api/auth/telegram/link/start",
        json={"expires_in_minutes": 15},
    )

    assert response.status_code == 200
    assert response.json()["start_token"] == "db-backed-token"


def test_telegram_login_refreshes_existing_linked_user_record(monkeypatch):
    conn = _AuthConn({"user_id": "11111111-1111-1111-1111-111111111111"})
    monkeypatch.setattr(telegram_auth, "verify_telegram_hash", lambda *_args: True)
    monkeypatch.setattr(
        telegram_auth.DatabaseService,
        "get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )
    monkeypatch.setattr(
        telegram_auth,
        "generate_supabase_jwt",
        lambda user_id, email, expires_in=3600 * 24 * 7: f"jwt::{user_id}::{email}",
    )

    client = _build_client()
    response = client.post(
        "/api/auth/telegram/login",
        json={
            "id": 123456789,
            "first_name": "TripC",
            "last_name": "Bot",
            "username": "tripc_bot",
            "photo_url": "https://cdn.example/avatar.png",
            "auth_date": 4102444800,
            "hash": "valid-hash",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["user"]["email"] == "tg_123456789@ai-influencer.invalid"

    user_insert = next(
        args
        for query, args in conn.executed
        if "INSERT INTO public.users" in query
    )
    link_insert = next(
        args
        for query, args in conn.executed
        if "INSERT INTO public.telegram_user_links" in query
    )

    assert user_insert[0] == "11111111-1111-1111-1111-111111111111"
    assert user_insert[1] == "tg_123456789@ai-influencer.invalid"
    assert user_insert[2] == "TripC Bot"
    assert link_insert[0] == 123456789
    assert link_insert[1] == "11111111-1111-1111-1111-111111111111"
    assert link_insert[2] == "tripc_bot"
