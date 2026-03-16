from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api import content


class _WorkflowStatus:
    def __init__(self, name: str):
        self.name = name


class _WorkflowItem:
    def __init__(self, workflow_id: str, run_id: str, status: str):
        self.id = workflow_id
        self.run_id = run_id
        self.status = _WorkflowStatus(status)
        self.start_time = datetime(2026, 3, 1, 10, 0, 0)


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("waiting_approval", "pending_approval"),
        ("running", "draft"),
        ("completed", "published"),
        ("failed", "failed"),
        ("terminated", "failed"),
        ("timed_out", "failed"),
        ("unknown", "draft"),
    ],
)
def test_map_workflow_to_content_status(raw_status: str, expected: str):
    assert content.map_workflow_to_content_status(raw_status) == expected


@pytest.mark.asyncio
async def test_list_content_items_happy_path(monkeypatch):
    workflow_items = [
        _WorkflowItem("wf-1", "run-1", "RUNNING"),
        _WorkflowItem("wf-2", "run-2", "COMPLETED"),
    ]

    async def iter_workflows(*_args, **_kwargs):
        for item in workflow_items:
            yield item

    handle_1 = AsyncMock()
    handle_1.query.return_value = {
        "status": "waiting_approval",
        "current_step": "wait_for_approval",
        "approval_feedback": "pending",
    }
    handle_2 = AsyncMock()
    handle_2.query.side_effect = RuntimeError("query failed")

    mock_client = SimpleNamespace(
        list_workflows=lambda *_args, **_kwargs: iter_workflows(),
        get_workflow_handle=lambda workflow_id, run_id=None: (
            handle_1 if workflow_id == "wf-1" else handle_2
        ),
    )

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    result = await content.list_content_items(request, limit=10)

    assert len(result["items"]) == 2
    first = result["items"][0]
    assert first["id"] == "wf-1"
    assert first["status"] == "pending_approval"
    assert first["currentStep"] == "wait_for_approval"
    assert first["approvalFeedback"] == "pending"

    second = result["items"][1]
    assert second["id"] == "wf-2"
    assert second["status"] == "published"


@pytest.mark.asyncio
async def test_list_content_items_respects_limit(monkeypatch):
    workflow_items = [
        _WorkflowItem("wf-1", "run-1", "RUNNING"),
        _WorkflowItem("wf-2", "run-2", "RUNNING"),
        _WorkflowItem("wf-3", "run-3", "RUNNING"),
    ]

    async def iter_workflows(*_args, **_kwargs):
        for item in workflow_items:
            yield item

    handle = AsyncMock()
    handle.query.return_value = {"status": "running"}

    mock_client = SimpleNamespace(
        list_workflows=lambda *_args, **_kwargs: iter_workflows(),
        get_workflow_handle=lambda *_args, **_kwargs: handle,
    )

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    result = await content.list_content_items(request, limit=2)

    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_list_content_items_converts_exception(monkeypatch):
    async def fake_get_temporal_client(_request):
        raise RuntimeError("temporal unavailable")

    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    with pytest.raises(HTTPException) as exc:
        await content.list_content_items(request, limit=10)

    assert exc.value.status_code == 500
    assert "temporal unavailable" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_get_content_stats_aggregates_counts(monkeypatch):
    async def fake_list_content_items(_request, limit=200):
        assert limit == 200
        return {
            "items": [
                {"status": "draft"},
                {"status": "pending_approval"},
                {"status": "scheduled"},
                {"status": "published"},
                {"status": "failed"},
            ]
        }

    monkeypatch.setattr(content, "list_content_items", fake_list_content_items)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    result = await content.get_content_stats(request)

    assert result == {
        "total_content": 5,
        "draft": 1,
        "pending_approval": 1,
        "scheduled": 1,
        "published": 1,
        "failed": 1,
        "active_campaigns": 3,
    }


@pytest.mark.asyncio
async def test_get_content_stats_converts_exception(monkeypatch):
    async def fake_list_content_items(_request, limit=200):
        raise RuntimeError("stats failure")

    monkeypatch.setattr(content, "list_content_items", fake_list_content_items)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as exc:
        await content.get_content_stats(request)

    assert exc.value.status_code == 500
    assert "stats failure" in str(exc.value.detail)
