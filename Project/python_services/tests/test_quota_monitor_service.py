import os

os.environ["DEBUG"] = "true"

import pytest

from services.quota_monitor_service import QuotaMonitorService


@pytest.fixture(autouse=True)
def clear_quota_snapshots():
    QuotaMonitorService.clear_memory_snapshots()
    yield
    QuotaMonitorService.clear_memory_snapshots()


@pytest.fixture(autouse=True)
def disable_live_refresh(monkeypatch):
    async def fake_refresh_live_provider_snapshots(force: bool = False):
        return None

    monkeypatch.setattr(
        QuotaMonitorService,
        "refresh_live_provider_snapshots",
        fake_refresh_live_provider_snapshots,
    )


@pytest.mark.asyncio
async def test_provider_overview_reads_environment_limits(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.OPENAI_API_KEY",
        "openai-key",
    )
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.ANTHROPIC_API_KEY",
        "anthropic-key",
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
async def test_summary_aggregates_cost_and_usage(monkeypatch):
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.OPENAI_API_KEY",
        "openai-key",
    )
    monkeypatch.setattr(
        "services.quota_monitor_service.settings.FAL_AI_API_KEY",
        "fal-key",
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
        "openai-key",
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
        "google-ai-key",
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
