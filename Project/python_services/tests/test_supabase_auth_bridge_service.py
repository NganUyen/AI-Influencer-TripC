import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET": "test-secret",
    "TELEGRAM_CHAT_ID": "999",
    "BACKEND_PUBLIC_URL": "http://localhost:8000",
    "DATABASE_URL": "postgresql://localhost/test",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "STORAGE_PROVIDER": "supabase",
    "SUPABASE_STORAGE_BUCKET": "media",
    "OPENAI_API_KEY": "sk-test",
    "ANTHROPIC_API_KEY": "sk-ant-test",
    "FAL_AI_API_KEY": "fal-test",
    "R2_ACCOUNT_ID": "test",
    "R2_ACCESS_KEY_ID": "test",
    "R2_SECRET_ACCESS_KEY": "test",
    "R2_BUCKET_NAME": "test",
    "R2_PUBLIC_URL": "https://test.r2.dev",
    "IPROYAL_USERNAME": "test",
    "IPROYAL_PASSWORD": "test",
    "ENVIRONMENT": "development",
    "DEBUG": "true",
    "CORS_ORIGINS": "http://localhost:3000",
    "JWT_SECRET_KEY": "test-jwt-secret",
    "APP_ADMIN_TOKEN": "test-admin-token",
    "INTERNAL_API_TOKEN": "test-internal-token",
    "TELEGRAM_AUTH_BRIDGE_SECRET": "test-telegram-auth-bridge-secret",
}

with patch.dict(os.environ, _TEST_ENV, clear=False):
    from services.supabase_auth_bridge_service import (
        SupabaseAuthBridgeCollisionError,
        SupabaseAuthBridgeError,
        SupabaseAuthBridgeService,
    )
    from services.telegram_identity_service import TelegramIdentity


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, headers, None))
        return self.responses.pop(0)

    async def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, headers, json))
        return self.responses.pop(0)

    async def put(self, url, headers=None, json=None):
        self.calls.append(("PUT", url, headers, json))
        return self.responses.pop(0)


def _identity() -> TelegramIdentity:
    return TelegramIdentity(
        chat_id=123456789,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        email="tg_123456789@ai-influencer.invalid",
        display_name="TripC Founder",
        avatar_url="https://cdn.example/avatar.png",
        telegram_username="tripc",
    )


def test_deterministic_password_is_stable():
    first = SupabaseAuthBridgeService.deterministic_password_for_user_id(
        "550e8400-e29b-41d4-a716-446655440000"
    )
    second = SupabaseAuthBridgeService.deterministic_password_for_user_id(
        "550e8400-e29b-41d4-a716-446655440000"
    )
    other = SupabaseAuthBridgeService.deterministic_password_for_user_id(
        "550e8400-e29b-41d4-a716-446655440001"
    )

    assert first == second
    assert first != other
    assert first.startswith("tg-bridge-")


@pytest.mark.asyncio
async def test_ensure_telegram_auth_user_creates_when_missing():
    fake_client = _FakeClient(
        [
            _FakeResponse(404, {"message": "not found"}),
            _FakeResponse(200, {"id": _identity().user_id}),
        ]
    )

    with patch(
        "services.supabase_auth_bridge_service.httpx.AsyncClient",
        return_value=fake_client,
    ):
        result = await SupabaseAuthBridgeService.ensure_telegram_auth_user(_identity())

    assert result.status == "created"
    method, _, _, payload = fake_client.calls[1]
    assert method == "POST"
    assert payload["email"] == "tg_123456789@ai-influencer.invalid"
    assert payload["email_confirm"] is True


@pytest.mark.asyncio
async def test_ensure_telegram_auth_user_updates_when_existing():
    fake_client = _FakeClient(
        [
            _FakeResponse(200, {"id": _identity().user_id, "email": _identity().email}),
            _FakeResponse(200, {"id": _identity().user_id}),
        ]
    )

    with patch(
        "services.supabase_auth_bridge_service.httpx.AsyncClient",
        return_value=fake_client,
    ):
        result = await SupabaseAuthBridgeService.ensure_telegram_auth_user(_identity())

    assert result.status == "updated"
    assert fake_client.calls[1][0] == "PUT"


@pytest.mark.asyncio
async def test_ensure_telegram_auth_user_raises_collision_on_duplicate_email():
    fake_client = _FakeClient(
        [
            _FakeResponse(404, {"message": "not found"}),
            _FakeResponse(422, {"message": "User already registered"}),
        ]
    )

    with patch(
        "services.supabase_auth_bridge_service.httpx.AsyncClient",
        return_value=fake_client,
    ):
        with pytest.raises(SupabaseAuthBridgeCollisionError):
            await SupabaseAuthBridgeService.ensure_telegram_auth_user(_identity())


@pytest.mark.asyncio
async def test_create_session_for_identity_returns_real_supabase_session():
    fake_client = _FakeClient(
        [
            _FakeResponse(
                200,
                {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        ]
    )

    with patch(
        "services.supabase_auth_bridge_service.httpx.AsyncClient",
        return_value=fake_client,
    ):
        session = await SupabaseAuthBridgeService.create_session_for_identity(_identity())

    assert session.access_token == "access-token"
    assert session.refresh_token == "refresh-token"
    assert session.expires_in == 3600


@pytest.mark.asyncio
async def test_create_session_for_identity_requires_refresh_token():
    fake_client = _FakeClient(
        [
            _FakeResponse(
                200,
                {
                    "access_token": "access-token",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        ]
    )

    with patch(
        "services.supabase_auth_bridge_service.httpx.AsyncClient",
        return_value=fake_client,
    ):
        with pytest.raises(SupabaseAuthBridgeError):
            await SupabaseAuthBridgeService.create_session_for_identity(_identity())
