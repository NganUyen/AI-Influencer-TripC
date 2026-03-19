import pytest

from chatgpt_connector.auth import ConnectorAuthService


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
    assert by_id.session_token == session.session_token

    resolved = await auth.resolve_session(session.session_token)
    assert resolved.session_id == session.session_id

    link = await auth.get_link("chatgpt-user-1")
    assert link is not None
    assert link.user_id == "user-123"
