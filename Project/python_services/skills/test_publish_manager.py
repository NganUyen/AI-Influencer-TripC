"""Unit tests for the publish queue skill."""

from unittest.mock import AsyncMock

import pytest

from skills.base import SkillStatus
from skills.publish_manager import PublishManagerSkill


@pytest.fixture
def queue_items():
    return [
        {
            "id": "failed-1",
            "title": "Retry this failed post",
            "status": "failed",
            "platform": ["facebook"],
            "publishError": "Postiz timeout",
        },
        {
            "id": "scheduled-1",
            "title": "Already scheduled",
            "status": "scheduled",
            "platform": ["linkedin"],
        },
    ]


@pytest.mark.asyncio
async def test_fetches_queue_and_prompts_selection(queue_items):
    session = PublishManagerSkill.initial_session()
    PublishManagerSkill._request_json = AsyncMock(return_value={"items": queue_items})

    result = await PublishManagerSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "select_item"
    assert result.session.control.status == SkillStatus.collecting
    assert result.output["queue_items"] == queue_items


@pytest.mark.asyncio
async def test_selects_queue_item_and_shows_actions(queue_items):
    session = PublishManagerSkill.initial_session()
    session.step_key = "select_item"
    session.collected["content_id"] = "failed-1"
    session.artifacts["queue_items"] = queue_items

    result = await PublishManagerSkill.execute(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "publish_or_schedule"
    assert result.output["content_item"]["id"] == "failed-1"


@pytest.mark.asyncio
async def test_retry_selected_rejects_non_failed_item(queue_items):
    session = PublishManagerSkill.initial_session()
    session.step_key = "publish_or_schedule"
    session.collected["content_id"] = "scheduled-1"
    session.artifacts["queue_items"] = queue_items
    session.artifacts["selected_item"] = queue_items[1]

    result = await PublishManagerSkill.retry_selected(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "publish_or_schedule"
    assert "Only failed items" in result.output["message"]


@pytest.mark.asyncio
async def test_retry_selected_starts_retry_workflow(queue_items):
    session = PublishManagerSkill.initial_session()
    session.step_key = "publish_or_schedule"
    session.collected["content_id"] = "failed-1"
    session.artifacts["queue_items"] = queue_items
    session.artifacts["selected_item"] = queue_items[0]
    PublishManagerSkill._request_json = AsyncMock(
        return_value={
            "workflow_id": "content-retry-failed-1",
            "run_id": "run-123",
            "status": "retry_started",
        }
    )

    result = await PublishManagerSkill.retry_selected(session, "http://backend", AsyncMock())

    assert result.success is True
    assert result.next_step == "done"
    assert result.session.control.status == SkillStatus.done
    assert result.output["workflow_id"] == "content-retry-failed-1"
