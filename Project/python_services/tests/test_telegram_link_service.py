from unittest.mock import AsyncMock

import pytest

from services import telegram_link_service as telegram_link_service_module
from services.telegram_identity_service import TelegramIdentity, TelegramIdentityService
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
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _RecordingConn:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.execute_calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, query, *args):
        if self.rows:
            return self.rows.pop(0)
        return None

    async def execute(self, query, *args):
        self.execute_calls.append((" ".join(query.split()), args))
        return "OK"


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
async def test_create_link_token_allows_anonymous_pending_user(monkeypatch):
    conn = _RecordingConn()
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    token = await TelegramLinkService.create_link_token(user_id=None, expires_in_minutes=15)

    assert token["start_token"]
    assert conn.execute_calls[0][1][0] is None


@pytest.mark.asyncio
async def test_consume_link_token_persists_resolved_user_id_for_anonymous_token(monkeypatch):
    conn = _RecordingConn(
        rows=[
            {
                "user_id": None,
                "expires_at": telegram_link_service_module._utcnow().replace(year=2099),
                "used_at": None,
            }
        ]
    )
    identity = TelegramIdentity(
        chat_id=123456,
        user_id=TelegramIdentityService.canonical_user_id_for_chat(123456),
        email="tg_123456@ai-influencer.invalid",
        display_name="@tripc",
        avatar_url=None,
        telegram_username="tripc",
    )
    monkeypatch.setattr(
        "services.telegram_link_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )
    resolve_or_create_identity = AsyncMock(return_value=identity)
    upsert_telegram_link = AsyncMock()
    monkeypatch.setattr(
        "services.telegram_link_service.TelegramIdentityService.resolve_or_create_identity",
        resolve_or_create_identity,
    )
    monkeypatch.setattr(
        "services.telegram_link_service.TelegramIdentityService.upsert_telegram_link",
        upsert_telegram_link,
    )

    result = await TelegramLinkService.consume_link_token(
        token="anon-token",
        chat_id=123456,
        telegram_username="tripc",
    )

    assert result["user_id"] == identity.user_id
    assert any(
        "update public.telegram_link_tokens set user_id = $2::uuid, used_at = now(), updated_at = now() where token_hash = $1"
        == query.lower()
        and args[1] == identity.user_id
        for query, args in conn.execute_calls
    )
    upsert_telegram_link.assert_awaited_once_with(
        conn,
        chat_id=123456,
        user_id=identity.user_id,
        telegram_username="tripc",
    )


def test_canonical_user_id_matches_telegram_owner_key():
    chat_id = 123456
    assert TelegramIdentityService.canonical_user_id_for_chat(chat_id) == (
        TelegramLinkService.synthetic_user_id_for_owner_key(f"telegram:{chat_id}")
    )
