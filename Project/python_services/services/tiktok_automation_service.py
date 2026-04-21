"""
TikTok browser automation for account bootstrap, session refresh, and publishing.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

import httpx

from config.settings import settings
from services.account_connection_service import AccountConnectionService
from services.browser_automation import BrowserAutomationService
from services.customer_token_vault import CustomerTokenVault
from services.errors import (
    TikTokAutomationAuthError,
    TikTokAutomationConfigurationError,
    TikTokAutomationRetryableError,
)
from services.tiktok_temp_email_service import TikTokTempEmailService

logger = logging.getLogger(__name__)


def _coerce_json_map(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TikTokAutomationService:
    EXPLORE_URL = "https://www.tiktok.com/explore"
    UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
    VIDEO_URL_RE = re.compile(
        r"https?://(?:www\.)?tiktok\.com/@[^/\s?#]+/video/(?P<video_id>\d+)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        browser_service_class: type[BrowserAutomationService] = BrowserAutomationService,
        temp_email_service_class: type[TikTokTempEmailService] = TikTokTempEmailService,
    ) -> None:
        self.browser_service_class = browser_service_class
        self.temp_email_service_class = temp_email_service_class

    @staticmethod
    def build_caption(content: str, hashtags: Optional[Iterable[str]] = None) -> str:
        text = str(content or "").strip()
        normalized_tags = []
        seen = set()
        for tag in hashtags or []:
            normalized = str(tag or "").strip()
            if not normalized:
                continue
            normalized = normalized.replace(" ", "")
            if not normalized.startswith("#"):
                normalized = f"#{normalized}"
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized_tags.append(normalized)

        tag_block = " ".join(normalized_tags).strip()
        if text and tag_block:
            return f"{text}\n\n{tag_block}"
        return text or tag_block

    @staticmethod
    def _generated_password() -> str:
        return f"TikTokAuto.{secrets.token_urlsafe(10)}"

    @staticmethod
    def _generated_username(seed: str) -> str:
        base = "".join(ch for ch in str(seed or "").split("@", 1)[0] if ch.isalnum()).lower()
        if len(base) < 4:
            base = f"creator{secrets.token_hex(3)}"
        suffix = secrets.token_hex(3)
        return f"{base[:18]}{suffix}"

    @staticmethod
    def _profile_name_from_account(account: Dict[str, Any]) -> Optional[str]:
        proxy_config = _coerce_json_map(account.get("proxy_config"))
        browser_profile = _coerce_json_map(proxy_config.get("browser_profile"))
        profile_name = str(browser_profile.get("profile_name") or "").strip()
        if profile_name:
            return profile_name

        storage_state_path = str(browser_profile.get("storage_state_path") or "").strip()
        marker = "/app/browser_profiles/"
        if marker in storage_state_path:
            suffix = storage_state_path.split(marker, 1)[1]
            if suffix.endswith("/storage_state.json"):
                return suffix[: -len("/storage_state.json")]
        return None

    @staticmethod
    def _proxy_config_from_account(account: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        proxy_config = _coerce_json_map(account.get("proxy_config"))
        proxy_lease = _coerce_json_map(proxy_config.get("proxy_lease"))
        proxy = _coerce_json_map(proxy_lease.get("proxy"))
        return proxy or None

    @staticmethod
    def _region_info_from_account(account: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response_payload = _coerce_json_map(account.get("last_api_response"))
        region = _coerce_json_map(response_payload.get("region"))
        if region:
            return region
        plan = _coerce_json_map(response_payload.get("plan"))
        return _coerce_json_map(plan.get("region")) or None

    @staticmethod
    def _credentials_from_account(account: Dict[str, Any]) -> Dict[str, Any]:
        encrypted_bundle = account.get("encrypted_token_bundle")
        if not encrypted_bundle:
            return {}
        try:
            return CustomerTokenVault.open(str(encrypted_bundle))
        except Exception as exc:
            raise TikTokAutomationAuthError(
                "TikTok account credentials are unreadable."
            ) from exc

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    async def _solve_captcha_if_present(self, page: Any, *, step_name: str) -> None:
        api_key = str(settings.TIKTOK_SADCAPTCHA_API_KEY or "").strip()
        if not api_key:
            logger.info("TikTok captcha solve skipped at %s: missing API key", step_name)
            return

        try:
            from tiktok_captcha_solver import PlaywrightSolver  # type: ignore
        except Exception:
            logger.info("TikTok captcha solver package unavailable at %s", step_name)
            return

        try:
            solver = PlaywrightSolver(page=page, sadcaptcha_api_key=api_key)
            present = await self._maybe_await(solver.captcha_is_present())
            if present:
                await self._maybe_await(solver.solve_captcha_if_present())
                logger.info("TikTok captcha solved at %s", step_name)
        except Exception as exc:
            logger.warning("TikTok captcha solve failed at %s: %s", step_name, exc)

    async def _locator_visible(
        self,
        page: Any,
        selector: str,
        *,
        timeout_ms: int = 3_000,
    ) -> bool:
        try:
            locator = page.locator(selector).first
            await locator.wait_for(state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    async def _has_upload_ui(self, page: Any) -> bool:
        selectors = [
            "input[type='file']",
            "button[data-e2e='select_video_button']",
            "button:has-text('Select video')",
            "[data-e2e='post_video_button']",
        ]
        for selector in selectors:
            if await self._locator_visible(page, selector, timeout_ms=2_000):
                return True
        return False

    async def _fill_first_matching_input(
        self,
        page: Any,
        selectors: list[str],
        value: str,
        *,
        timeout_ms: int = 30_000,
    ) -> None:
        last_error: Exception | None = None
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                await locator.click(timeout=timeout_ms, force=True)
                await locator.fill(value, timeout=timeout_ms)
                return
            except Exception as exc:
                last_error = exc
        raise TikTokAutomationRetryableError(
            f"Unable to fill TikTok input for selectors={selectors}"
        ) from last_error

    async def _click_first_matching(
        self,
        page: Any,
        selectors: list[str],
        *,
        timeout_ms: int = 30_000,
        force: bool = True,
    ) -> None:
        last_error: Exception | None = None
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                await locator.click(timeout=timeout_ms, force=force)
                return
            except Exception as exc:
                last_error = exc
        raise TikTokAutomationRetryableError(
            f"Unable to click TikTok selector set={selectors}"
        ) from last_error

    async def _click_when_enabled(
        self,
        page: Any,
        selectors: list[str],
        *,
        timeout_ms: int = 30_000,
    ) -> None:
        last_error: Exception | None = None
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                for _ in range(40):
                    disabled = await locator.get_attribute("disabled")
                    if disabled is None:
                        await locator.click(timeout=timeout_ms, force=True)
                        return
                    await asyncio.sleep(0.25)
                raise TikTokAutomationRetryableError(
                    f"TikTok button stayed disabled for selector={selector}"
                )
            except Exception as exc:
                last_error = exc
        raise TikTokAutomationRetryableError(
            f"Unable to click enabled TikTok selector set={selectors}"
        ) from last_error

    async def _otp_error_present(self, page: Any) -> bool:
        patterns = [
            "Verification code is expired or incorrect",
            "verification code is expired",
            "Try again",
            "expired",
            "incorrect",
            "Mã xác minh",
            "hết hạn",
            "không đúng",
            "Thử lại",
        ]
        for pattern in patterns:
            try:
                locator = page.locator(f"text={pattern}").first
                await locator.wait_for(state="visible", timeout=2_000)
                return True
            except Exception:
                continue
        return False

    async def _select_birth_date(self, page: Any) -> None:
        containers = page.locator("[data-e2e='select-container']")
        await containers.first.wait_for(state="visible", timeout=60_000)

        await containers.nth(0).click(timeout=30_000)
        await page.locator("#Month-options-item-0").first.click(timeout=30_000)
        await asyncio.sleep(0.5)

        await containers.nth(1).click(timeout=30_000)
        await page.locator("#Day-options-item-0").first.click(timeout=30_000)
        await asyncio.sleep(0.5)

        await containers.nth(2).click(timeout=30_000)
        await self._click_first_matching(
            page,
            [
                "#Year-options-list-container [role='option']:has-text('2000')",
                "#Year-options-item-25",
            ],
        )
        await asyncio.sleep(0.5)

    async def _click_send_code_and_verify(self, page: Any) -> None:
        button = page.locator("[data-e2e='send-code-button']").first
        await button.wait_for(state="visible", timeout=60_000)

        for _ in range(3):
            text_before = (await button.inner_text(timeout=30_000)).strip()
            disabled_before = await button.get_attribute("disabled")
            await button.scroll_into_view_if_needed(timeout=30_000)
            await button.click(timeout=30_000, force=True)
            await asyncio.sleep(2)
            text_after = (await button.inner_text(timeout=30_000)).strip()
            disabled_after = await button.get_attribute("disabled")
            if text_after != text_before or disabled_after != disabled_before:
                return
        raise TikTokAutomationRetryableError("TikTok signup send-code click was not confirmed.")

    async def _start_signup_and_send_code(
        self,
        page: Any,
        *,
        email: str,
        password: str,
    ) -> None:
        await page.goto(self.EXPLORE_URL, wait_until="domcontentloaded", timeout=60_000)
        await self._click_first_matching(
            page,
            [
                "#top-right-action-bar-login-button",
                "#header-login-button",
            ],
        )
        await asyncio.sleep(1)
        await self._click_first_matching(
            page,
            [
                "a:has-text('Sign up')",
                "a:has-text('Đăng ký')",
                "span:has-text('Sign up')",
                "span:has-text('Đăng ký')",
            ],
        )
        await asyncio.sleep(1)
        await self._click_first_matching(
            page,
            [
                "[data-e2e='channel-item']:has-text('Use phone or email')",
                "[data-e2e='channel-item']:has-text('Sử dụng số điện thoại hoặc email')",
                "div[role='link']:has-text('Use phone or email')",
            ],
        )
        await asyncio.sleep(1)
        await self._click_first_matching(
            page,
            [
                "a[href*='/signup/phone-or-email/email']",
                "a:has-text('Sign up with email')",
                "a:has-text('Đăng ký bằng email')",
                "span:has-text('Sign up with email')",
            ],
        )
        await asyncio.sleep(1)
        await self._select_birth_date(page)
        await self._fill_first_matching_input(
            page,
            [
                "input[name='email']",
                "input[placeholder*='Email']",
                "input[autocomplete='username']",
            ],
            email,
        )
        await self._fill_first_matching_input(
            page,
            [
                "input[type='password']",
                "input[name='password']",
                "input[placeholder*='Password']",
                "input[autocomplete='new-password']",
            ],
            password,
        )
        await self._click_send_code_and_verify(page)

    async def _fill_verification_code_and_continue(
        self,
        page: Any,
        *,
        verification_code: str,
    ) -> None:
        await asyncio.sleep(3)
        await self._fill_first_matching_input(
            page,
            [
                "input[placeholder='Enter 6-digit code']",
                "input[placeholder*='6-digit code']",
                "input[data-testid='tux-web-input']",
            ],
            verification_code,
        )
        await asyncio.sleep(2)
        await self._click_when_enabled(
            page,
            [
                "button[type='submit']:has-text('Next')",
                "button:has-text('Next')",
                "button[data-testid='tux-web-button']",
            ],
        )
        await asyncio.sleep(2)
        await self._solve_captcha_if_present(page, step_name="signup_after_otp_next")

    async def _fill_username_and_signup(
        self,
        page: Any,
        *,
        preferred_username: str,
    ) -> str:
        candidates = [preferred_username, self._generated_username(preferred_username)]
        for candidate in candidates:
            try:
                await self._fill_first_matching_input(
                    page,
                    [
                        "input[name='username']",
                        "input[placeholder*='Username']",
                        "input[placeholder*='username']",
                    ],
                    candidate,
                )
                await self._click_first_matching(
                    page,
                    [
                        "button[type='submit']:has-text('Sign up')",
                        "button:has-text('Sign up')",
                    ],
                )
                return candidate
            except Exception:
                continue
        raise TikTokAutomationRetryableError("TikTok signup username submission failed.")

    async def _click_email_login_entry(self, page: Any) -> None:
        for selector in ["#top-right-action-bar-login-button", "#header-login-button"]:
            try:
                locator = page.locator(selector).first
                await locator.wait_for(state="visible", timeout=5_000)
                await locator.click(timeout=5_000, force=True)
                await asyncio.sleep(1)
                break
            except Exception:
                continue

        await self._click_first_matching(
            page,
            [
                "[data-e2e='channel-item']:has-text('Use phone / email / username')",
                "[data-e2e='channel-item']:has-text('Use phone / email')",
                "[data-e2e='channel-item']:has-text('Use phone or email')",
                "[data-e2e='channel-item']:has-text('Số điện thoại / email / tên người dùng')",
            ],
        )
        await self._click_first_matching(
            page,
            [
                "a[href*='/login/phone-or-email/email']",
                "a:has-text('Log in with email')",
                "a:has-text('Đăng nhập bằng email')",
            ],
        )

    async def _click_otp_entry(self, page: Any) -> None:
        await self._click_first_matching(
            page,
            [
                "div.pc-home-item-IxNc0F",
                "div[class*='pc-home-item-']:has-text('Email')",
            ],
            timeout_ms=60_000,
        )

    async def _fill_otp_code_and_continue(self, page: Any, *, code: str) -> None:
        selectors = [
            "input[placeholder='Enter 6-digit code'][data-testid='tux-web-input']",
            "input[data-testid='tux-web-input']",
            "input[placeholder*='Enter 6-digit code']",
        ]

        last_error: Exception | None = None
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=60_000)
                await locator.click(timeout=30_000, force=True)
                await locator.press("Control+A", timeout=30_000)
                await locator.type(code, delay=15, timeout=30_000)
                current_value = (await locator.input_value(timeout=30_000)).strip()
                if current_value == code:
                    break
            except Exception as exc:
                last_error = exc
        else:
            raise TikTokAutomationRetryableError("Unable to set TikTok OTP input.") from last_error

        await asyncio.sleep(5)
        await self._click_when_enabled(
            page,
            [
                "button:has-text('Next')",
                "button[data-testid='tux-web-button']",
            ],
            timeout_ms=60_000,
        )

    async def _login_account(self, page: Any, *, email: str, password: str) -> None:
        await page.goto(self.EXPLORE_URL, wait_until="domcontentloaded", timeout=60_000)
        await asyncio.sleep(float(settings.TIKTOK_WAIT_AFTER_OPEN_SECONDS))
        await self._click_email_login_entry(page)
        await self._fill_first_matching_input(
            page,
            [
                "input[placeholder='Email or username'][name='username']",
                "input[placeholder*='Email or username']",
                "input[name='username']",
            ],
            email,
        )
        await self._fill_first_matching_input(
            page,
            [
                "input[type='password'][placeholder='Password']",
                "input[placeholder*='Password'][type='password']",
                "input[type='password']",
            ],
            password,
        )

        await asyncio.sleep(5)
        await self._click_when_enabled(
            page,
            [
                "button[data-e2e='login-button']",
                "[data-e2e='login-button'] button[type='submit']",
            ],
        )
        await asyncio.sleep(float(settings.TIKTOK_WAIT_AFTER_LOGIN_CLICK_SECONDS))
        await self._solve_captcha_if_present(page, step_name="after_login_click")
        await self._click_otp_entry(page)
        await asyncio.sleep(2)
        await self._solve_captcha_if_present(page, step_name="after_otp_entry_click")

        previous_code: Optional[str] = None
        for _ in range(3):
            await asyncio.sleep(float(settings.TIKTOK_WAIT_BEFORE_FETCH_OTP_SECONDS))
            code = await self.temp_email_service_class.fetch_verification_code(
                email,
                previous_code=previous_code,
                timeout_seconds=120,
            )
            await self._fill_otp_code_and_continue(page, code=code)
            await asyncio.sleep(float(settings.TIKTOK_WAIT_AFTER_OTP_NEXT_SECONDS))
            await self._solve_captcha_if_present(page, step_name="after_otp_next")
            if not await self._otp_error_present(page):
                return
            previous_code = code
            try:
                resend_button = page.locator(
                    "[data-e2e='send-code-button'], button:has-text('Resend'), button:has-text('Send code')"
                ).first
                await resend_button.wait_for(state="visible", timeout=5_000)
                await resend_button.click(timeout=5_000, force=True)
            except Exception:
                pass
            await asyncio.sleep(float(settings.TIKTOK_WAIT_AFTER_RESEND_SECONDS))

        raise TikTokAutomationAuthError("TikTok OTP login failed after retries.")

    async def _open_upload_page(self, page: Any) -> Any:
        await page.goto(self.UPLOAD_URL, wait_until="domcontentloaded", timeout=60_000)
        if await self._has_upload_ui(page):
            return page

        await page.goto(self.EXPLORE_URL, wait_until="domcontentloaded", timeout=60_000)
        if await self._has_upload_ui(page):
            return page

        for selector in ["button[aria-label='Upload']", "a[href*='upload']"]:
            try:
                button = page.locator(selector).first
                await button.wait_for(state="visible", timeout=5_000)
                await button.click(timeout=30_000, force=True)
                await asyncio.sleep(3)
            except Exception:
                continue

            for candidate in page.context.pages:
                if await self._has_upload_ui(candidate):
                    return candidate

        raise TikTokAutomationRetryableError("TikTok upload UI was not found.")

    async def _upload_video(self, page: Any, video_path: Path) -> None:
        file_input = page.locator("input[type='file']").first
        try:
            await file_input.wait_for(state="attached", timeout=8_000)
            await file_input.set_input_files(str(video_path))
            await asyncio.sleep(3)
            return
        except Exception:
            pass

        button = page.locator("button[data-e2e='select_video_button']").first
        try:
            await button.wait_for(state="visible", timeout=20_000)
        except Exception:
            button = page.locator("button:has-text('Select video')").first
            await button.wait_for(state="visible", timeout=20_000)

        async with page.expect_file_chooser(timeout=30_000) as chooser_info:
            await button.click(timeout=30_000, force=True)
        chooser = await chooser_info.value
        await chooser.set_files(str(video_path))
        await asyncio.sleep(5)

    async def _fill_caption(self, page: Any, caption_text: str) -> None:
        if not caption_text:
            return
        editor = page.locator("div[contenteditable='true']").first
        await editor.wait_for(state="visible", timeout=90_000)
        await editor.click(timeout=30_000, force=True)
        await asyncio.sleep(1)
        await editor.press("Control+A", timeout=30_000)
        await asyncio.sleep(1)
        await page.keyboard.type(caption_text, delay=10)
        await asyncio.sleep(1)

    async def _click_blank_area(self, page: Any) -> None:
        try:
            await page.locator("body").first.click(
                timeout=30_000,
                force=True,
                position={"x": 5, "y": 5},
            )
        except Exception:
            await page.mouse.click(5, 5)
        await asyncio.sleep(2)

    async def _disable_checked_switch(self, page: Any) -> None:
        await asyncio.sleep(15)
        switch = page.locator("div.Switch__content").first
        try:
            await switch.wait_for(state="visible", timeout=60_000)
        except Exception:
            return

        data_state = (await switch.get_attribute("data-state") or "").strip()
        aria_checked = (await switch.get_attribute("aria-checked") or "").strip().lower()
        if data_state == "checked" and aria_checked == "true":
            await switch.click(timeout=60_000, force=True)
            await asyncio.sleep(1)

    async def _click_post(self, page: Any) -> None:
        await self._click_blank_area(page)
        await self._disable_checked_switch(page)
        await asyncio.sleep(10)
        button = page.locator("[data-e2e='post_video_button']").first
        await button.wait_for(
            state="visible",
            timeout=int(settings.TIKTOK_UPLOAD_TIMEOUT_SECONDS) * 1000,
        )
        await button.click(
            timeout=int(settings.TIKTOK_UPLOAD_TIMEOUT_SECONDS) * 1000,
            force=True,
        )
        await asyncio.sleep(10)

    async def _publish_confirmation_visible(self, page: Any) -> bool:
        selectors = [
            "a[href*='/video/']",
            "a:has-text('Manage posts')",
            "a:has-text('Upload another video')",
            "a:has-text('View profile')",
            "text=Your video is being uploaded",
            "text=Uploaded",
        ]
        for selector in selectors:
            if await self._locator_visible(page, selector, timeout_ms=2_000):
                return True
        current_url = str(getattr(page, "url", "") or "")
        return "tiktokstudio" in current_url and current_url != self.UPLOAD_URL

    async def _extract_post_reference(self, page: Any) -> Dict[str, Optional[str]]:
        candidates = [str(getattr(page, "url", "") or "").strip()]
        try:
            hrefs = await page.locator("a[href*='/video/']").evaluate_all(
                "(els) => els.map((el) => el.href || el.getAttribute('href') || '')"
            )
            candidates.extend(str(item or "").strip() for item in hrefs)
        except Exception:
            pass

        for candidate in candidates:
            if not candidate:
                continue
            match = self.VIDEO_URL_RE.search(candidate)
            if not match:
                continue
            post_url = candidate.split("?", 1)[0]
            video_id = match.group("video_id")
            return {
                "platform_post_id": video_id,
                "provider_post_id": video_id,
                "post_url": post_url,
            }
        return {
            "platform_post_id": None,
            "provider_post_id": None,
            "post_url": None,
        }

    async def _confirm_post_published(self, page: Any) -> Dict[str, Optional[str]]:
        wait_timeout_seconds = max(30, int(settings.TIKTOK_UPLOAD_TIMEOUT_SECONDS))
        deadline = asyncio.get_running_loop().time() + wait_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            reference = await self._extract_post_reference(page)
            if reference.get("post_url"):
                return reference
            if await self._publish_confirmation_visible(page):
                return reference
            await asyncio.sleep(2)

        raise TikTokAutomationRetryableError(
            "TikTok post submission was not confirmed."
        )

    async def _download_media_file(self, url: str) -> Path:
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix or ".mp4"
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        handle.close()
        target = Path(handle.name)
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            target.write_bytes(response.content)
            if target.stat().st_size == 0:
                raise TikTokAutomationRetryableError("Downloaded TikTok media file is empty.")
            return target
        except httpx.HTTPError as exc:
            target.unlink(missing_ok=True)
            raise TikTokAutomationRetryableError(
                f"Failed to download TikTok media from {url}."
            ) from exc

    async def _initialize_browser_for_account(
        self,
        account: Dict[str, Any],
    ) -> BrowserAutomationService:
        browser_service = self.browser_service_class()
        await browser_service.initialize_browser(
            proxy_config=self._proxy_config_from_account(account),
            region_info=self._region_info_from_account(account),
            platform="tiktok",
            profile_name=self._profile_name_from_account(account),
        )
        return browser_service

    async def bootstrap_account(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.TIKTOK_AUTOMATION_ENABLED:
            raise TikTokAutomationConfigurationError("TikTok automation is disabled.")

        social_account_id = str(payload.get("social_account_id") or "").strip()
        if not social_account_id:
            raise TikTokAutomationConfigurationError("social_account_id is required for TikTok bootstrap.")

        account = await AccountConnectionService.get_account_by_id(social_account_id)
        if not account:
            raise TikTokAutomationConfigurationError("Prepared TikTok social account was not found.")

        email = await self.temp_email_service_class.generate_email()
        password = str(payload.get("password") or self._generated_password())
        desired_username = str(
            payload.get("desired_username")
            or payload.get("username")
            or self._generated_username(email)
        )

        browser_service = await self._initialize_browser_for_account(account)
        page = await browser_service.context.new_page()  # type: ignore[union-attr]
        final_username = desired_username
        try:
            await self._start_signup_and_send_code(page, email=email, password=password)
            verification_code = await self.temp_email_service_class.fetch_verification_code(
                email
            )
            await self._fill_verification_code_and_continue(
                page,
                verification_code=verification_code,
            )
            final_username = await self._fill_username_and_signup(
                page,
                preferred_username=desired_username,
            )
        finally:
            await browser_service.close()

        updated = await AccountConnectionService.upsert_browser_session_account(
            user_id=str(account["user_id"]),
            social_account_id=social_account_id,
            platform="tiktok",
            account_name=final_username or email,
            account_handle=final_username or email.split("@", 1)[0],
            display_name=final_username or email,
            provider_account_id=email,
            encrypted_bundle_payload={
                "email": email,
                "password": password,
                "username": final_username,
                "provider": str(settings.TIKTOK_TEMP_EMAIL_PROVIDER or "tinyhost"),
                "updated_at": _utcnow().isoformat(),
            },
            token_expires_at=_utcnow() + timedelta(days=7),
            publish_capabilities={
                "direct_publish": True,
                "platform": "tiktok",
                "strategy": "tiktok_browser_automation",
            },
            proxy_config={
                "browser_profile": _coerce_json_map(
                    _coerce_json_map(account.get("proxy_config")).get("browser_profile")
                ),
            },
            last_api_response={
                "bootstrap": {
                    "email": email,
                    "username": final_username,
                    "completed_at": _utcnow().isoformat(),
                }
            },
            is_primary=bool(account.get("is_primary")),
            is_active=True,
            connection_status="connected",
            connection_method="browser_session",
            last_error=None,
        )
        return {
            "status": "connected",
            "social_account_id": str(updated["id"]),
            "user_id": str(updated["user_id"]),
            "platform": "tiktok",
            "account_handle": updated.get("account_handle"),
            "display_name": updated.get("display_name"),
            "connection_status": updated.get("connection_status"),
            "browser_profile": _coerce_json_map(updated.get("proxy_config")).get("browser_profile"),
            "credentials_stored": True,
            "email": email,
        }

    async def refresh_account_session(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.TIKTOK_AUTOMATION_ENABLED:
            raise TikTokAutomationConfigurationError("TikTok automation is disabled.")

        social_account_id = str(payload.get("social_account_id") or "").strip()
        if not social_account_id:
            raise TikTokAutomationConfigurationError("social_account_id is required for TikTok session refresh.")

        account = await AccountConnectionService.get_account_by_id(social_account_id)
        if not account:
            raise TikTokAutomationConfigurationError("TikTok social account was not found.")

        credentials = self._credentials_from_account(account)
        email = str(credentials.get("email") or "").strip()
        password = str(credentials.get("password") or "").strip()
        if not email or not password:
            raise TikTokAutomationAuthError("TikTok account credentials are missing.")

        browser_service = await self._initialize_browser_for_account(account)
        page = await browser_service.context.new_page()  # type: ignore[union-attr]
        try:
            await self._login_account(page, email=email, password=password)
        finally:
            await browser_service.close()

        updated = await AccountConnectionService.upsert_browser_session_account(
            user_id=str(account["user_id"]),
            social_account_id=social_account_id,
            platform="tiktok",
            account_name=str(account.get("account_name") or email),
            account_handle=str(account.get("account_handle") or email.split("@", 1)[0]),
            display_name=str(account.get("display_name") or email),
            provider_account_id=str(account.get("provider_account_id") or email),
            encrypted_bundle_payload={
                **credentials,
                "updated_at": _utcnow().isoformat(),
            },
            token_expires_at=_utcnow() + timedelta(days=7),
            publish_capabilities={
                "direct_publish": True,
                "platform": "tiktok",
                "strategy": "tiktok_browser_automation",
            },
            proxy_config={
                "browser_profile": _coerce_json_map(
                    _coerce_json_map(account.get("proxy_config")).get("browser_profile")
                ),
            },
            last_api_response={
                "session_refresh": {
                    "completed_at": _utcnow().isoformat(),
                }
            },
            is_primary=bool(account.get("is_primary")),
            is_active=True,
            connection_status="connected",
            connection_method="browser_session",
            last_error=None,
        )
        return {
            "status": "connected",
            "social_account_id": str(updated["id"]),
            "platform": "tiktok",
            "account_handle": updated.get("account_handle"),
            "connection_status": updated.get("connection_status"),
            "refreshed_at": _utcnow().isoformat(),
        }

    @staticmethod
    def _session_expired(account: Dict[str, Any]) -> bool:
        token_expires_at = account.get("token_expires_at")
        if not token_expires_at:
            return False
        if isinstance(token_expires_at, str):
            try:
                token_expires_at = datetime.fromisoformat(token_expires_at)
            except ValueError:
                return False
        if token_expires_at.tzinfo is None:
            token_expires_at = token_expires_at.replace(tzinfo=timezone.utc)
        return token_expires_at <= _utcnow()

    async def publish_post(self, post_config: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.TIKTOK_AUTOMATION_ENABLED:
            raise TikTokAutomationConfigurationError("TikTok automation is disabled.")

        media_urls = [
            str(item.get("storage_url") or item.get("url") or "").strip()
            for item in post_config.get("media", [])
            if str(item.get("storage_url") or item.get("url") or "").strip()
        ]
        if len(media_urls) != 1:
            raise TikTokAutomationConfigurationError(
                "TikTok automation requires exactly one video asset."
            )

        user_id = str(post_config.get("user_id") or "").strip()
        if not user_id:
            raise TikTokAutomationConfigurationError("TikTok publish requires user_id.")

        social_account_id = str(post_config.get("social_account_id") or "").strip() or None
        if social_account_id:
            account = await AccountConnectionService.get_account_by_id(
                social_account_id,
                user_id=user_id,
            )
        else:
            account = await AccountConnectionService.get_connected_account(
                user_id=user_id,
                platform="tiktok",
            )
        if not account or not account.get("is_active"):
            raise TikTokAutomationAuthError(
                "No active TikTok browser-session account is connected."
            )

        credentials = self._credentials_from_account(account)
        email = str(credentials.get("email") or "").strip()
        password = str(credentials.get("password") or "").strip()
        if not email or not password:
            raise TikTokAutomationAuthError("TikTok publish credentials are missing.")

        if self._session_expired(account):
            await self.refresh_account_session(
                {"social_account_id": str(account["id"])}
            )
            account = await AccountConnectionService.get_account_by_id(
                str(account["id"]),
                user_id=user_id,
            ) or account

        local_media_path = await self._download_media_file(media_urls[0])
        browser_service = await self._initialize_browser_for_account(account)
        page = await browser_service.context.new_page()  # type: ignore[union-attr]
        post_reference: Dict[str, Optional[str]] = {
            "platform_post_id": None,
            "provider_post_id": None,
            "post_url": None,
        }
        try:
            try:
                studio_page = await self._open_upload_page(page)
            except Exception:
                await self._login_account(page, email=email, password=password)
                studio_page = await self._open_upload_page(page)

            await self._upload_video(studio_page, local_media_path)
            await self._fill_caption(
                studio_page,
                self.build_caption(
                    str(post_config.get("content") or ""),
                    post_config.get("hashtags") or [],
                ),
            )
            await self._click_post(studio_page)
            post_reference = await self._confirm_post_published(studio_page)
        finally:
            await browser_service.close()
            local_media_path.unlink(missing_ok=True)

        updated = await AccountConnectionService.upsert_browser_session_account(
            user_id=user_id,
            social_account_id=str(account["id"]),
            platform="tiktok",
            account_name=str(account.get("account_name") or email),
            account_handle=str(account.get("account_handle") or email.split("@", 1)[0]),
            display_name=str(account.get("display_name") or email),
            provider_account_id=str(account.get("provider_account_id") or email),
            encrypted_bundle_payload={
                **credentials,
                "updated_at": _utcnow().isoformat(),
            },
            token_expires_at=_utcnow() + timedelta(days=7),
            publish_capabilities={
                "direct_publish": True,
                "platform": "tiktok",
                "strategy": "tiktok_browser_automation",
            },
            is_primary=bool(account.get("is_primary")),
            is_active=True,
            connection_status="connected",
            connection_method="browser_session",
            last_error=None,
        )

        return {
            "status": "published",
            "published_at": _utcnow().isoformat(),
            "platform_post_id": post_reference.get("platform_post_id"),
            "provider_post_id": post_reference.get("provider_post_id"),
            "post_url": post_reference.get("post_url"),
            "provider_status": "published",
            "method": "tiktok_browser_automation",
            "raw": {
                "social_account_id": str(updated["id"]),
                "account_handle": updated.get("account_handle"),
                "media_source": media_urls[0],
                "post_reference_confirmed": bool(post_reference.get("post_url")),
            },
        }
