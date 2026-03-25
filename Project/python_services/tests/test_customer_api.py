from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import customer
from services.customer_auth_service import CustomerSession


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(customer.router, prefix="/api/customer")
    return TestClient(app)


def _session() -> CustomerSession:
    return CustomerSession(
        user_id="11111111-1111-1111-1111-111111111111",
        email="founder@example.com",
        display_name="Founder",
        avatar_url=None,
        access_token="token-1",
        raw_user={"id": "11111111-1111-1111-1111-111111111111"},
    )


def test_get_brand_profile_returns_customer_payload(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_for_user(_user_id):
        return {
            "brand_profile_id": "brand-1",
            "product_name": "TripC",
            "campaign_goals": ["launch"],
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.BrandProfileService, "get_for_user", fake_get_for_user)

    client = _build_client()
    response = client.get(
        "/api/customer/brand",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["brand_profile"]["product_name"] == "TripC"
    assert payload["customer"]["email"] == "founder@example.com"


def test_start_social_oauth_returns_auth_url(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_start_oauth(_session, platform):
        return {"platform": platform, "auth_url": f"https://oauth.example/{platform}"}

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(
        customer.AccountConnectionService,
        "start_oauth",
        fake_start_oauth,
    )

    client = _build_client()
    response = client.post(
        "/api/customer/social-accounts/linkedin/oauth/start",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    assert response.json()["auth_url"] == "https://oauth.example/linkedin"


def test_get_ai_backbone_returns_settings_payload(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_for_user(_user_id):
        return {
            "access_mode": "platform_managed",
            "workspace_default": {
                "api_url": "https://openclaw.example",
                "has_api_key": True,
            },
            "customer_api": {
                "api_url": "https://customer-openclaw.example",
                "has_api_key": False,
            },
            "chatgpt_oauth": {
                "linked": False,
                "session_ready": False,
            },
            "effective_status": {
                "ready": True,
                "message": "Using workspace-managed OpenClaw access.",
            },
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(
        customer.CustomerAIBackboneService,
        "get_for_user",
        fake_get_for_user,
    )

    client = _build_client()
    response = client.get(
        "/api/customer/ai-backbone",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    assert response.json()["settings"]["access_mode"] == "platform_managed"


def test_link_chatgpt_oauth_returns_updated_settings(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_link_chatgpt_oauth(_session, chatgpt_subject, display_name, subscription_tier):
        return {
            "access_mode": "chatgpt_oauth",
            "workspace_default": {
                "api_url": "https://openclaw.example",
                "has_api_key": True,
            },
            "customer_api": {
                "api_url": "https://customer-openclaw.example",
                "has_api_key": True,
            },
            "chatgpt_oauth": {
                "linked": True,
                "session_ready": True,
                "chatgpt_subject": chatgpt_subject,
                "display_name": display_name,
                "subscription_tier": subscription_tier,
            },
            "effective_status": {
                "ready": True,
                "message": "Using connector-backed GPT OAuth access.",
            },
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(
        customer.CustomerAIBackboneService,
        "link_chatgpt_oauth",
        fake_link_chatgpt_oauth,
    )

    client = _build_client()
    response = client.post(
        "/api/customer/ai-backbone/chatgpt/oauth/link",
        headers={"Authorization": "Bearer customer-token"},
        json={
            "chatgpt_subject": "customer@example.com",
            "display_name": "Founder",
            "subscription_tier": "pro",
        },
    )

    assert response.status_code == 200
    assert response.json()["settings"]["chatgpt_oauth"]["chatgpt_subject"] == "customer@example.com"
    assert response.json()["settings"]["chatgpt_oauth"]["subscription_tier"] == "pro"


def test_oauth_callback_redirects_to_dashboard_on_success(monkeypatch):
    async def fake_complete_oauth(_platform, _code, _state):
        return {"platform": "linkedin"}

    monkeypatch.setattr(
        customer.AccountConnectionService,
        "complete_oauth",
        fake_complete_oauth,
    )
    monkeypatch.setattr(customer.settings, "FRONTEND_PUBLIC_URL", "https://app.example.com")

    client = _build_client()
    response = client.get(
        "/api/customer/social-accounts/linkedin/oauth/callback?code=abc&state=state-1",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert (
        response.headers["location"]
        == "https://app.example.com/dashboard?oauth_status=success&platform=linkedin"
    )


def test_launch_campaign_returns_temporal_payload(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_launch_campaign(_session, campaign_id):
        return {
            "campaign_id": campaign_id,
            "workflow_id": "weekly-marketing-1",
            "run_id": "run-123",
            "status": "launched",
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(
        customer.CustomerCampaignService,
        "launch_campaign",
        fake_launch_campaign,
    )

    client = _build_client()
    response = client.post(
        "/api/customer/campaigns/campaign-1/launch",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    assert response.json()["workflow_id"] == "weekly-marketing-1"
