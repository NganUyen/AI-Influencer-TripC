import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    from api import telegram_auth
    from services.supabase_auth_bridge_service import SupabaseAuthSession
    from services.telegram_identity_service import TelegramIdentity
    from utils import jwt_compat as jwt


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


class _StubConn:
    pass


@pytest.mark.asyncio
async def test_link_start_allows_anonymous_token_creation():
    with patch.object(
        telegram_auth.TelegramLinkService,
        "create_link_token",
        AsyncMock(return_value={"start_token": "anon-token", "expires_at": "2026-03-29T12:00:00Z"}),
    ) as create_link_token:
        response = await telegram_auth.start_anonymous_telegram_link(
            telegram_auth.AnonymousLinkStartRequest(expires_in_minutes=15),
        )

    assert response["start_token"] == "anon-token"
    create_link_token.assert_awaited_once_with(user_id=None, expires_in_minutes=15)


@pytest.mark.asyncio
async def test_link_complete_returns_pending_status():
    with patch.object(
        telegram_auth.TelegramLinkService,
        "get_link_token_completion",
        AsyncMock(
            return_value={
                "status": "pending",
                "expires_at": "2026-03-29T12:00:00Z",
                "authenticated_at": None,
            }
        ),
    ):
        response = await telegram_auth.complete_anonymous_telegram_link(
            telegram_auth.TelegramLinkCompleteRequest(start_token="anon-token"),
        )

    normalized = telegram_auth.TelegramLinkCompleteResponse.model_validate(response)

    assert normalized.model_dump() == {
        "status": "pending",
        "expires_at": "2026-03-29T12:00:00Z",
        "authenticated_at": None,
        "access_token": None,
        "refresh_token": None,
        "token_type": None,
        "expires_in": None,
        "user": None,
    }


@pytest.mark.asyncio
async def test_link_complete_returns_authenticated_session():
    identity = TelegramIdentity(
        chat_id=123456789,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        email="founder@example.com",
        display_name="TripC Founder",
        avatar_url="https://cdn.example/avatar.png",
        telegram_username="tripc",
    )

    with patch.object(
        telegram_auth.TelegramLinkService,
        "get_link_token_completion",
        AsyncMock(
            return_value={
                "status": "authenticated",
                "user_id": identity.user_id,
                "expires_at": "2026-03-29T12:00:00Z",
                "authenticated_at": "2026-03-29T11:55:00Z",
            }
        ),
    ), patch.object(
        telegram_auth.DatabaseService,
        "get_pool",
        AsyncMock(return_value=_StubPool(_StubConn())),
    ), patch.object(
        telegram_auth.TelegramIdentityService,
        "get_identity_for_user_id",
        AsyncMock(return_value=identity),
    ), patch.object(
        telegram_auth.SupabaseAuthBridgeService,
        "provision_identity_session",
        AsyncMock(
            return_value=SupabaseAuthSession(
                access_token="supabase-access-token",
                refresh_token="supabase-refresh-token",
                token_type="bearer",
                expires_in=3600,
            )
        ),
    ):
        response = await telegram_auth.complete_anonymous_telegram_link(
            telegram_auth.TelegramLinkCompleteRequest(start_token="anon-token"),
        )

    assert response["status"] == "authenticated"
    assert response["user"]["id"] == identity.user_id
    assert response["user"]["email"] == identity.email
    assert response["access_token"] == "supabase-access-token"
    assert response["refresh_token"] == "supabase-refresh-token"
    assert response["expires_in"] == 3600


@pytest.mark.asyncio
async def test_link_complete_returns_expired_status():
    with patch.object(
        telegram_auth.TelegramLinkService,
        "get_link_token_completion",
        AsyncMock(
            return_value={
                "status": "expired",
                "expires_at": "2026-03-29T12:00:00Z",
                "authenticated_at": None,
            }
        ),
    ):
        response = await telegram_auth.complete_anonymous_telegram_link(
            telegram_auth.TelegramLinkCompleteRequest(start_token="anon-token"),
        )

    normalized = telegram_auth.TelegramLinkCompleteResponse.model_validate(response)
    assert normalized.status == "expired"
    assert normalized.access_token is None


@pytest.mark.asyncio
async def test_login_uses_shared_identity_resolution_and_linking():
    identity = TelegramIdentity(
        chat_id=123456789,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        email="founder@example.com",
        display_name="TripC Founder",
        avatar_url="https://cdn.example/avatar.png",
        telegram_username="tripc",
    )

    with patch.object(
        telegram_auth.DatabaseService,
        "get_pool",
        AsyncMock(return_value=_StubPool(_StubConn())),
    ), patch.object(
        telegram_auth.TelegramIdentityService,
        "resolve_or_create_identity",
        AsyncMock(return_value=identity),
    ) as resolve_or_create_identity, patch.object(
        telegram_auth.TelegramIdentityService,
        "upsert_telegram_link",
        AsyncMock(),
    ) as upsert_telegram_link:
        response = await telegram_auth.telegram_login(
            telegram_auth.TelegramLoginRequest(
                id=123456789,
                first_name="TripC",
                last_name="Founder",
                username="tripc",
                photo_url="https://cdn.example/avatar.png",
                auth_date=int(1_800_000_000),
                hash="__MOCK_DEV_LOGIN__",
            ),
        )

    assert response["user"]["email"] == identity.email
    claims = jwt.decode(
        response["access_token"],
        _TEST_ENV["JWT_SECRET_KEY"],
        algorithms=["HS256"],
        audience="authenticated",
    )
    assert claims["mock_telegram_login"] is True
    assert response.get("refresh_token") is None
    resolve_or_create_identity.assert_awaited_once()
    upsert_telegram_link.assert_awaited_once_with(
        resolve_or_create_identity.await_args.args[0],
        chat_id=123456789,
        user_id=identity.user_id,
        telegram_username="tripc",
    )


@pytest.mark.asyncio
async def test_login_uses_supabase_bridge_for_real_telegram_sign_in():
    identity = TelegramIdentity(
        chat_id=123456789,
        user_id="550e8400-e29b-41d4-a716-446655440000",
        email="founder@example.com",
        display_name="TripC Founder",
        avatar_url="https://cdn.example/avatar.png",
        telegram_username="tripc",
    )

    with patch.object(
        telegram_auth.DatabaseService,
        "get_pool",
        AsyncMock(return_value=_StubPool(_StubConn())),
    ), patch.object(
        telegram_auth.TelegramIdentityService,
        "resolve_or_create_identity",
        AsyncMock(return_value=identity),
    ), patch.object(
        telegram_auth.TelegramIdentityService,
        "upsert_telegram_link",
        AsyncMock(),
    ), patch.object(
        telegram_auth,
        "verify_telegram_hash",
        return_value=True,
    ), patch.object(
        telegram_auth.SupabaseAuthBridgeService,
        "provision_identity_session",
        AsyncMock(
            return_value=SupabaseAuthSession(
                access_token="supabase-access-token",
                refresh_token="supabase-refresh-token",
                token_type="bearer",
                expires_in=3600,
            )
        ),
    ) as provision_identity_session:
        response = await telegram_auth.telegram_login(
            telegram_auth.TelegramLoginRequest(
                id=123456789,
                first_name="TripC",
                last_name="Founder",
                username="tripc",
                photo_url="https://cdn.example/avatar.png",
                auth_date=int(time.time()),
                hash="verified-hash",
            ),
        )

    assert response["access_token"] == "supabase-access-token"
    assert response["refresh_token"] == "supabase-refresh-token"
    assert response["expires_in"] == 3600
    provision_identity_session.assert_awaited_once_with(identity)
