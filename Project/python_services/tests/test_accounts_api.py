from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import accounts
from services.proxy_manager_service import ProxyManagerService


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(accounts.router, prefix="/api/accounts")
    return TestClient(app)


def _seed_inventory() -> None:
    ProxyManagerService.reset_state()
    ProxyManagerService.refresh_inventory(
        [
            "http://proxy-vn.example:8000|country=VN|region=Da Nang|label=vn-1",
            "http://proxy-us.example:8001|country=US|region=New York|label=us-1",
        ]
    )


def test_plan_onboarding_returns_browser_profile():
    _seed_inventory()
    client = _build_client()

    response = client.post(
        "/api/accounts/onboarding/plan",
        json={
            "platform": "tiktok",
            "account_key": "creator-vn",
            "persona_config": {"country_code": "VN", "name": "Minh"},
        },
    )

    assert response.status_code == 200
    payload = response.json()["plan"]
    assert payload["account_type"] == "proxy_bootstrap"
    assert payload["browser_profile"]["storage_state_path"].endswith(
        "/browser_profiles/tiktok/creator-vn/storage_state.json"
    )
    assert payload["browser_context"]["locale"] == "vi-VN"


def test_execute_onboarding_persists_registry_and_tracks_human_assisted_bootstrap(monkeypatch):
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

    client = _build_client()
    response = client.post(
        "/api/accounts/onboarding/execute",
        json={
            "platform": "facebook",
            "account_key": "creator-fb",
            "owner_key": "owner-1",
            "persona_config": {"country_code": "US", "name": "Creator FB"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "prepared"
    assert body["execution"]["plan"]["browser_profile"]["storage_state_path"].endswith(
        "/browser_profiles/facebook/creator-fb/storage_state.json"
    )
    assert captured["is_primary"] is False
    assert captured["platform"] == "facebook"
    assert captured["status"] == "prepared"


def test_connect_platform_account_registers_primary_oauth(monkeypatch):
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

    client = _build_client()
    response = client.post(
        "/api/accounts/connect/youtube",
        json={
            "owner_key": "owner-2",
            "email": "creator@example.com",
            "oauth_token": "token-123",
            "country_code": "US",
            "name": "Studio Channel",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "connected"
    assert body["registry"]["is_primary"] is True
    assert body["plan"]["account_type"] == "primary_oauth"
    assert captured["is_primary"] is True
    assert captured["platform"] == "youtube"


def test_list_connected_accounts_returns_state_and_registry(monkeypatch):
    _seed_inventory()

    async def fake_list_registry(**_kwargs):
        return {
            "registry_persisted": True,
            "accounts": [{"id": "registry-1", "platform": "tiktok"}],
            "owner_key": None,
            "limit": 100,
        }

    monkeypatch.setattr(ProxyManagerService, "list_registry", fake_list_registry)

    client = _build_client()
    response = client.get("/api/accounts/list")

    assert response.status_code == 200
    body = response.json()
    assert body["registry"]["accounts"][0]["platform"] == "tiktok"
    assert len(body["inventory"]) == 2
    assert "password" not in body["inventory"][0]
    assert body["inventory"][0]["requires_auth"] is True


def test_list_connected_accounts_redacts_registry_secrets(monkeypatch):
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

    client = _build_client()
    response = client.get("/api/accounts/list")

    assert response.status_code == 200
    account = response.json()["registry"]["accounts"][0]
    assert account["oauth_token_present"] is True
    assert account["proxy_config"]["proxy_lease"]["proxy"]["password"] == "[redacted]"
    assert account["last_api_response"]["oauth_token"] == "[redacted]"
