from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api import workflows


class _WorkflowStatus:
    def __init__(self, name: str):
        self.name = name


class _WorkflowItem:
    def __init__(self, workflow_id: str, run_id: str, status: str):
        self.id = workflow_id
        self.run_id = run_id
        self.status = _WorkflowStatus(status)
        self.start_time = datetime(2026, 3, 2, 10, 0, 0)


@pytest.mark.asyncio
async def test_start_weekly_workflow_returns_started(monkeypatch):
    handle = SimpleNamespace(id="run-123")

    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.start_weekly_workflow(
        request,
        user_id="user-1",
        brand_config={"tone": "friendly"},
    )

    assert response["workflow_id"] == "weekly-marketing-user-1"
    assert response["run_id"] == "run-123"
    assert response["status"] == "started"
    mock_client.start_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_workflow_sends_signal(monkeypatch):
    handle = AsyncMock()
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.approve_workflow(
        request,
        workflow_id="wf-approve",
        approved=True,
        feedback="ok",
    )

    assert response == {
        "workflow_id": "wf-approve",
        "approved": True,
        "status": "signal_sent",
    }
    handle.signal.assert_awaited_once_with("approve_strategy", True, "ok")


@pytest.mark.asyncio
async def test_get_workflow_status_returns_query(monkeypatch):
    handle = AsyncMock()
    handle.query.return_value = {
        "status": "waiting_approval",
        "workflow_id": "wf-1",
    }
    mock_client = SimpleNamespace(get_workflow_handle=lambda _workflow_id: handle)

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.get_workflow_status(request, workflow_id="wf-1")

    assert response["workflow_id"] == "wf-1"
    assert response["status"]["status"] == "waiting_approval"


@pytest.mark.asyncio
async def test_list_workflows_happy_path(monkeypatch):
    workflow_items = [
        _WorkflowItem("wf-1", "run-1", "RUNNING"),
        _WorkflowItem("wf-2", "run-2", "COMPLETED"),
    ]

    async def iter_workflows(*_args, **_kwargs):
        for item in workflow_items:
            yield item

    mock_client = SimpleNamespace(
        list_workflows=lambda *_args, **_kwargs: iter_workflows()
    )

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await workflows.list_workflows(request, limit=10)

    assert len(response["workflows"]) == 2
    assert response["workflows"][0]["workflow_id"] == "wf-1"
    assert response["workflows"][0]["status"] == "running"


@pytest.mark.asyncio
async def test_workflow_api_converts_exceptions(monkeypatch):
    async def fake_get_temporal_client(_request):
        raise RuntimeError("temporal down")

    monkeypatch.setattr(workflows, "get_temporal_client", fake_get_temporal_client)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(HTTPException):
        await workflows.start_weekly_workflow(request, user_id="u", brand_config={})

    with pytest.raises(HTTPException):
        await workflows.list_workflows(request)
