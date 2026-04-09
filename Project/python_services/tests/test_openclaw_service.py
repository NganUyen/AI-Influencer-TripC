import os
import sys
from pathlib import Path
from types import SimpleNamespace
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
    "FRONTEND_PUBLIC_URL": "http://localhost:3000",
    "CHATGPT_CONNECTOR_PUBLIC_URL": "http://localhost:8010",
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
    from services.openclaw_service import OpenClawService


@pytest.mark.asyncio
async def test_execute_task_raises_when_response_body_marks_failure():
    service = OpenClawService(base_url="http://openclaw.local", api_key="test-key")
    service._record_usage = AsyncMock()
    service.client = SimpleNamespace(
        post=AsyncMock(
            return_value=SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {
                    "id": "resp_123",
                    "status": "failed",
                    "model": "openclaw:main",
                    "error": {
                        "code": "api_error",
                        "message": "internal error",
                    },
                    "output": [],
                },
            )
        )
    )

    with pytest.raises(ValueError, match="code=api_error"):
        await service.execute_task(
            task_type="video_preproduction_concept_brief",
            prompt="build a concept",
            user_id="telegram:1",
        )


@pytest.mark.asyncio
async def test_create_for_owner_uses_linked_customer_runtime():
    with (
        patch(
            "services.telegram_link_service.TelegramLinkService.resolve_user_id_for_owner_key",
            AsyncMock(return_value="11111111-1111-1111-1111-111111111111"),
        ) as resolve_user,
        patch(
            "services.customer_ai_backbone_service.CustomerAIBackboneService.resolve_runtime_config",
            AsyncMock(
                return_value={
                    "base_url": "http://connector.local",
                    "connector_session_token": "connector-token",
                    "access_mode": "chatgpt_oauth",
                }
            ),
        ) as resolve_runtime,
    ):
        service = await OpenClawService.create_for_owner(owner_key="telegram:12345")

    resolve_user.assert_awaited_once_with("telegram:12345")
    resolve_runtime.assert_awaited_once_with(
        "11111111-1111-1111-1111-111111111111"
    )
    assert service.transport == "connector"
    assert service.base_url == "http://connector.local/"
    assert service.connector_session_token == "connector-token"
