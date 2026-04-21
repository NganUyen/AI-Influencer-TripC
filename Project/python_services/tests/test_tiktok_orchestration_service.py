from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.tiktok_orchestration_service import TikTokOrchestrationService


@pytest.mark.asyncio
async def test_start_publish_workflow_uses_deterministic_id_for_future_schedule(monkeypatch):
    captured = {}

    class _Handle:
        first_execution_run_id = "run-1"

    class _Client:
        async def start_workflow(self, _run, args, id, task_queue):
            captured["args"] = args
            captured["id"] = id
            captured["task_queue"] = task_queue
            return _Handle()

    async def fake_get_temporal_client(cls, existing_client=None):
        return _Client()

    monkeypatch.setattr(
        TikTokOrchestrationService,
        "_get_temporal_client",
        classmethod(fake_get_temporal_client),
    )

    result = await TikTokOrchestrationService.start_publish_workflow(
        post_config={
            "id": "video-wf-1",
            "content_record_id": "content-77",
            "scheduled_time": "2099-04-21T00:00:00Z",
        },
        wait_for_completion=False,
    )

    assert captured["id"] == "publish-content-77"
    assert result["workflow_id"] == "publish-content-77"
    assert result["status"] == "scheduled"


@pytest.mark.asyncio
async def test_start_publish_workflow_reuses_existing_future_schedule(monkeypatch):
    class _Client:
        async def start_workflow(self, _run, args, id, task_queue):
            raise RuntimeError("workflow execution already started")

        def get_workflow_handle(self, workflow_id):
            return SimpleNamespace(workflow_id=workflow_id)

    async def fake_get_temporal_client(cls, existing_client=None):
        return _Client()

    monkeypatch.setattr(
        TikTokOrchestrationService,
        "_get_temporal_client",
        classmethod(fake_get_temporal_client),
    )

    result = await TikTokOrchestrationService.start_publish_workflow(
        post_config={
            "id": "video-wf-1",
            "content_record_id": "content-77",
            "scheduled_time": "2099-04-21T00:00:00Z",
        },
        wait_for_completion=False,
    )

    assert result["status"] == "scheduled"
    assert result["workflow_id"] == "publish-content-77"
    assert result["reused_existing"] is True
