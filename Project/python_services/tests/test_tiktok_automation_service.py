from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.settings import settings
from services.account_connection_service import AccountConnectionService
from services.customer_token_vault import CustomerTokenVault
from services.errors import TikTokAutomationConfigurationError
from services.tiktok_automation_service import TikTokAutomationService


def test_build_caption_deduplicates_and_normalizes_hashtags():
    caption = TikTokAutomationService.build_caption(
        "Launch today",
        ["AppReview", "#AppReview", "TikTokReview"],
    )

    assert caption == "Launch today\n\n#AppReview #TikTokReview"


@pytest.mark.asyncio
async def test_publish_post_requires_exactly_one_video(monkeypatch):
    monkeypatch.setattr(settings, "TIKTOK_AUTOMATION_ENABLED", True)
    service = TikTokAutomationService()

    with pytest.raises(TikTokAutomationConfigurationError):
        await service.publish_post(
            {
                "platform": "tiktok",
                "user_id": "user-1",
                "content": "Caption",
                "media": [
                    {"storage_url": "https://cdn.example/one.mp4"},
                    {"storage_url": "https://cdn.example/two.mp4"},
                ],
            }
        )


@pytest.mark.asyncio
async def test_publish_post_refreshes_expired_session_before_upload(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settings, "TIKTOK_AUTOMATION_ENABLED", True)
    service = TikTokAutomationService()
    refreshed = {}

    sealed = CustomerTokenVault.seal(
        {
            "email": "creator@example.com",
            "password": "secret-1",
        }
    )
    expired_account = {
        "id": "social-1",
        "user_id": "user-1",
        "platform": "tiktok",
        "is_active": True,
        "is_primary": True,
        "account_name": "Creator",
        "account_handle": "creator",
        "display_name": "Creator",
        "provider_account_id": "creator@example.com",
        "encrypted_token_bundle": sealed,
        "token_expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
        "proxy_config": {"browser_profile": {"profile_name": "tiktok/creator"}},
    }

    async def fake_get_connected_account(*, user_id, platform):
        assert user_id == "user-1"
        assert platform == "tiktok"
        return expired_account

    async def fake_get_account_by_id(_social_account_id, *, user_id=None):
        assert user_id == "user-1"
        return expired_account

    async def fake_refresh_account_session(payload):
        refreshed.update(payload)
        return {"status": "connected"}

    class _Page:
        pass

    class _Context:
        async def new_page(self):
            return _Page()

    class _BrowserService:
        def __init__(self):
            self.context = _Context()

        async def close(self):
            return None

    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"video")

    monkeypatch.setattr(
        AccountConnectionService,
        "get_connected_account",
        fake_get_connected_account,
    )
    monkeypatch.setattr(
        AccountConnectionService,
        "get_account_by_id",
        fake_get_account_by_id,
    )

    async def fake_upsert_browser_session_account(**kwargs):
        return expired_account

    monkeypatch.setattr(
        AccountConnectionService,
        "upsert_browser_session_account",
        fake_upsert_browser_session_account,
    )
    monkeypatch.setattr(service, "refresh_account_session", fake_refresh_account_session)

    async def fake_download_media_file(_url):
        return video_path

    async def fake_initialize_browser_for_account(_account):
        return _BrowserService()

    async def fake_open_upload_page(page):
        return page

    async def fake_upload_video(page, path):
        assert path == video_path
        return None

    async def fake_fill_caption(page, caption):
        assert caption == "Caption\n\n#AppReview"
        return None

    async def fake_click_post(page):
        return None

    async def fake_confirm_post_published(page):
        return {
            "platform_post_id": "7360001112223334444",
            "provider_post_id": "7360001112223334444",
            "post_url": "https://www.tiktok.com/@creator/video/7360001112223334444",
        }

    monkeypatch.setattr(service, "_download_media_file", fake_download_media_file)
    monkeypatch.setattr(service, "_initialize_browser_for_account", fake_initialize_browser_for_account)
    monkeypatch.setattr(service, "_open_upload_page", fake_open_upload_page)
    monkeypatch.setattr(service, "_upload_video", fake_upload_video)
    monkeypatch.setattr(service, "_fill_caption", fake_fill_caption)
    monkeypatch.setattr(service, "_click_post", fake_click_post)
    monkeypatch.setattr(service, "_confirm_post_published", fake_confirm_post_published)

    result = await service.publish_post(
        {
            "platform": "tiktok",
            "user_id": "user-1",
            "content": "Caption",
            "hashtags": ["AppReview"],
            "media": [{"storage_url": "https://cdn.example/clip.mp4"}],
        }
    )

    assert refreshed == {"social_account_id": "social-1"}
    assert result["method"] == "tiktok_browser_automation"
    assert result["platform_post_id"] == "7360001112223334444"
    assert result["post_url"] == "https://www.tiktok.com/@creator/video/7360001112223334444"
