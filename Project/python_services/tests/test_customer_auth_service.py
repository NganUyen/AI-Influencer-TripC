import os
import sys
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
}

with patch.dict(os.environ, _TEST_ENV, clear=False):
    from api.telegram_auth import generate_supabase_jwt
    from services.customer_auth_service import CustomerAuthService


class _FailingResponse:
    status_code = 401

    def json(self):
        return {"message": "unauthorized"}


@pytest.mark.asyncio
async def test_resolve_session_falls_back_to_local_jwt_when_remote_validation_rejects():
    token = generate_supabase_jwt(
        "550e8400-e29b-41d4-a716-446655440000",
        "founder@example.com",
        display_name="TripC Founder",
        avatar_url="https://cdn.example/avatar.png",
    )
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_FailingResponse())
    fake_client.__aenter__.return_value = fake_client
    fake_client.__aexit__.return_value = False

    with patch(
        "services.customer_auth_service.httpx.AsyncClient",
        return_value=fake_client,
    ), patch.object(
        CustomerAuthService,
        "ensure_user_record",
        AsyncMock(),
    ) as ensure_user_record:
        session = await CustomerAuthService.resolve_session(f"Bearer {token}")

    assert session.user_id == "550e8400-e29b-41d4-a716-446655440000"
    assert session.email == "founder@example.com"
    assert session.display_name == "TripC Founder"
    assert session.avatar_url == "https://cdn.example/avatar.png"
    ensure_user_record.assert_awaited_once()
