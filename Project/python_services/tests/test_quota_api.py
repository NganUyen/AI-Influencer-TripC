import os

os.environ["DEBUG"] = "true"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import quota


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(quota.router, prefix="/api/quota")
    return TestClient(app)


def test_get_provider_overview_endpoint(monkeypatch):
    async def fake_get_provider_overview(days: int = 30):
        assert days == 30
        return {
            "time_period": "30_days",
            "providers": [{"provider": "openai", "status": "ok"}],
            "total_cost_usd": 1.25,
            "total_snapshots": 1,
        }

    monkeypatch.setattr(
        quota.QuotaMonitorService,
        "get_provider_overview",
        fake_get_provider_overview,
    )

    client = _build_client()
    response = client.get("/api/quota/providers")

    assert response.status_code == 200
    assert response.json()["providers"][0]["provider"] == "openai"


def test_post_quota_snapshot_endpoint(monkeypatch):
    captured = {}

    async def fake_record_snapshot(**kwargs):
        captured.update(kwargs)
        return {"id": "snapshot-1", "provider": kwargs["provider"]}

    monkeypatch.setattr(
        quota.QuotaMonitorService,
        "record_snapshot",
        fake_record_snapshot,
    )

    client = _build_client()
    response = client.post(
        "/api/quota/snapshots",
        json={
            "provider": "openai",
            "usage": {"tokens": 1000},
            "cost_usd": 2.5,
            "quota": {"limit": 10000, "remaining": 9000},
            "source": "manual",
            "metadata": {"note": "operator check"},
        },
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "openai"
    assert captured["usage"]["tokens"] == 1000
    assert captured["cost_usd"] == 2.5


def test_get_provider_detail_returns_404_for_unknown_provider(monkeypatch):
    async def fake_get_provider_detail(provider: str, days: int = 30):
        raise KeyError(f"Unknown provider: {provider}")

    monkeypatch.setattr(
        quota.QuotaMonitorService,
        "get_provider_detail",
        fake_get_provider_detail,
    )

    client = _build_client()
    response = client.get("/api/quota/providers/unknown")

    assert response.status_code == 404
    assert "Unknown provider" in response.json()["detail"]
