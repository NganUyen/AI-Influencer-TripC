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

    def patch(self, path: str, **kwargs):
        return self.request("PATCH", path, **kwargs)


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


def test_create_review_engine_job_skips_campaign_creation_without_brand_profile(monkeypatch):
    class _FakeScriptContract:
        def model_dump(self):
            return {
                "script": "Generated review script",
                "duration_estimate": 40,
                "scenes": [],
            }

    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_review_url(url, objective=None, user_id=None):
        from services.contracts import WebPageReviewContract

        assert url == "https://play.google.com/store/apps/details?id=com.android.chrome"
        assert objective == "Review"
        assert user_id == _session().user_id
        return WebPageReviewContract(
            target_url=url,
            normalized_url=url,
            page_title="Chrome Store Listing",
            product_summary="Chrome app listing",
            access_level="unknown",
            login_required=False,
        )

    async def fake_get_persona(persona_id, user_id=None):
        assert persona_id == "persona-1"
        assert user_id == _session().user_id
        return {
            "persona_id": persona_id,
            "display_name": "Chrome Reviewer",
            "language": "English",
        }

    async def fake_generate_script_from_review_plan(_self, *, app_name, review_plan, persona_config):
        assert app_name == "Chrome Store Listing"
        assert review_plan["persona_id"] == "persona-1"
        assert persona_config["display_name"] == "Chrome Reviewer"
        return _FakeScriptContract(), None

    async def fake_get_for_user(_user_id):
        return None

    async def fake_list_accounts(_user_id):
        return []

    async def fake_get_telegram_link(_user_id):
        return None

    async def fail_create_campaign(*args, **kwargs):
        raise AssertionError("campaign creation should be skipped when brand profile is missing")

    async def fake_create_jobs(*, session, payload, temporal_client=None):
        assert session.user_id == _session().user_id
        assert payload["target_personas"] == ["persona-1"]
        assert temporal_client is None
        return {
            "status": "success",
            "jobs": [
                {
                    "persona_id": "persona-1",
                    "campaign_id": None,
                    "script": {
                        "script": "Generated review script",
                        "duration_estimate": 40,
                        "scenes": [],
                    },
                }
            ],
            "warnings": [
                {
                    "code": "brand_onboarding_incomplete",
                    "message": "Brand profile is missing.",
                }
            ],
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.BrandProfileService, "get_for_user", fake_get_for_user)
    monkeypatch.setattr(customer.AccountConnectionService, "list_accounts", fake_list_accounts)
    monkeypatch.setattr(customer.TelegramLinkService, "get_link_for_user", fake_get_telegram_link)
    monkeypatch.setattr(customer.CustomerCampaignService, "create_campaign", fail_create_campaign)
    monkeypatch.setattr(customer.AppReviewStudioService, "create_jobs", fake_create_jobs)
    monkeypatch.setattr(customer.PersonaRegistryService, "get_persona", fake_get_persona)
    monkeypatch.setattr(
        "services.website_review_service.WebsiteReviewService.review_url",
        fake_review_url,
    )
    monkeypatch.setattr(
        "services.script_service.ScriptService.generate_script_from_review_plan",
        fake_generate_script_from_review_plan,
    )

    client = _build_client()
    response = client.post(
        "/api/customer/review-engine/jobs",
        headers={"Authorization": "Bearer customer-token"},
        json={
            "source_url": "https://play.google.com/store/apps/details?id=com.android.chrome",
            "objective": "Review",
            "target_personas": ["persona-1"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["jobs"][0]["persona_id"] == "persona-1"
    assert payload["jobs"][0]["campaign_id"] is None
    assert payload["jobs"][0]["script"]["script"] == "Generated review script"
    assert payload["warnings"][0]["code"] == "brand_onboarding_incomplete"


def test_get_review_engine_setup_returns_persona_options(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_setup(*, user_id):
        assert user_id == _session().user_id
        return {
            "steps": [
                {"key": "enter_url", "label": "Step 1: Enter URL"},
                {"key": "choose_persona", "label": "Step 2: Choose an available persona"},
                {"key": "final_product", "label": "Step 3: Final product"},
            ],
            "supported_languages": ["English", "Chinese", "Spanish", "Arabic"],
            "persona_options": [
                {
                    "persona_id": "basic-american-host",
                    "display_name": "Ava Brooks",
                    "selection_image_url": "data:image/svg+xml;base64,abc",
                    "tiktok_integration": {"status": "inactive"},
                }
            ],
            "custom_personas": [],
            "create_your_own": {"available": True, "label": "Create your own Persona"},
            "publishing_requirements": {"telegram_linked": False, "tiktok_channels_active": False},
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.AppReviewStudioService, "get_setup", fake_get_setup)

    client = _build_client()
    response = client.get(
        "/api/customer/review-engine/setup",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["supported_languages"] == ["English", "Chinese", "Spanish", "Arabic"]
    assert payload["persona_options"][0]["selection_image_url"].startswith("data:image/svg+xml")


def test_list_customer_personas_includes_preset_selection_image(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_list_personas(*, user_id):
        assert user_id == _session().user_id
        return [
            {
                "persona_id": "persona-1",
                "display_name": "Custom Host",
                "language": "English",
                "tts_voice": "en-US-Standard-F",
                "avatar_image_url": "https://cdn.example/custom.png",
                "status": "ready",
                "video_count": 3,
            }
        ]

    monkeypatch.setattr(
        customer.CustomerAuthService, "resolve_session", fake_resolve_session
    )
    monkeypatch.setattr(
        customer.PersonaRegistryService, "list_personas", fake_list_personas
    )
    monkeypatch.setattr(
        customer.AppReviewStudioService,
        "preset_persona_map",
        lambda: {
            "basic-american-host": {
                "persona_id": "basic-american-host",
                "display_name": "Ava Brooks",
                "language": "English",
                "status": "ready",
                "video_count": 0,
                "selection_image_url": "data:image/svg+xml;base64,abc",
                "region_label": "American",
                "is_preset_catalog": True,
            }
        },
    )

    client = _build_client()
    response = client.get(
        "/api/customer/personas",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    personas = response.json()["personas"]
    preset = next(
        item for item in personas if item["persona_id"] == "basic-american-host"
    )
    assert preset["selection_image_url"].startswith("data:image/svg+xml")
    assert preset["region_label"] == "American"
    assert preset["is_preset_catalog"] is True


def test_list_customer_personas_does_not_append_legacy_presets_when_system_personas_exist(
    monkeypatch,
):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_list_personas(*, user_id):
        assert user_id == _session().user_id
        return [
            {
                "user_id": _session().user_id,
                "persona_id": "persona-1",
                "display_name": "Custom Host",
                "language": "English",
                "status": "ready",
                "video_count": 3,
            },
            {
                "user_id": customer.AppReviewStudioService.SYSTEM_PERSONA_USER_ID,
                "persona_id": "global-cn-wei",
                "display_name": "Wei Chen",
                "language": "Mandarin",
                "status": "draft",
                "video_count": 0,
            },
        ]

    monkeypatch.setattr(
        customer.CustomerAuthService, "resolve_session", fake_resolve_session
    )
    monkeypatch.setattr(
        customer.PersonaRegistryService, "list_personas", fake_list_personas
    )

    client = _build_client()
    response = client.get(
        "/api/customer/personas",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    personas = response.json()["personas"]
    assert [item["persona_id"] for item in personas] == [
        "persona-1",
        "global-cn-wei",
    ]
    assert personas[1]["is_preset_catalog"] is True
    assert (
        personas[1]["user_id"] == customer.AppReviewStudioService.SYSTEM_PERSONA_USER_ID
    )


def test_list_customer_personas_marks_reserved_global_ids_as_preset_when_owner_drifted(
    monkeypatch,
):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_list_personas(*, user_id):
        assert user_id == _session().user_id
        return [
            {
                "user_id": _session().user_id,
                "persona_id": "global-cn-wei",
                "display_name": "Wei Chen",
                "language": "Mandarin",
                "status": "ready",
                "video_count": 0,
            },
        ]

    monkeypatch.setattr(
        customer.CustomerAuthService, "resolve_session", fake_resolve_session
    )
    monkeypatch.setattr(
        customer.PersonaRegistryService, "list_personas", fake_list_personas
    )

    client = _build_client()
    response = client.get(
        "/api/customer/personas",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    personas = response.json()["personas"]
    assert personas[0]["persona_id"] == "global-cn-wei"
    assert personas[0]["is_preset_catalog"] is True


def test_create_customer_persona_uses_default_voice(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_create_persona(payload):
        assert payload["persona_id"] == "custom-zoe-founder"
        assert payload["language"] == "English"
        assert payload["tts_voice"] == "en-US-Standard-F"
        assert payload["user_id"] == _session().user_id
        return payload

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.PersonaRegistryService, "create_persona", fake_create_persona)

    client = _build_client()
    response = client.post(
        "/api/customer/personas",
        headers={"Authorization": "Bearer customer-token"},
        json={
            "display_name": "Zoe Founder",
            "language": "English",
            "appearance_prompt_or_photo": "Confident startup reviewer",
            "tone_default": "confident",
            "market_default": "american",
        },
    )

    assert response.status_code == 200
    payload = response.json()["persona"]
    assert payload["persona_id"] == "custom-zoe-founder"
    assert payload["tts_voice"] == "en-US-Standard-F"


def test_get_review_engine_job_returns_serialized_payload(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_job(*, user_id, job_id, temporal_client=None):
        assert user_id == _session().user_id
        assert job_id == "video-basic-american-host-1234"
        assert temporal_client is None
        return {
            "job_id": job_id,
            "status": "completed",
            "persona": {"persona_id": "basic-american-host", "display_name": "Ava Brooks"},
            "production": {"ready": True, "playable_video_url": "https://cdn.example/review.mp4"},
            "publish": {"status": "ready_to_publish"},
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.AppReviewStudioService, "get_job", fake_get_job)

    client = _build_client()
    response = client.get(
        "/api/customer/review-engine/jobs/video-basic-american-host-1234",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["production"]["playable_video_url"] == "https://cdn.example/review.mp4"


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


def test_create_persona_studio_session_returns_state(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_start_session(*, app, user_id, session_id=None):
        assert app is not None
        assert user_id == _session().user_id
        assert session_id is None
        return {
            "session_id": "studio-1",
            "status": "collecting",
            "step_key": "choose_creation_mode",
            "messages": [
                {"id": "msg-1", "role": "assistant", "content": "How would you like to build your persona?"}
            ],
            "composer": {"enabled": False, "kind": "action", "placeholder": "Choose an option below..."},
            "actions": [{"id": "manual", "label": "Create Manually", "value": "manual", "kind": "action"}],
            "preview": None,
            "persona": None,
            "readiness": None,
            "can_finalize": False,
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.PersonaStudioService, "start_session", fake_start_session)

    client = _build_client()
    response = client.post(
        "/api/customer/persona-studio/sessions",
        headers={"Authorization": "Bearer customer-token"},
        json={},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "studio-1"
    assert payload["step_key"] == "choose_creation_mode"
    assert payload["messages"][0]["role"] == "assistant"


def test_create_persona_studio_session_returns_debug_detail_on_internal_error(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_start_session(*, app, user_id, session_id=None):
        raise RuntimeError("request_key column missing from workflows")

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.PersonaStudioService, "start_session", fake_start_session)

    client = _build_client()
    response = client.post(
        "/api/customer/persona-studio/sessions",
        headers={"Authorization": "Bearer customer-token"},
        json={},
    )

    assert response.status_code == 500
    payload = response.json()
    assert payload["detail"] == (
        "Persona studio start failed: RuntimeError: request_key column missing from workflows"
    )


def test_append_persona_studio_message_forwards_action(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_append_message(*, app, user_id, session_id, kind, content=None, action=None, value=None):
        assert app is not None
        assert user_id == _session().user_id
        assert session_id == "studio-1"
        assert kind == "action"
        assert action == "manual"
        assert value == "manual"
        assert content is None
        return {
            "session_id": session_id,
            "status": "collecting",
            "step_key": "collect_persona_id",
            "messages": [
                {"id": "msg-1", "role": "user", "content": "Create Manually"}
            ],
            "composer": {"enabled": True, "kind": "text", "placeholder": "Send a unique ID for the new persona."},
            "actions": [],
            "preview": None,
            "persona": None,
            "readiness": None,
            "can_finalize": False,
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.PersonaStudioService, "append_message", fake_append_message)

    client = _build_client()
    response = client.post(
        "/api/customer/persona-studio/sessions/studio-1/messages",
        headers={"Authorization": "Bearer customer-token"},
        json={"kind": "action", "action": "manual", "value": "manual"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "studio-1"
    assert payload["step_key"] == "collect_persona_id"


def test_commit_persona_studio_finalize_returns_saved_persona(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_commit(*, app, user_id, session_id, mode):
        assert app is not None
        assert user_id == _session().user_id
        assert session_id == "studio-1"
        assert mode == "finalize"
        return {
            "session_id": session_id,
            "status": "done",
            "step_key": "preview",
            "messages": [
                {"id": "msg-1", "role": "system", "content": "Persona finalized."}
            ],
            "composer": {"enabled": False, "kind": "action", "placeholder": "Choose an option below..."},
            "actions": [],
            "preview": {
                "image_url": "https://cdn.example/avatar.png",
                "persona": {"persona_id": "custom-zoe-founder", "display_name": "Zoe Founder"},
                "readiness": {"ready": True},
            },
            "persona": {"persona_id": "custom-zoe-founder", "display_name": "Zoe Founder"},
            "readiness": {"ready": True},
            "can_finalize": True,
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.PersonaStudioService, "commit", fake_commit)

    client = _build_client()
    response = client.post(
        "/api/customer/persona-studio/sessions/studio-1/commit",
        headers={"Authorization": "Bearer customer-token"},
        json={"mode": "finalize"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "done"
    assert payload["persona"]["persona_id"] == "custom-zoe-founder"


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


def test_get_review_engine_plan_returns_public_contract(monkeypatch):
    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_plan(plan_id, user_id):
        assert plan_id == "plan-1"
        assert user_id == _session().user_id
        return {
            "id": "plan-1",
            "plan_id": "plan-1",
            "user_id": user_id,
            "campaign_id": "campaign-1",
            "persona_id": "basic-american-host",
            "source_url": "https://example.com",
            "objective": "Drive signups",
            "script_text": "Narration text",
            "scenes_data": [],
            "status": "generated",
            "workflow_id": None,
            "video_url": None,
            "publish_settings": {"input_mode": "ai_autonomous"},
            "creative_preferences": {"background": "studio-soft"},
            "page_review_data": {"normalized_url": "https://example.com"},
            "created_at": "2026-04-18T00:00:00Z",
            "updated_at": "2026-04-18T00:00:00Z",
            "approved_at": None,
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.VideoPlanningService, "get_plan", fake_get_plan)

    client = _build_client()
    response = client.get(
        "/api/customer/review-engine/plans/plan-1",
        headers={"Authorization": "Bearer customer-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan_id"] == "plan-1"
    assert payload["persona_id"] == "basic-american-host"
    assert payload["creative_preferences"] == {"background": "studio-soft"}
    assert "id" not in payload
    assert "user_id" not in payload
    assert "page_review_data" not in payload


def test_patch_review_engine_plan_merges_json_fields(monkeypatch):
    captured = {}

    async def fake_resolve_session(_authorization):
        return _session()

    async def fake_get_plan(plan_id, user_id):
        assert plan_id == "plan-1"
        assert user_id == _session().user_id
        return {
            "id": "plan-1",
            "plan_id": "plan-1",
            "persona_id": "basic-american-host",
            "source_url": "https://example.com",
            "objective": "Drive signups",
            "script_text": "Narration text",
            "scenes_data": [],
            "status": "generated",
            "workflow_id": None,
            "publish_settings": {
                "input_mode": "ai_autonomous",
                "content_title": "Old title",
            },
            "creative_preferences": {
                "background": "studio-soft",
                "music_mood": "None",
            },
            "page_review_data": {
                "normalized_url": "https://example.com",
                "page_title": "Example",
            },
            "created_at": "2026-04-18T00:00:00Z",
            "updated_at": "2026-04-18T00:00:00Z",
            "approved_at": None,
        }

    async def fake_update_plan(plan_id, user_id, updates):
        captured["plan_id"] = plan_id
        captured["user_id"] = user_id
        captured["updates"] = updates
        return {
            "id": plan_id,
            "plan_id": plan_id,
            "persona_id": "basic-american-host",
            "source_url": "https://example.com",
            "objective": "Drive signups",
            "script_text": "Narration text",
            "scenes_data": [],
            "status": "generated",
            "workflow_id": None,
            "publish_settings": updates["publish_settings"],
            "creative_preferences": updates["creative_preferences"],
            "created_at": "2026-04-18T00:00:00Z",
            "updated_at": "2026-04-18T00:10:00Z",
            "approved_at": None,
        }

    monkeypatch.setattr(customer.CustomerAuthService, "resolve_session", fake_resolve_session)
    monkeypatch.setattr(customer.VideoPlanningService, "get_plan", fake_get_plan)
    monkeypatch.setattr(customer.VideoPlanningService, "update_plan", fake_update_plan)

    client = _build_client()
    response = client.patch(
        "/api/customer/review-engine/plans/plan-1",
        headers={"Authorization": "Bearer customer-token"},
        json={
            "publish_settings": {"caption_draft": "Updated caption"},
            "creative_preferences": {"music_volume": 85},
            "page_review_data": {"suggested_objective": "Drive signups"},
        },
    )

    assert response.status_code == 200
    assert captured["plan_id"] == "plan-1"
    assert captured["updates"]["publish_settings"] == {
        "input_mode": "ai_autonomous",
        "content_title": "Old title",
        "caption_draft": "Updated caption",
    }
    assert captured["updates"]["creative_preferences"] == {
        "background": "studio-soft",
        "music_mood": "None",
        "music_volume": 85,
    }
    assert captured["updates"]["page_review_data"] == {
        "normalized_url": "https://example.com",
        "page_title": "Example",
        "suggested_objective": "Drive signups",
    }
    payload = response.json()
    assert payload["plan_id"] == "plan-1"
    assert payload["publish_settings"]["caption_draft"] == "Updated caption"


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
