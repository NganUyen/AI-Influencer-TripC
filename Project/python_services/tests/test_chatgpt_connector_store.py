from types import SimpleNamespace

import pytest

from chatgpt_connector.store import ConnectorLinkStore


class FakeConnection:
    def __init__(self):
        self.record = None
        self.execute_calls = []

    async def fetchrow(self, query, *args):
        normalized = " ".join(query.split()).lower()
        if normalized.startswith("insert into public.chatgpt_oauth_links"):
            self.record = {
                "chatgpt_subject": args[0],
                "user_id": args[1],
                "display_name": args[2],
                "session_id": args[3],
                "linked_at": args[4],
                "last_used_at": args[5],
                "active": True,
            }
            return self.record
        if normalized.startswith("select chatgpt_subject, user_id"):
            return self.record
        raise AssertionError(f"Unexpected query: {query}")

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return FakeAcquire(self.conn)

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_connector_link_store_uses_db_and_memory_fallback(monkeypatch):
    conn = FakeConnection()
    pool = FakePool(conn)
    async def _create_pool(**_):
        return pool
    monkeypatch.setattr(
        "chatgpt_connector.store.asyncpg",
        SimpleNamespace(create_pool=_create_pool),
    )

    store = ConnectorLinkStore(db_url="postgresql://test", enabled=True)

    record = await store.upsert_link(
        chatgpt_subject="chatgpt-user-1",
        user_id="user-1",
        display_name="Jess",
        session_id="sess-1",
    )
    assert record.chatgpt_subject == "chatgpt-user-1"
    assert record.session_id == "sess-1"

    store._memory.clear()
    fetched = await store.get_link("chatgpt-user-1")
    assert fetched is not None
    assert fetched.user_id == "user-1"

    await store.touch_link("chatgpt-user-1", session_id="sess-2")
    assert conn.execute_calls
    assert conn.execute_calls[0][1][1] == "sess-2"
