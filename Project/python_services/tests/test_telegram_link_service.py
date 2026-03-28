from unittest.mock import AsyncMock

import pytest

from services import telegram_link_service as telegram_link_service_module
from services.telegram_link_service import TelegramLinkError, TelegramLinkService


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


class _MissingRelationConn:
    async def fetchrow(self, query, *args):
        raise RuntimeError('relation "public.telegram_user_links" does not exist')

    async def execute(self, query, *args):
        raise RuntimeError('relation "public.telegram_user_links" does not exist')


class _MissingTokensConn:
    async def execute(self, query, *args):
        raise RuntimeError('relation "public.telegram_link_tokens" does not exist')


class _MissingRelationWithLegacyUserConn:
    async def fetchrow(self, query, *args):
        if "FROM public.telegram_user_links" in query:
            raise RuntimeError('relation "public.telegram_user_links" does not exist')
        if "FROM public.users" in query:
            return {
                "id": "8a8119f0-2640-5d14-9544-e1be9b293c23",
                "email": "persona-telegram-123456@local.ai-influencer.invalid",
            }
        return None

    async def execute(self, query, *args):
        raise RuntimeError('relation "public.telegram_user_links" does not exist')


@pytest.mark.asyncio
async def test_resolve_user_id_for_owner_key_uses_synthetic_fallback_when_link_table_missing(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationConn())),
    )

    resolved = await TelegramLinkService.resolve_user_id_for_owner_key(
        "telegram:123456",
        allow_fallback=True,
    )

    assert resolved == TelegramLinkService.synthetic_user_id_for_owner_key("telegram:123456")


@pytest.mark.asyncio
async def test_resolve_user_id_for_owner_key_reuses_legacy_synthetic_user_when_present(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationWithLegacyUserConn())),
    )

    resolved = await TelegramLinkService.resolve_user_id_for_owner_key(
        "telegram:123456",
        allow_fallback=True,
    )

    assert resolved == "8a8119f0-2640-5d14-9544-e1be9b293c23"


@pytest.mark.asyncio
async def test_resolve_user_id_for_owner_key_disables_synthetic_fallback_in_production(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationConn())),
    )
    monkeypatch.setattr(telegram_link_service_module.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(telegram_link_service_module.settings, "DEBUG", False)

    resolved = await TelegramLinkService.resolve_user_id_for_owner_key(
        "telegram:123456",
        allow_fallback=True,
    )

    assert resolved is None


@pytest.mark.asyncio
async def test_touch_link_ignores_missing_relation_table(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationConn())),
    )

    await TelegramLinkService.touch_link(chat_id=123456, telegram_username="demo_user")


@pytest.mark.asyncio
async def test_create_link_token_raises_friendly_error_when_tables_missing(monkeypatch):
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingTokensConn())),
    )

    with pytest.raises(TelegramLinkError) as exc:
        await TelegramLinkService.create_link_token(
            user_id="550e8400-e29b-41d4-a716-446655440000"
        )

    assert "Telegram link tables are not installed" in str(exc.value)
