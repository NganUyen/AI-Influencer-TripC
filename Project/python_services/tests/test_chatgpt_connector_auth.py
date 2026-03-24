from datetime import datetime, timezone

import pytest

from chatgpt_connector.auth import ConnectorAuthService
from chatgpt_connector.store import ConnectorLinkRecord


@pytest.mark.asyncio
async def test_connector_auth_service_creates_and_resolves_session():
    auth = ConnectorAuthService(public_url="http://connector.test", secret="unit-test-secret")

    start = await auth.begin_oauth(
        chatgpt_subject="chatgpt-user-1",
        user_id="user-123",
        display_name="Jess",
    )

    assert start.chatgpt_subject == "chatgpt-user-1"
    assert start.authorization_url.startswith("http://connector.test/oauth/callback")

    session = await auth.complete_oauth(
        state=start.state,
        chatgpt_subject="chatgpt-user-1",
        user_id="user-123",
        display_name="Jess",
    )

    assert session.user_id == "user-123"
    assert session.chatgpt_subject == "chatgpt-user-1"
    assert session.active is True

    by_id = await auth.get_session(session.session_id)
    assert by_id is not None
    assert by_id.session_id == session.session_id

    resolved = await auth.resolve_session(session.session_token)
    assert resolved.session_id == session.session_id

    link = await auth.get_link("chatgpt-user-1")
    assert link is not None
    assert link.user_id == "user-123"


@pytest.mark.asyncio
async def test_connector_auth_service_resolves_persisted_session_across_instances(monkeypatch):
    records = {}

    class SharedLinkStore:
        def __init__(self, *args, **kwargs):
            self.enabled = True

        async def upsert_link(self, chatgpt_subject, user_id, display_name, session_id):
            existing = records.get(chatgpt_subject)
            record = ConnectorLinkRecord(
                chatgpt_subject=chatgpt_subject,
                user_id=user_id,
                display_name=display_name,
                session_id=session_id,
                linked_at=existing.linked_at if existing else datetime.now(timezone.utc),
                last_used_at=datetime.now(timezone.utc),
                active=True,
            )
            records[chatgpt_subject] = record
            return record

        async def get_link(self, chatgpt_subject):
            return records.get(chatgpt_subject)

        async def touch_link(self, chatgpt_subject, session_id=None):
            record = records.get(chatgpt_subject)
            if record is not None and session_id:
                record.session_id = session_id

        async def close(self):
            return None

    monkeypatch.setattr("chatgpt_connector.auth.ConnectorLinkStore", SharedLinkStore)

    issuing_auth = ConnectorAuthService(
        public_url="http://connector.test",
        secret="unit-test-secret",
        persist_links=True,
    )
    start = await issuing_auth.begin_oauth(
        chatgpt_subject="chatgpt-user-2",
        user_id="user-234",
        display_name="Riley",
    )
    issued = await issuing_auth.complete_oauth(
        state=start.state,
        chatgpt_subject="chatgpt-user-2",
        user_id="user-234",
        display_name="Riley",
    )
    await issuing_auth.close()

    resolving_auth = ConnectorAuthService(
        public_url="http://connector.test",
        secret="unit-test-secret",
        persist_links=True,
    )
    resolved = await resolving_auth.resolve_session(issued.session_token)

    assert resolved.session_id == issued.session_id
    assert resolved.user_id == "user-234"
    assert resolved.chatgpt_subject == "chatgpt-user-2"
