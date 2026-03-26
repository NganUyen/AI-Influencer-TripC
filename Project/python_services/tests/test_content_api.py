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


@pytest.fixture(autouse=True)
def stub_persisted_content(monkeypatch):
    async def fake_list_persisted_content_items(_limit: int):
        return []

    monkeypatch.setattr(
        content,
        "list_persisted_content_items",
        fake_list_persisted_content_items,
    )


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("waiting_approval", "pending_approval"),
        ("approved", "draft"),
        ("running", "draft"),
        ("completed", "published"),
        ("rejected", "failed"),
        ("timeout", "failed"),
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
async def test_list_content_items_merges_persisted_and_temporal(monkeypatch):
    async def fake_list_persisted_content_items(_limit: int):
        return [
            {
                "id": "content-1",
                "workflowId": "wf-1",
                "title": "Scheduled post",
                "content": "Persisted",
                "platform": ["twitter"],
                "status": "scheduled",
                "scheduledAt": "2026-03-02T10:00:00+00:00",
                "publishedAt": None,
                "mediaUrls": ["https://cdn.example/1.jpg"],
                "createdAt": "2026-03-01T10:00:00+00:00",
                "updatedAt": "2026-03-01T10:00:00+00:00",
            }
        ]

    monkeypatch.setattr(
        content,
        "list_persisted_content_items",
        fake_list_persisted_content_items,
    )

    workflow_items = [
        _WorkflowItem("wf-1", "run-1", "COMPLETED"),
        _WorkflowItem("wf-2", "run-2", "RUNNING"),
    ]

    async def iter_workflows(*_args, **_kwargs):
        for item in workflow_items:
            yield item

    handle = AsyncMock()
    handle.query.return_value = {"status": "waiting_approval"}

    mock_client = SimpleNamespace(
        list_workflows=lambda *_args, **_kwargs: iter_workflows(),
        get_workflow_handle=lambda *_args, **_kwargs: handle,
    )

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    result = await content.list_content_items(request, limit=10)

    assert [item["id"] for item in result["items"]] == ["content-1", "wf-2"]


@pytest.mark.asyncio
async def test_list_content_items_enriches_persisted_workflow_details(monkeypatch):
    async def fake_list_persisted_content_items(_limit: int):
        return [
            {
                "id": "content-1",
                "workflowId": "wf-1",
                "title": "Published post",
                "content": "Persisted",
                "platform": ["twitter"],
                "status": "published",
                "scheduledAt": None,
                "publishedAt": "2026-03-02T10:00:00+00:00",
                "mediaUrls": [],
                "createdAt": "2026-03-01T10:00:00+00:00",
                "updatedAt": "2026-03-01T10:00:00+00:00",
            }
        ]

    monkeypatch.setattr(
        content,
        "list_persisted_content_items",
        fake_list_persisted_content_items,
    )

    async def iter_workflows(*_args, **_kwargs):
        if False:
            yield None

    handle = AsyncMock()
    handle.query.return_value = {
        "status": "completed",
        "current_step": "engagement_tracking",
        "approval_feedback": "approved",
    }

    mock_client = SimpleNamespace(
        list_workflows=lambda *_args, **_kwargs: iter_workflows(),
        get_workflow_handle=lambda *_args, **_kwargs: handle,
    )

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    result = await content.list_content_items(request, limit=10)

    assert result["items"][0]["workflowStatus"] == "completed"
    assert result["items"][0]["currentStep"] == "engagement_tracking"
    assert result["items"][0]["approvalFeedback"] == "approved"


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
        raise content.TemporalUnavailableError("temporal unavailable")

    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await content.list_content_items(request, limit=10)

    assert response["items"] == []
    assert response["temporal_available"] is False
    assert "temporal unavailable" in response["detail"]


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


@pytest.mark.asyncio
async def test_retry_content_publish_starts_retry_workflow(monkeypatch):
    async def fake_get_retry_post_config(content_id: str):
        assert content_id == "content-1"
        return {
            "content_record_id": "content-1",
            "id": "logical-post-1",
            "workflow_id": "wf-1",
            "platform": "twitter",
            "status": "failed",
            "scheduled_time": "2026-03-10T10:00:00+00:00",
        }

    handle = SimpleNamespace(id="run-123")
    mock_client = AsyncMock()
    mock_client.start_workflow.return_value = handle

    async def fake_get_temporal_client(_request):
        return mock_client

    monkeypatch.setattr(
        content.ContentPersistenceService,
        "get_retry_post_config",
        fake_get_retry_post_config,
    )
    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    response = await content.retry_content_publish(request, content_id="content-1")

    assert response["status"] == "retry_started"
    assert response["workflow_id"].startswith("content-retry-content-1-")
    assert response["run_id"] == "run-123"
    assert mock_client.start_workflow.await_args.kwargs["args"][0]["scheduled_time"] is None


@pytest.mark.asyncio
async def test_retry_content_publish_rejects_non_failed_content(monkeypatch):
    async def fake_get_retry_post_config(_content_id: str):
        return {
            "content_record_id": "content-1",
            "id": "logical-post-1",
            "workflow_id": "wf-1",
            "platform": "twitter",
            "status": "published",
        }

    monkeypatch.setattr(
        content.ContentPersistenceService,
        "get_retry_post_config",
        fake_get_retry_post_config,
    )

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as exc:
        await content.retry_content_publish(request, content_id="content-1")

    assert exc.value.status_code == 400
    assert "Only failed content items can be retried" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_retry_content_publish_returns_503_when_temporal_unavailable(monkeypatch):
    async def fake_get_retry_post_config(_content_id: str):
        return {
            "content_record_id": "content-1",
            "id": "logical-post-1",
            "workflow_id": "wf-1",
            "platform": "twitter",
            "status": "failed",
        }

    async def fake_get_temporal_client(_request):
        raise content.TemporalUnavailableError("temporal unavailable")

    monkeypatch.setattr(
        content.ContentPersistenceService,
        "get_retry_post_config",
        fake_get_retry_post_config,
    )
    monkeypatch.setattr(content, "get_temporal_client", fake_get_temporal_client)

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as exc:
        await content.retry_content_publish(request, content_id="content-1")

    assert exc.value.status_code == 503
    assert "temporal unavailable" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_get_content_provider_wiring(monkeypatch):
    async def fake_get_retry_post_config(content_id: str):
        assert content_id == "content-1"
        return {
            "id": "content-1",
            "logical_post_id": "logical-1",
            "workflow_id": "wf-1",
            "platform": "twitter",
            "status": "published",
            "publish_method": "postiz_oauth",
            "platform_post_id": "platform-1",
            "provider_post_id": "provider-1",
            "post_url": "https://x.com/post/1",
            "publish_error": None,
            "syndicate_triggered": True,
            "syndicate_job_id": "growchief-job-1",
            "engagement_metrics": {"engagement_rate": 2.5},
        }

    monkeypatch.setattr(
        content.ContentPersistenceService,
        "get_retry_post_config",
        fake_get_retry_post_config,
    )

    response = await content.get_content_provider_wiring("content-1")

    assert response["publish_method"] == "postiz_oauth"
    assert response["platform_post_id"] == "platform-1"
    assert response["syndicate_triggered"] is True


@pytest.mark.asyncio
async def test_check_content_engagement_records_snapshot(monkeypatch):
    async def fake_get_retry_post_config(content_id: str):
        assert content_id == "content-1"
        return {
            "id": "content-1",
            "logical_post_id": "logical-1",
            "workflow_id": "wf-1",
            "content_record_id": "content-1",
            "platform": "twitter",
            "platform_post_id": "platform-1",
            "provider_post_id": "provider-1",
            "post_url": "https://x.com/post/1",
            "syndicate_triggered": False,
        }

    fake_growchief = AsyncMock()
    fake_growchief.get_engagement_metrics.return_value = {
        "engagement_rate": 1.8,
        "source": "growchief_public_api_fallback",
    }

    monkeypatch.setattr(
        content.ContentPersistenceService,
        "get_retry_post_config",
        fake_get_retry_post_config,
    )
    monkeypatch.setattr(content, "GrowChiefService", lambda: fake_growchief)
    record_mock = AsyncMock()
    monkeypatch.setattr(
        content.ContentPersistenceService,
        "record_engagement_result",
        record_mock,
    )

    response = await content.check_content_engagement("content-1")

    assert response["status"] == "engagement_snapshot_recorded"
    assert response["metrics"]["engagement_rate"] == 1.8
    record_mock.assert_awaited_once()
    fake_growchief.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_trigger_content_engagement_records_job(monkeypatch):
    async def fake_get_retry_post_config(content_id: str):
        assert content_id == "content-1"
        return {
            "id": "content-1",
            "logical_post_id": "logical-1",
            "workflow_id": "wf-1",
            "content_record_id": "content-1",
            "platform": "twitter",
            "platform_post_id": "platform-1",
            "provider_post_id": "provider-1",
            "post_url": "https://x.com/post/1",
        }

    fake_growchief = AsyncMock()
    fake_growchief.trigger_engagement.return_value = {
        "job_id": "growchief-job-1",
        "status": "pending",
    }

    monkeypatch.setattr(
        content.ContentPersistenceService,
        "get_retry_post_config",
        fake_get_retry_post_config,
    )
    monkeypatch.setattr(content, "GrowChiefService", lambda: fake_growchief)
    record_mock = AsyncMock()
    monkeypatch.setattr(
        content.ContentPersistenceService,
        "record_engagement_result",
        record_mock,
    )

    payload = content.EngagementTriggerRequest(
        action_types=["like", "comment"],
        account_count=4,
        delay_minutes=15,
    )
    response = await content.trigger_content_engagement("content-1", payload)

    assert response["status"] == "engagement_triggered"
    assert response["job"]["job_id"] == "growchief-job-1"
    record_mock.assert_awaited_once()
    fake_growchief.close.assert_awaited_once()
