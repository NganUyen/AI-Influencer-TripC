import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import backfill_telegram_auth_users as backfill_script
from services.supabase_auth_bridge_service import (
    SupabaseAuthBridgeCollisionError,
    SupabaseAuthBridgeError,
    SupabaseAuthProvisionResult,
)
from services.telegram_identity_service import TelegramIdentity


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
    def __init__(self, link_rows, orphan_rows):
        self.link_rows = link_rows
        self.orphan_rows = orphan_rows

    async def fetch(self, query):
        if "WHERE u.email ~ '^tg_[0-9]+@ai-influencer\\.invalid$'" in query:
            return self.orphan_rows
        if "FROM public.telegram_user_links" in query:
            return self.link_rows
        raise AssertionError(f"Unexpected query: {query}")


@pytest.mark.asyncio
async def test_fetch_backfill_candidates_includes_orphans_and_dedupes(monkeypatch):
    conn = _StubConn(
        link_rows=[
            {
                "chat_id": 123456789,
                "telegram_username": "tripc",
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "tg_123456789@ai-influencer.invalid",
                "name": "TripC Founder",
                "avatar_url": None,
            }
        ],
        orphan_rows=[
            {
                "chat_id": None,
                "telegram_username": None,
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "email": "tg_222222222@ai-influencer.invalid",
                "name": None,
                "avatar_url": None,
            },
            {
                "chat_id": None,
                "telegram_username": None,
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "tg_123456789@ai-influencer.invalid",
                "name": "Duplicate",
                "avatar_url": None,
            },
        ],
    )
    monkeypatch.setattr(
        backfill_script.DatabaseService,
        "get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    identities = await backfill_script.fetch_backfill_candidates()

    assert [identity.user_id for identity in identities] == [
        "550e8400-e29b-41d4-a716-446655440000",
        "550e8400-e29b-41d4-a716-446655440001",
    ]
    assert identities[1].chat_id == 222222222
    assert identities[1].display_name == "Telegram User 222222222"


@pytest.mark.asyncio
async def test_run_backfill_apply_tracks_successes_and_failures(monkeypatch):
    identities = [
        TelegramIdentity(
            chat_id=1,
            user_id="user-1",
            email="tg_1@ai-influencer.invalid",
            display_name="One",
            avatar_url=None,
            telegram_username=None,
        ),
        TelegramIdentity(
            chat_id=2,
            user_id="user-2",
            email="tg_2@ai-influencer.invalid",
            display_name="Two",
            avatar_url=None,
            telegram_username=None,
        ),
        TelegramIdentity(
            chat_id=3,
            user_id="user-3",
            email="tg_3@ai-influencer.invalid",
            display_name="Three",
            avatar_url=None,
            telegram_username=None,
        ),
    ]
    monkeypatch.setattr(
        backfill_script,
        "fetch_backfill_candidates",
        AsyncMock(return_value=identities),
    )
    monkeypatch.setattr(
        backfill_script.SupabaseAuthBridgeService,
        "ensure_telegram_auth_user",
        AsyncMock(
            side_effect=[
                SupabaseAuthProvisionResult(
                    user_id="user-1",
                    email="tg_1@ai-influencer.invalid",
                    status="created",
                ),
                SupabaseAuthBridgeCollisionError("collision"),
                SupabaseAuthBridgeError("boom"),
            ]
        ),
    )

    summary = await backfill_script.run_backfill(apply_changes=True)

    assert summary == {
        "candidates": 3,
        "created": 1,
        "updated": 0,
        "collisions": 1,
        "failed": 1,
    }
