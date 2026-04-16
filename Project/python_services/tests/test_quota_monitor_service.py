import os
import json
from datetime import datetime, timezone

os.environ["DEBUG"] = "true"

import pytest

from services.content_persistence_service import ContentPersistenceService
from services.quota_monitor_service import QuotaMonitorService
from services.errors import QuotaExceededError


@pytest.fixture(autouse=True)
def clear_quota_snapshots():
    QuotaMonitorService.clear_memory_snapshots()
    yield
    QuotaMonitorService.clear_memory_snapshots()


@pytest.fixture(autouse=True)
def disable_live_refresh(monkeypatch):
    async def fake_refresh_live_provider_snapshots(force: bool = False):
        return None

    async def fake_refresh_provider_live_snapshot(_provider: str, force: bool = False):
        return None

    monkeypatch.setattr(
        QuotaMonitorService,
        "refresh_live_provider_snapshots",
        fake_refresh_live_provider_snapshots,
    )
    monkeypatch.setattr(
        QuotaMonitorService,
        "_refresh_provider_live_snapshot",
        fake_refresh_provider_live_snapshot,
    )


@pytest.mark.asyncio
async def test_provider_overview_reads_environment_limits(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.OPENAI_API_KEY",
        "test_openai_key",
    )
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.ANTHROPIC_API_KEY",
        "test_anthropic_key",
    )
    monkeypatch.setenv("QUOTA_OPENAI_MONTHLY_LIMIT_USD", "120.5")
    monkeypatch.setenv("QUOTA_OPENAI_WARN_AT_PERCENT", "75")

    await QuotaMonitorService.record_snapshot(
        provider="openai",
        usage={"requests": 4, "tokens": 1200},
        cost_usd=11.75,
        quota={"limit": 10000, "remaining": 3000},
        source="manual",
    )

    overview = await QuotaMonitorService.get_provider_overview(days=30)
    openai = next(item for item in overview["providers"] if item["provider"] == "openai")
    anthropic = next(
        item for item in overview["providers"] if item["provider"] == "anthropic"
    )

    assert openai["api_key_present"] is True
    assert openai["monthly_limit_usd"] == 120.5
    assert openai["warn_at_percent"] == 75.0
    assert openai["snapshot_count"] == 1
    assert openai["latest_snapshot"]["usage"]["tokens"] == 1200
    assert anthropic["api_key_present"] is True
    assert overview["total_snapshots"] == 1


@pytest.mark.asyncio
async def test_record_snapshot_uses_memory_fallback_when_db_unavailable(monkeypatch):
    async def fake_get_pool():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(QuotaMonitorService, "_get_pool", fake_get_pool)

    snapshot = await QuotaMonitorService.record_snapshot(
        provider="anthropic",
        usage={"requests": 2, "tokens": 500},
        cost_usd=2.5,
        quota={"limit": 5000, "remaining": 4500},
        metadata={"source": "test"},
    )

    assert snapshot["provider"] == "anthropic"
    items = await QuotaMonitorService.list_snapshots(provider="anthropic", limit=10)
    assert len(items) == 1
    assert items[0]["usage"]["tokens"] == 500


@pytest.mark.asyncio
async def test_quota_snapshots_normalize_non_uuid_user_ids_for_db_storage_and_filters(monkeypatch):
    captured: dict[str, tuple] = {}
    normalized_user_id = str(
        ContentPersistenceService._resolve_user_uuid("review-plan:persona-1")
    )

    class FakeConn:
        async def execute(self, _query, *params):
            captured["insert_params"] = params

        async def fetch(self, _query, *params):
            captured["fetch_params"] = params
            return []

    class FakePool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr(QuotaMonitorService, "_get_pool", fake_get_pool)

    snapshot = await QuotaMonitorService.record_snapshot(
        provider="openai",
        usage={"requests": 1},
        user_id="review-plan:persona-1",
    )

    await QuotaMonitorService.list_snapshots(
        provider="openai",
        limit=10,
        days=0,
        user_id="review-plan:persona-1",
    )

    assert snapshot["user_id"] == normalized_user_id
    assert captured["insert_params"][1] == normalized_user_id
    assert captured["fetch_params"][1] == normalized_user_id


@pytest.mark.asyncio
async def test_summary_aggregates_cost_and_usage(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.OPENAI_API_KEY",
        "test_openai_key",
    )
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.FAL_AI_API_KEY",
        "test_fal_key",
    )

    await QuotaMonitorService.record_snapshot(
        provider="openai",
        usage={"requests": 3, "tokens": 1000},
        cost_usd=4.25,
        quota={"limit": 10000, "remaining": 9000},
    )
    await QuotaMonitorService.record_snapshot(
        provider="fal_ai",
        usage={"requests": 1, "images": 2},
        cost_usd=1.75,
        quota={"limit": 50, "remaining": 48},
    )

    summary = await QuotaMonitorService.get_summary(days=30)

    assert summary["total_snapshots"] == 2
    assert summary["total_cost_usd"] == 6.0
    assert summary["usage_totals"]["requests"] == 4.0
    assert summary["usage_totals"]["tokens"] == 1000.0
    assert summary["usage_totals"]["images"] == 2.0
    openai = next(item for item in summary["providers"] if item["provider"] == "openai")
    fal_ai = next(item for item in summary["providers"] if item["provider"] == "fal_ai")
    assert openai["status"] == "ok"
    assert fal_ai["snapshot_count"] == 1
    assert openai["remaining_value"] == 9000.0
    assert openai["remaining_exact"] is False


@pytest.mark.asyncio
async def test_summary_prefers_provider_reported_remaining(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.OPENAI_API_KEY",
        "test_openai_key",
    )

    await QuotaMonitorService.record_snapshot(
        provider="openai",
        usage={"requests": 1, "tokens": 250},
        quota={
            "limit": 150000,
            "remaining": 149750,
            "unit": "tokens",
            "exact": True,
            "source": "provider_response_headers",
            "requests_limit": 60,
            "requests_remaining": 59,
            "requests_reset_after": "1m0s",
        },
        metadata={"operation": "generate_text"},
    )

    summary = await QuotaMonitorService.get_summary(days=30)
    openai = next(item for item in summary["providers"] if item["provider"] == "openai")

    assert openai["remaining_value"] == 149750.0
    assert openai["remaining_limit"] == 150000.0
    assert openai["remaining_exact"] is True
    assert openai["remaining_source"] == "provider_response_headers"
    assert openai["remaining_requests"] == 59.0
    assert openai["remaining_requests_limit"] == 60.0


@pytest.mark.asyncio
async def test_summary_derives_tracked_remaining_from_limit(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.GOOGLE_AI_API_KEY",
        "test_google_ai_key",
    )
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.GOOGLE_AI_MONTHLY_TOKEN_LIMIT",
        10000,
    )

    await QuotaMonitorService.record_snapshot(
        provider="gemini",
        usage={"requests": 2, "tokens": 1200},
        metadata={"operation": "generate_text"},
    )

    summary = await QuotaMonitorService.get_summary(days=30)
    gemini = next(item for item in summary["providers"] if item["provider"] == "gemini")

    assert gemini["remaining_value"] == 8800.0
    assert gemini["remaining_limit"] == 10000.0
    assert gemini["remaining_exact"] is False
    assert gemini["remaining_source"] == "tracked_usage"


@pytest.mark.asyncio
async def test_summary_parses_stringified_jsonb_quota_snapshots(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )

    payload = {
        "snapshot_id": "snapshot-1",
        "provider": "heygen",
        "source": "runtime",
        "usage": {},
        "cost_usd": None,
        "quota": {
            "unit": "quota_units",
            "exact": True,
            "source": "provider_live_endpoint",
            "remaining": 1127,
        },
        "observed_at": "2026-03-20T00:43:59.099369",
        "metadata": {
            "service": "heygen_service",
            "operation": "get_remaining_quota",
            "status": "success",
        },
    }

    class FakeConn:
        async def fetch(self, *_args):
            return [
                {
                    "content_id": None,
                    "platform": "heygen",
                    "metadata": json.dumps(payload),
                    "created_at": datetime(2026, 3, 20, 0, 44, 0, tzinfo=timezone.utc),
                }
            ]

    class FakePool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    async def fake_get_pool():
        return FakePool()

    monkeypatch.setattr(QuotaMonitorService, "_get_pool", fake_get_pool)

    summary = await QuotaMonitorService.get_summary(days=30)
    heygen = next(item for item in summary["providers"] if item["provider"] == "heygen")

    assert summary["total_snapshots"] == 1
    assert heygen["snapshot_count"] == 1
    assert heygen["status"] == "ok"
    assert heygen["remaining_value"] == 1127.0
    assert heygen["remaining_exact"] is True
    assert heygen["remaining_source"] == "provider_live_endpoint"


@pytest.mark.asyncio
async def test_summary_marks_configured_provider_without_quota_data(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.GOOGLE_AI_API_KEY",
        "test_google_ai_key",
    )

    summary = await QuotaMonitorService.get_summary(days=30)
    gemini = next(item for item in summary["providers"] if item["provider"] == "gemini")

    assert gemini["snapshot_count"] == 0
    assert gemini["remaining_value"] is None
    assert gemini["status"] == "configured"


@pytest.mark.asyncio
async def test_assert_within_budget_blocks_when_estimated_usage_exceeds_remaining(
    monkeypatch,
):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.OPENAI_API_KEY",
        "test_openai_key",
    )

    await QuotaMonitorService.record_snapshot(
        provider="openai",
        usage={"requests": 1, "tokens": 950},
        quota={
            "limit": 1000,
            "remaining": 50,
            "unit": "tokens",
            "exact": True,
            "source": "provider_response_headers",
        },
        metadata={"operation": "generate_text", "status": "success"},
    )

    with pytest.raises(QuotaExceededError, match="OpenAI quota exhausted"):
        await QuotaMonitorService.assert_within_budget(
            "openai",
            estimated_usage={"requests": 1, "tokens": 60},
            operation="generate_text:gpt-4",
        )


@pytest.mark.asyncio
async def test_assert_within_budget_blocks_when_exact_remaining_is_zero(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.HEYGEN_API_KEY",
        "test_heygen_key",
    )

    await QuotaMonitorService.record_snapshot(
        provider="heygen",
        quota={
            "remaining": 0,
            "unit": "quota_units",
            "exact": True,
            "source": "provider_live_endpoint",
        },
        metadata={"operation": "get_remaining_quota", "status": "success"},
    )

    with pytest.raises(QuotaExceededError, match="HeyGen quota exhausted"):
        await QuotaMonitorService.assert_within_budget(
            "heygen",
            estimated_usage={"requests": 1, "jobs": 1},
            operation="create_video",
        )
