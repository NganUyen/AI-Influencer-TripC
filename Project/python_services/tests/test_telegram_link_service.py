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


class _Transaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _MissingRelationConn:
    async def fetchrow(self, query, *args):
        raise RuntimeError('relation "public.telegram_user_links" does not exist')

    async def execute(self, query, *args):
        raise RuntimeError('relation "public.telegram_user_links" does not exist')


class _MissingTokensConn:
    async def execute(self, query, *args):
        raise RuntimeError('relation "public.telegram_link_tokens" does not exist')


class _RecordingConn:
    def __init__(self):
        self.executed = []

    async def execute(self, query, *args):
        self.executed.append((" ".join(query.split()), args))

    def transaction(self):
        return _Transaction()


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
async def test_resolve_user_id_for_owner_key_returns_none_when_link_table_missing(
    monkeypatch,
):
    """After bypass removal, missing telegram_user_links table returns None."""
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationConn())),
    )

    resolved = await TelegramLinkService.resolve_user_id_for_owner_key(
        "telegram:123456",
        allow_fallback=False,
    )

    assert resolved is None


@pytest.mark.asyncio
async def test_resolve_user_id_for_owner_key_returns_none_without_valid_link(
    monkeypatch,
):
    """Fallback is permanently disabled - unlinked users always get None."""
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationWithLegacyUserConn())),
    )

    resolved = await TelegramLinkService.resolve_user_id_for_owner_key(
        "telegram:123456",
        allow_fallback=False,
    )

    # Legacy fallback is disabled, so even with legacy user present, returns None
    assert resolved is None


@pytest.mark.asyncio
async def test_resolve_user_id_for_owner_key_fallback_always_disabled(
    monkeypatch,
):
    """allow_fallback=True has no effect - fallback is permanently disabled."""
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(_MissingRelationConn())),
    )

    resolved = await TelegramLinkService.resolve_user_id_for_owner_key(
        "telegram:123456",
        allow_fallback=True,  # Even with True, fallback is disabled
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


@pytest.mark.asyncio
async def test_create_public_auth_link_token_persists_placeholder_user_and_hashed_token(
    monkeypatch,
):
    conn = _RecordingConn()
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )
    monkeypatch.setattr(
        telegram_link_service_module.secrets,
        "token_urlsafe",
        lambda _size: "public-auth-token",
    )
    monkeypatch.setattr(
        telegram_link_service_module.uuid,
        "uuid4",
        lambda: telegram_link_service_module.uuid.UUID(
            "11111111-1111-1111-1111-111111111111"
        ),
    )

    result = await TelegramLinkService.create_public_auth_link_token(
        expires_in_minutes=15
    )

    assert result["start_token"] == "public-auth-token"
    user_insert = next(
        args
        for query, args in conn.executed
        if "INSERT INTO public.users" in query
    )
    token_insert = next(
        args
        for query, args in conn.executed
        if "INSERT INTO public.telegram_link_tokens" in query
    )

    assert user_insert[0] == "11111111-1111-1111-1111-111111111111"
    assert (
        user_insert[1]
        == "tg_pending_11111111-1111-1111-1111-111111111111@ai-influencer.invalid"
    )
    assert user_insert[2] == TelegramLinkService.PENDING_TELEGRAM_USER_NAME
    assert token_insert[0] == "11111111-1111-1111-1111-111111111111"
    assert (
        token_insert[1]
        == telegram_link_service_module.hashlib.sha256(
            b"public-auth-token"
        ).hexdigest()
    )
