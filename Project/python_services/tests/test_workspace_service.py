import pytest

from services.workspace_service import WorkspaceService


@pytest.mark.asyncio
async def test_get_system_summary_normalizes_provider_dict_payload(monkeypatch):
    async def fake_get_summary(*, days=0, user_id=None):
        assert days == 0
        assert user_id == "user-1"
        return {
            "providers": {
                "openai": {
                    "label": "OpenAI",
                    "usage_value": 42,
                    "monthly_limit": 100,
                    "usage_unit": "tokens",
                    "remaining_value": 58,
                    "remaining_unit": "tokens",
                    "remaining_source": "tracked_usage",
                    "snapshot_count": 3,
                }
            }
        }

    async def fake_list_recent_assets(*, user_id, asset_type="video", limit=5):
        assert user_id == "user-1"
        assert asset_type == "video"
        assert limit == 5
        return []

    monkeypatch.setattr(
        "services.workspace_service.QuotaMonitorService.get_summary",
        fake_get_summary,
    )
    monkeypatch.setattr(
        "services.workspace_service.CustomerMediaService.list_recent_assets",
        fake_list_recent_assets,
    )

    payload = await WorkspaceService.get_system_summary(
        user_id="user-1",
        temporal_client=None,
    )

    assert payload["status"] == "degraded"
    assert "detail" not in payload
    assert payload["quota"] == [
        {
            "provider": "openai",
            "name": "OpenAI",
            "used": 42.0,
            "total": 100.0,
            "unit": "tokens",
            "status": None,
            "usage_percent": None,
            "remaining": 58,
            "remaining_unit": "tokens",
            "remaining_exact": None,
            "remaining_source": "tracked_usage",
            "remaining_message": None,
            "reset_at": None,
            "observed_at": None,
            "billing_type": None,
            "warn_at_percent": None,
            "snapshot_count": 3,
            "cost_usd": None,
            "requests_remaining": None,
            "requests_limit": None,
            "requests_reset_at": None,
            "last_error": None,
            "last_error_type": None,
            "telemetry_scope": None,
        }
    ]


@pytest.mark.asyncio
async def test_get_system_summary_tolerates_string_provider_entries(monkeypatch):
    async def fake_get_summary(*, days=0, user_id=None):
        assert days == 0
        assert user_id == "user-2"
        return {"providers": ["OpenAI"]}

    async def fake_list_recent_assets(*, user_id, asset_type="video", limit=5):
        assert user_id == "user-2"
        assert asset_type == "video"
        assert limit == 5
        return []

    monkeypatch.setattr(
        "services.workspace_service.QuotaMonitorService.get_summary",
        fake_get_summary,
    )
    monkeypatch.setattr(
        "services.workspace_service.CustomerMediaService.list_recent_assets",
        fake_list_recent_assets,
    )

    payload = await WorkspaceService.get_system_summary(
        user_id="user-2",
        temporal_client=None,
    )

    assert payload["status"] == "degraded"
    assert "detail" not in payload
    assert payload["quota"] == [
        {
            "provider": None,
            "name": "OpenAI",
            "used": 0.0,
            "total": 100.0,
            "unit": "units",
        }
    ]
