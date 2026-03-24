import pytest

from services.proxy_manager_service import ProxyManagerService
from services.region_service import RegionService


@pytest.fixture(autouse=True)
def reset_proxy_state():
    ProxyManagerService.reset_state()
    yield
    ProxyManagerService.reset_state()


def test_refresh_inventory_parses_env_like_proxy_entries():
    inventory = ProxyManagerService.refresh_inventory(
        [
            "http://proxy-vn.example:8000|country=VN|region=Da Nang|label=vn-1",
            "http://proxy-us.example:8001|country=US|region=New York|label=us-1",
        ]
    )

    assert len(inventory) == 2
    assert inventory[0].country_code == "VN"
    assert inventory[1].region == "New York"
    assert inventory[0].to_dict()["server"] == "http://proxy-vn.example:8000"
    assert "password" not in inventory[0].to_dict()


@pytest.mark.asyncio
async def test_lease_proxy_is_sticky_and_region_aware():
    ProxyManagerService.refresh_inventory(
        [
            "http://proxy-vn.example:8000|country=VN|region=Da Nang|label=vn-1",
            "http://proxy-us.example:8001|country=US|region=New York|label=us-1",
        ]
    )

    first_lease = await ProxyManagerService.lease_proxy(
        account_key="creator-a",
        platform="tiktok",
        region_code="VN",
    )
    second_lease = await ProxyManagerService.lease_proxy(
        account_key="creator-a",
        platform="tiktok",
        region_code="VN",
    )
    us_lease = await ProxyManagerService.lease_proxy(
        account_key="creator-b",
        platform="facebook",
        region_code="US",
    )

    assert first_lease["lease_id"] == second_lease["lease_id"]
    assert first_lease["proxy_details"]["country_code"] == "VN"
    assert us_lease["proxy_details"]["country_code"] == "US"
    assert "password" not in first_lease["proxy"]
    assert "username" not in first_lease["proxy_details"]


@pytest.mark.asyncio
async def test_build_onboarding_plan_sets_platform_policy_and_browser_profile():
    ProxyManagerService.refresh_inventory(
        ["http://proxy-vn.example:8000|country=VN|region=Da Nang|label=vn-1"]
    )

    tiktok_plan = await ProxyManagerService.build_onboarding_plan(
        account_key="creator-vn",
        platform="tiktok",
        persona_config={"country_code": "VN", "name": "Minh"},
    )
    youtube_plan = await ProxyManagerService.build_onboarding_plan(
        account_key="creator-yt",
        platform="youtube",
        persona_config={"country_code": "US", "name": "Studio"},
    )

    assert tiktok_plan["account_type"] == "proxy_bootstrap"
    assert tiktok_plan["bootstrap_mode"] == "human_assisted"
    assert tiktok_plan["browser_context"]["locale"] == "vi-VN"
    assert "manual review" in " ".join(tiktok_plan["steps"])

    assert youtube_plan["account_type"] == "primary_oauth"
    assert youtube_plan["conservative"] is True
    assert youtube_plan["browser_context"]["locale"] == "en-US"
    assert any("OAuth" in note for note in youtube_plan["platform_policy"]["notes"])


def test_region_service_build_browser_context_settings_is_region_aware():
    region_service = RegionService()
    context = region_service.build_browser_context_settings(
        region_info={
            "country": "Vietnam",
            "countryCode": "VN",
            "region": "Da Nang",
            "city": "Da Nang",
            "timezone": "Asia/Ho_Chi_Minh",
            "continent": "asia",
            "locale": "vi-VN",
        },
        platform="tiktok",
    )

    assert context["locale"] == "vi-VN"
    assert context["is_mobile"] is True
    assert context["timezone_id"] == "Asia/Ho_Chi_Minh"
