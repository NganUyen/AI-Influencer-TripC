import anyio
import httpx
from fastapi import FastAPI

from api import customer
from services.customer_auth_service import CustomerSession


class _SyncASGIClient:
    def __init__(self, app: FastAPI):
        self.app = app

    def request(self, method: str, path: str, **kwargs):
        async def _run():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, **kwargs)

        return anyio.run(_run)

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs):
        return self.request("POST", path, **kwargs)


def _build_client() -> _SyncASGIClient:
    app = FastAPI()
    app.include_router(customer.router, prefix="/api/customer")
    return _SyncASGIClient(app)


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
            "platform_managed": {
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
            "platform_managed": {
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


def test_get_customer_workspace_returns_aggregated_payload(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_workspace(*, user_id, customer, temporal_client=None):
        assert user_id == _session().user_id
        assert customer["email"] == "founder@example.com"
        assert temporal_client is None
        return {
            "customer": customer,
            "brand": {"product_name": "TripC"},
            "social_accounts": [{"id": "account-1", "platform": "linkedin"}],
            "assistant_threads": [{"id": "thread-1", "title": "Launch"}],
            "campaigns": [{"id": "campaign-1", "name": "Q2 Launch"}],
            "approvals": [{"id": "campaign-2", "name": "Needs review"}],
            "approval_requests": [{"approval_id": "approval-1", "status": "pending"}],
            "content": [{"id": "content-1", "title": "Teaser"}],
            "ai_backbone": {"access_mode": "platform_managed"},
            "personas": [{"persona_id": "persona-1", "display_name": "Linh"}],
            "telegram_link": {"linked": True, "link": {"chat_id": "123"}},
            "system_summary": {"services": [], "quota": []},
            "workflow_summary": {"workflows": [], "status": "empty"},
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.WorkspaceService, "get_workspace", fake_get_workspace)

    client = _build_client()
    response = client.get(
        "/api/customer/workspace",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["brand"]["product_name"] == "TripC"
    assert payload["ai_backbone"]["access_mode"] == "platform_managed"
    assert payload["customer"]["email"] == "founder@example.com"


def test_inspect_video_capture_handoff_requires_matching_customer(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    def fake_inspect_token(token, expected_user_id=None):
        assert token == "secure-handoff-token"
        assert expected_user_id == "11111111-1111-1111-1111-111111111111"
        return {
            "user_id": expected_user_id,
            "plan_id": "plan_1",
            "objective": "Capture a dashboard review",
            "target_url": "https://example.com/app",
            "persona_id": "persona-1",
            "execution_mode": "authenticated_pc_recording",
            "review_plan": {"plan_id": "plan_1"},
            "expires_at": "2026-04-08T12:00:00Z",
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(
        customer.VideoCaptureHandoffService,
        "inspect_token",
        fake_inspect_token,
    )

    client = _build_client()
    response = client.post(
        "/api/customer/video-capture/handoff/inspect",
        headers={"Authorization": "Bearer customer-token"},
        json={"token": "secure-handoff-token"},
    )

    assert response.status_code == 200
    payload = response.json()["handoff"]
    assert payload["objective"] == "Capture a dashboard review"
    assert payload["secure_collection_required"] is True
    assert "workspace_session_capture" in payload["allowed_methods"]


def test_complete_video_capture_handoff_starts_workflow(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    def fake_inspect_token(token, expected_user_id=None):
        assert token == "secure-handoff-token"
        return {
            "user_id": expected_user_id,
            "plan_id": "plan_1",
            "objective": "Capture a dashboard review",
            "target_url": "https://example.com/app",
            "persona_id": "persona-1",
            "execution_mode": "authenticated_pc_recording",
            "review_plan": {
                "planning_mode": "webpage_review",
                "plan_id": "plan_1",
                "objective": "Capture a dashboard review",
                "target_url": "https://example.com/app",
                "language": "English",
                "persona_id": "persona-1",
                "execution_mode": "authenticated_pc_recording",
                "access_level": "has_logged_in_access",
                "status": "confirmed",
            },
            "telegram_chat_id": "555",
            "expires_at": "2026-04-08T12:00:00Z",
        }

    async def fake_complete_authenticated_handoff(**kwargs):
        assert kwargs["method"] == "workspace_session_capture"
        return {
            "status": "started",
            "message": "Workflow started.",
            "workflow_id": "video-auth-1",
            "execution_mode": "authenticated_pc_recording",
            "credential_handoff": {"status": "completed"},
            "video_review_plan": {"plan_id": "plan_1"},
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.VideoCaptureHandoffService, "inspect_token", fake_inspect_token)
    monkeypatch.setattr(
        customer.VideoPlannerHandoffService,
        "complete_authenticated_handoff",
        fake_complete_authenticated_handoff,
    )

    client = _build_client()
    response = client.post(
        "/api/customer/video-capture/handoff/complete",
        headers={"Authorization": "Bearer customer-token"},
        json={
            "token": "secure-handoff-token",
            "method": "workspace_session_capture",
            "notes": "Secure session is ready.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_id"] == "video-auth-1"
    assert payload["credential_handoff"]["status"] == "completed"


def test_get_system_summary_includes_recent_videos(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_system_summary(*, user_id, temporal_client=None):
        assert user_id == _session().user_id
        return {
            "services": [],
            "quota": [],
            "recent_videos": [
                {
                    "asset_id": "asset-1",
                    "persona_id": "persona-1",
                    "title": "Launch walkthrough",
                    "access_url": "https://cdn.example/video.mp4",
                    "created_at": "2026-04-09T12:00:00Z",
                }
            ],
            "status": "healthy",
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.WorkspaceService, "get_system_summary", fake_get_system_summary)

    client = _build_client()
    response = client.get(
        "/api/customer/system/summary",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recent_videos"][0]["asset_id"] == "asset-1"
    assert payload["recent_videos"][0]["access_url"] == "https://cdn.example/video.mp4"


def test_list_recent_customer_media_returns_assets(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_list_recent_assets(*, user_id, asset_type=None, limit=10):
        assert user_id == _session().user_id
        assert asset_type == "video"
        assert limit == 3
        return [
            {
                "asset_id": "asset-1",
                "persona_id": "persona-1",
                "type": "video",
                "status": "available",
                "filename": "launch.mp4",
                "title": "Launch walkthrough",
                "access_url": "https://cdn.example/video.mp4",
                "created_at": "2026-04-09T12:00:00Z",
            }
        ]

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.CustomerMediaService, "list_recent_assets", fake_list_recent_assets)

    client = _build_client()
    response = client.get(
        "/api/customer/media/recent?limit=3",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["assets"][0]["asset_id"] == "asset-1"
    assert payload["assets"][0]["title"] == "Launch walkthrough"


def test_list_system_workflows_includes_persona_owned_video_workflows(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_workflow_summary(*, user_id, temporal_client=None, limit=20):
        assert user_id == _session().user_id
        assert limit == 20
        return {
            "status": "ok",
            "workflows": [
                {
                    "id": "video-persona-1-abcd1234",
                    "workflow_id": "video-persona-1-abcd1234",
                    "name": "short_video",
                    "status": "completed",
                    "progress": 100,
                }
            ],
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.WorkspaceService, "get_workflow_summary", fake_get_workflow_summary)

    app = FastAPI()
    app.include_router(customer.router, prefix="/api/customer")
    client = _SyncASGIClient(app)
    response = client.get(
        "/api/customer/system/workflows",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(payload["workflows"]) == 1
    assert payload["workflows"][0]["id"] == "video-persona-1-abcd1234"
    assert payload["workflows"][0]["name"] == "short_video"
    assert payload["workflows"][0]["progress"] == 100
