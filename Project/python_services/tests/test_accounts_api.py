import pytest

from api import accounts
from services.proxy_manager_service import ProxyManagerService


def _seed_inventory() -> None:
    ProxyManagerService.reset_state()
    ProxyManagerService.refresh_inventory(
        [
            "http://proxy-vn.example:8000|country=VN|region=Da Nang|label=vn-1",
            "http://proxy-us.example:8001|country=US|region=New York|label=us-1",
        ]
    )


@pytest.mark.asyncio
async def test_plan_onboarding_returns_browser_profile():
    _seed_inventory()
    response = await accounts.plan_onboarding(
        {
            "platform": "tiktok",
            "account_key": "creator-vn",
            "persona_config": {"country_code": "VN", "name": "Minh"},
        }
    )

    payload = response["plan"]
    assert payload["account_type"] == "proxy_bootstrap"
    assert payload["browser_profile"]["storage_state_path"].endswith(
        "/browser_profiles/tiktok/creator-vn/storage_state.json"
    )
    assert payload["browser_context"]["locale"] == "vi-VN"


@pytest.mark.asyncio
async def test_execute_onboarding_persists_registry_and_tracks_human_assisted_bootstrap(monkeypatch):
    _seed_inventory()
    captured = {}

    async def fake_register_account_record(**kwargs):
        captured.update(kwargs)
        return {
            "registry_persisted": True,
            "registry_id": "registry-1",
            "owner_key": kwargs["owner_key"],
            "platform": kwargs["platform"],
            "account_key": kwargs["account_key"],
            "status": kwargs["status"],
            "is_primary": kwargs["is_primary"],
            "account_type": "proxy_bootstrap",
            "plan": kwargs["plan"],
        }

    monkeypatch.setattr(
        ProxyManagerService,
        "register_account_record",
        fake_register_account_record,
    )

    body = await accounts.execute_onboarding(
        {
            "platform": "facebook",
            "account_key": "creator-fb",
            "owner_key": "owner-1",
            "persona_config": {"country_code": "US", "name": "Creator FB"},
        }
    )

    assert body["status"] == "prepared"
    assert body["execution"]["plan"]["browser_profile"]["storage_state_path"].endswith(
        "/browser_profiles/facebook/creator-fb/storage_state.json"
    )
    assert captured["is_primary"] is False
    assert captured["platform"] == "facebook"
    assert captured["status"] == "prepared"


@pytest.mark.asyncio
async def test_connect_platform_account_registers_primary_oauth(monkeypatch):
    _seed_inventory()
    captured = {}

    async def fake_register_account_record(**kwargs):
        captured.update(kwargs)
        return {
            "registry_persisted": True,
            "registry_id": "registry-2",
            "owner_key": kwargs["owner_key"],
            "platform": kwargs["platform"],
            "account_key": kwargs["account_key"],
            "status": "connected",
            "is_primary": kwargs["is_primary"],
            "account_type": "primary_oauth",
            "plan": kwargs["plan"],
        }

    monkeypatch.setattr(
        ProxyManagerService,
        "register_account_record",
        fake_register_account_record,
    )

    body = await accounts.connect_platform_account(
        "youtube",
        {
            "owner_key": "owner-2",
            "email": "creator@example.com",
            "oauth_token": "token-123",
            "country_code": "US",
            "name": "Studio Channel",
        },
    )

    assert body["status"] == "connected"
    assert body["registry"]["is_primary"] is True
    assert body["plan"]["account_type"] == "primary_oauth"
    assert captured["is_primary"] is True
    assert captured["platform"] == "youtube"


@pytest.mark.asyncio
async def test_list_connected_accounts_returns_state_and_registry(monkeypatch):
    _seed_inventory()

    async def fake_list_registry(**_kwargs):
        return {
            "registry_persisted": True,
            "accounts": [{"id": "registry-1", "platform": "tiktok"}],
            "owner_key": None,
            "limit": 100,
        }

    monkeypatch.setattr(ProxyManagerService, "list_registry", fake_list_registry)

    body = await accounts.list_connected_accounts()
    assert body["registry"]["accounts"][0]["platform"] == "tiktok"
    assert len(body["inventory"]) == 2
    assert "password" not in body["inventory"][0]
    assert body["inventory"][0]["requires_auth"] is True


@pytest.mark.asyncio
async def test_list_connected_accounts_redacts_registry_secrets(monkeypatch):
    _seed_inventory()

    async def fake_list_registry(**_kwargs):
        return {
            "registry_persisted": True,
            "accounts": [
                {
                    "id": "registry-1",
                    "platform": "youtube",
                    "oauth_token_present": True,
                    "proxy_config": {
                        "proxy_lease": {
                            "proxy": {
                                "server": "http://proxy.example:8000",
                                "password": "secret-password",
                            }
                        }
                    },
                    "last_api_response": {
                        "oauth_token": "oauth-secret",
                    },
                }
            ],
            "owner_key": None,
            "limit": 100,
        }

    monkeypatch.setattr(ProxyManagerService, "list_registry", fake_list_registry)

    account = (await accounts.list_connected_accounts())["registry"]["accounts"][0]
    assert account["oauth_token_present"] is True
    assert account["proxy_config"]["proxy_lease"]["proxy"]["password"] == "[redacted]"
    assert account["last_api_response"]["oauth_token"] == "[redacted]"


@pytest.mark.asyncio
async def test_bootstrap_tiktok_account_starts_worker_workflow(monkeypatch):
    _seed_inventory()
    captured = {}

    async def fake_register_account_record(**kwargs):
        return {
            "registry_persisted": True,
            "registry_id": "registry-tiktok-1",
            "owner_key": kwargs["owner_key"],
            "platform": kwargs["platform"],
            "account_key": kwargs["account_key"],
            "status": kwargs["status"],
            "is_primary": kwargs["is_primary"],
            "plan": kwargs["plan"],
        }

    async def fake_start_account_bootstrap(*, payload, temporal_client=None, wait_for_completion=True):
        captured.update(
            {
                "payload": payload,
                "wait_for_completion": wait_for_completion,
                "temporal_client": temporal_client,
            }
        )
        return {
            "status": "connected",
            "workflow_id": "tiktok-bootstrap-registry-tiktok-1",
            "result": {
                "social_account_id": "registry-tiktok-1",
                "account_handle": "creator-vn",
                "connection_status": "connected",
            },
        }

    monkeypatch.setattr(
        ProxyManagerService,
        "register_account_record",
        fake_register_account_record,
    )
    monkeypatch.setattr(
        accounts.TikTokOrchestrationService,
        "start_account_bootstrap",
        fake_start_account_bootstrap,
    )

    body = await accounts.bootstrap_tiktok_account(
        {
            "owner_key": "owner-3",
            "account_key": "creator-vn",
            "persona_config": {"country_code": "VN", "name": "Minh"},
        }
    )

    assert body["status"] == "connected"
    assert body["registry"]["registry_id"] == "registry-tiktok-1"
    assert captured["payload"]["social_account_id"] == "registry-tiktok-1"
    assert captured["wait_for_completion"] is True
    assert body["account"]["connection_status"] == "connected"


@pytest.mark.asyncio
async def test_refresh_tiktok_account_starts_worker_workflow(monkeypatch):
    async def fake_start_account_refresh(*, payload, temporal_client=None, wait_for_completion=True):
        assert temporal_client is None
        assert wait_for_completion is False
        assert payload == {"social_account_id": "social-123"}
        return {
            "status": "started",
            "workflow_id": "tiktok-refresh-social-123-abcd12",
        }

    monkeypatch.setattr(
        accounts.TikTokOrchestrationService,
        "start_account_refresh",
        fake_start_account_refresh,
    )

    body = await accounts.refresh_tiktok_account(
        {
            "social_account_id": "social-123",
            "wait_for_completion": False,
        }
    )

    assert body["status"] == "started"
    assert body["workflow"]["workflow_id"].startswith("tiktok-refresh-social-123")
