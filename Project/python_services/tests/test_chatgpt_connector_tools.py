from datetime import datetime, timedelta, timezone

import pytest

from chatgpt_connector.auth import ConnectorSession
from chatgpt_connector.tools import OpenClawToolRunner


class FakeOpenClawService:
    def __init__(self):
        self.calls = []
        self.closed = False

    async def execute_task(self, **kwargs):
        self.calls.append(("execute_task", kwargs))
        return {"task_id": "task-1", "status": "accepted", "raw": kwargs}

    async def get_task_status(self, task_id):
        self.calls.append(("get_task_status", {"task_id": task_id}))
        return {"task_id": task_id, "status": "running"}

    async def cancel_task(self, task_id):
        self.calls.append(("cancel_task", {"task_id": task_id}))
        return {"task_id": task_id, "status": "canceled"}

    async def close(self):
        self.closed = True


def build_session() -> ConnectorSession:
    now = datetime.now(timezone.utc)
    return ConnectorSession(
        session_id="sess_1",
        session_token="token-1",
        user_id="user-1",
        chatgpt_subject="chatgpt-1",
        display_name="Jess",
        linked_at=now,
        expires_at=now + timedelta(hours=1),
    ).to_view()


@pytest.mark.asyncio
async def test_connector_runner_rejects_shell_tasks():
    fake_service = FakeOpenClawService()
    runner = OpenClawToolRunner(service_factory=lambda: fake_service)

    with pytest.raises(ValueError, match="Shell execution is not exposed"):
        await runner.execute_task(
            {"task_type": "shell_command", "prompt": "run rm -rf /"},
            build_session(),
        )

    assert fake_service.calls == []


@pytest.mark.asyncio
async def test_connector_runner_delegates_safe_openclaw_tasks():
    fake_service = FakeOpenClawService()
    runner = OpenClawToolRunner(service_factory=lambda: fake_service)
    session = build_session()

    result = await runner.execute_task(
        {
            "task_type": "content_strategy",
            "prompt": "Plan a 5-day TikTok campaign",
            "context": {"theme": "travel"},
        },
        session,
    )

    assert result["task_id"] == "task-1"
    assert result["status"] == "accepted"
    assert fake_service.closed is True
    assert fake_service.calls[0][0] == "execute_task"
    assert fake_service.calls[0][1]["user_id"] == "user-1"
    assert fake_service.calls[0][1]["context"]["theme"] == "travel"
    assert fake_service.calls[0][1]["context"]["connector_session"]["session_id"] == "sess_1"

    status = await runner.get_task_status({"task_id": "task-1"}, session)
    assert status["status"] == "running"

    canceled = await runner.cancel_task({"task_id": "task-1"}, session)
    assert canceled["status"] == "canceled"
