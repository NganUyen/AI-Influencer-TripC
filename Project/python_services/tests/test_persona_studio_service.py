from unittest.mock import AsyncMock

import pytest
import json

from services.persona_studio_service import PersonaStudioService
from skills.base import SkillControl, SkillSession, SkillStatus


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


class _LegacyFallbackConn:
    def __init__(self):
        self.execute_calls = []

    async def execute(self, query, *args):
        normalized = " ".join(query.split())
        self.execute_calls.append((normalized, args))
        if len(self.execute_calls) == 1:
            raise RuntimeError('column "channel" of relation "workflows" does not exist')
        return "OK"


class _LoadConn:
    def __init__(self, row):
        self.row = row
        self.fetchrow_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((" ".join(query.split()), args))
        return self.row


@pytest.mark.asyncio
async def test_persist_state_falls_back_when_workflows_metadata_columns_missing(
    monkeypatch,
):
    conn = _LegacyFallbackConn()
    monkeypatch.setattr(
        "services.persona_studio_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    session = SkillSession(
        skill_name="persona-creator",
        step_key="choose_creation_mode",
        collected={},
        artifacts={"web_messages": []},
        control=SkillControl(status=SkillStatus.collecting),
    )

    await PersonaStudioService._persist_state(
        session_id="studio-1",
        user_id="11111111-1111-1111-1111-111111111111",
        session=session,
        studio_state={"session_id": "studio-1", "status": "collecting"},
    )

    assert len(conn.execute_calls) == 2
    assert "channel" in conn.execute_calls[0][0].lower()
    assert "request_key" in conn.execute_calls[0][0].lower()
    assert "channel" not in conn.execute_calls[1][0].lower()
    assert "request_key" not in conn.execute_calls[1][0].lower()


@pytest.mark.asyncio
async def test_load_session_uses_workflow_id_lookup(monkeypatch):
    session = SkillSession(
        skill_name="persona-creator",
        step_key="preview",
        collected={"persona_id": "zoe-founder"},
        artifacts={"web_messages": []},
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    conn = _LoadConn(
        {
            "input_data": {
                "studio_session": session.model_dump(mode="json"),
            }
        }
    )
    monkeypatch.setattr(
        "services.persona_studio_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    loaded = await PersonaStudioService._load_session(
        session_id="studio-1",
        user_id="11111111-1111-1111-1111-111111111111",
    )

    assert loaded.step_key == "preview"
    assert loaded.collected["persona_id"] == "zoe-founder"
    query, args = conn.fetchrow_calls[0]
    assert "workflow_id = $3" in query.lower()
    assert args[2] == "persona-studio-studio-1"


@pytest.mark.asyncio
async def test_load_session_accepts_stringified_json_payload(monkeypatch):
    session = SkillSession(
        skill_name="persona-creator",
        step_key="preview",
        collected={"persona_id": "zoe-founder"},
        artifacts={"web_messages": []},
        control=SkillControl(status=SkillStatus.preview_ready),
    )
    conn = _LoadConn(
        {
            "input_data": json.dumps(
                {
                    "studio_session": json.dumps(session.model_dump(mode="json")),
                }
            )
        }
    )
    monkeypatch.setattr(
        "services.persona_studio_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    loaded = await PersonaStudioService._load_session(
        session_id="studio-1",
        user_id="11111111-1111-1111-1111-111111111111",
    )

    assert loaded.step_key == "preview"
    assert loaded.collected["persona_id"] == "zoe-founder"


def test_apply_message_accepts_confirm_dream_actions():
    session = SkillSession(
        skill_name="persona-creator",
        step_key="confirm_dream",
        collected={},
        artifacts={"web_messages": []},
        control=SkillControl(status=SkillStatus.collecting),
    )

    message = PersonaStudioService._apply_message_to_session(
        session=session,
        kind="action",
        content=None,
        action="confirm",
        value="confirm",
    )

    assert session.collected["dream_confirmed"] == "confirm"
    assert message["role"] == "user"
    assert "Use & Continue" in message["content"]
