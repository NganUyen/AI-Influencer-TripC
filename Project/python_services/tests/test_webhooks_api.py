from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import webhooks


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(webhooks.router, prefix="/api/webhooks")
    return TestClient(app)


def test_postiz_webhook_requires_secret_when_configured(monkeypatch):
    monkeypatch.setattr(webhooks.settings, "POSTIZ_WEBHOOK_SECRET", "postiz-secret")

    client = _build_client()
    response = client.post("/api/webhooks/postiz", json={"status": "published"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook secret"


def test_postiz_webhook_syncs_normalized_payload(monkeypatch):
    captured = {}

    async def fake_sync_postiz_webhook(event):
        captured.update(event)
        return {"matched": True, "status": event["status"]}

    monkeypatch.setattr(webhooks.settings, "POSTIZ_WEBHOOK_SECRET", "postiz-secret")
    monkeypatch.setattr(
        webhooks.ContentPersistenceService,
        "sync_postiz_webhook",
        fake_sync_postiz_webhook,
    )

    client = _build_client()
    response = client.post(
        "/api/webhooks/postiz",
        json={
            "event": "post.published",
            "data": {
                "id": "provider-1",
                "post_id": "platform-1",
                "platform": "twitter",
                "status": "completed",
            },
        },
        headers={"x-postiz-webhook-secret": "postiz-secret"},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "postiz"
    assert captured["status"] == "published"
    assert captured["provider_post_id"] == "provider-1"
    assert captured["platform_post_id"] == "platform-1"


def test_growchief_webhook_accepts_bearer_secret(monkeypatch):
    captured = {}

    async def fake_sync_growchief_webhook(event):
        captured.update(event)
        return {
            "matched": True,
            "status": event["status"],
            "provider_job_id": event["provider_job_id"],
        }

    monkeypatch.setattr(
        webhooks.settings,
        "GROWCHIEF_WEBHOOK_SECRET",
        "growchief-secret",
    )
    monkeypatch.setattr(
        webhooks.ContentPersistenceService,
        "sync_growchief_webhook",
        fake_sync_growchief_webhook,
    )

    client = _build_client()
    response = client.post(
        "/api/webhooks/growchief",
        json={
            "data": {
                "job_id": "job-1",
                "platform": "twitter",
                "status": "success",
                "post_url": "https://twitter.com/post/1",
            }
        },
        headers={"Authorization": "Bearer growchief-secret"},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "growchief"
    assert response.json()["provider_job_id"] == "job-1"
    assert captured["status"] == "completed"
    assert captured["target_url"] == "https://twitter.com/post/1"


def test_webhook_rejects_unsigned_requests_when_secret_not_configured_in_production(
    monkeypatch,
):
    async def fake_sync_postiz_webhook(_event):
        return {"matched": False, "status": "scheduled"}

    monkeypatch.setattr(webhooks.settings, "POSTIZ_WEBHOOK_SECRET", None)
    monkeypatch.setattr(webhooks.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        webhooks.ContentPersistenceService,
        "sync_postiz_webhook",
        fake_sync_postiz_webhook,
    )

    client = _build_client()
    response = client.post("/api/webhooks/postiz", json={"status": "scheduled"})

    assert response.status_code == 503
    assert response.json()["detail"] == "postiz webhook secret is not configured"
