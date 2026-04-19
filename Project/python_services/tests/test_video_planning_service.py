from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from services.video_planning_service import VideoPlanningService


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


class _CreateConn:
    def __init__(self, row):
        self.row = row
        self.fetchrow_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((" ".join(query.split()), args))
        return self.row


class _ListConn:
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((" ".join(query.split()), args))
        return self.rows


@pytest.mark.asyncio
async def test_create_plan_serializes_row_without_type_error(monkeypatch):
    created_at = datetime(2026, 4, 19, 15, 20, tzinfo=timezone.utc)
    conn = _CreateConn(
        {
            "id": "plan-1",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "campaign_id": None,
            "persona_id": "persona-1",
            "source_url": "https://example.com",
            "objective": "Drive signups",
            "script_text": "Narration",
            "scenes_data": '[{"scene":1}]',
            "duration_estimate": 42.0,
            "status": "generated",
            "workflow_id": None,
            "video_url": None,
            "publish_settings": '{"input_mode":"ai_autonomous"}',
            "creative_preferences": '{"background":"studio"}',
            "page_review_data": '{"normalized_url":"https://example.com"}',
            "created_at": created_at,
            "updated_at": created_at,
            "approved_at": None,
        }
    )
    monkeypatch.setattr(
        "services.video_planning_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    plan = await VideoPlanningService.create_plan(
        {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "persona_id": "persona-1",
            "source_url": "https://example.com",
            "objective": "Drive signups",
            "script_text": "Narration",
            "scenes_data": [{"scene": 1}],
        }
    )

    assert plan["plan_id"] == "plan-1"
    assert plan["scenes_data"] == [{"scene": 1}]
    assert plan["publish_settings"] == {"input_mode": "ai_autonomous"}
    assert plan["creative_preferences"] == {"background": "studio"}
    assert plan["page_review_data"] == {"normalized_url": "https://example.com"}
    assert plan["created_at"] == created_at.isoformat()
    assert conn.fetchrow_calls[0][1][0] == "11111111-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_list_plans_uses_class_record_parser(monkeypatch):
    created_at = datetime(2026, 4, 19, 15, 20, tzinfo=timezone.utc)
    conn = _ListConn(
        [
            {
                "id": "plan-1",
                "user_id": "11111111-1111-1111-1111-111111111111",
                "campaign_id": None,
                "persona_id": "persona-1",
                "source_url": "https://example.com",
                "objective": "Drive signups",
                "script_text": "Narration",
                "scenes_data": [{"scene": 1}],
                "duration_estimate": 42.0,
                "status": "generated",
                "workflow_id": "wf-1",
                "video_url": None,
                "publish_settings": {"input_mode": "ai_autonomous"},
                "creative_preferences": {"background": "studio"},
                "page_review_data": {"normalized_url": "https://example.com"},
                "created_at": created_at,
                "updated_at": created_at,
                "approved_at": None,
            }
        ]
    )
    monkeypatch.setattr(
        "services.video_planning_service.DatabaseService.get_pool",
        AsyncMock(return_value=_StubPool(conn)),
    )

    plans = await VideoPlanningService.list_plans(
        "11111111-1111-1111-1111-111111111111",
        limit=5,
    )

    assert len(plans) == 1
    assert plans[0]["workflow_id"] == "wf-1"
    assert plans[0]["created_at"] == created_at.isoformat()
    assert conn.fetch_calls[0][1] == (
        "11111111-1111-1111-1111-111111111111",
        5,
    )
