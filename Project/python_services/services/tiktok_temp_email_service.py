"""
Temp-email helpers for TikTok browser automation.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from config.settings import settings
from services.errors import (
    TikTokAutomationConfigurationError,
    TikTokAutomationRetryableError,
)

try:  # pragma: no cover - worker-only dependency
    from playwright.async_api import async_playwright
except ImportError:  # pragma: no cover - exercised in API image
    async_playwright = None

logger = logging.getLogger(__name__)


class TikTokTempEmailService:
    DEFAULT_URL = "https://tinyhost.shop"
    EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    CODE_PATTERN = re.compile(
        r"(\d{6})\s+is your(?:\s+6-digit)?\s+code|(\d{6})\s+is your verification code",
        re.IGNORECASE,
    )

    @classmethod
    def _ensure_provider_available(cls) -> None:
        provider = str(settings.TIKTOK_TEMP_EMAIL_PROVIDER or "tinyhost").strip().lower()
        if provider != "tinyhost":
            raise TikTokAutomationConfigurationError(
                f"Unsupported TikTok temp email provider '{provider}'."
            )
        if async_playwright is None:
            raise TikTokAutomationConfigurationError(
                "TikTok temp email automation requires Playwright in worker runtime."
            )

    @classmethod
    async def generate_email(
        cls,
        *,
        timeout_ms: int = 60_000,
    ) -> str:
        cls._ensure_provider_available()

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            try:
                await page.goto(
                    cls.DEFAULT_URL,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                email_input = page.locator("#email")
                await email_input.wait_for(state="visible", timeout=timeout_ms)
                previous_value = (await email_input.input_value()).strip()
                generate_button = page.locator("button.action-btn.generate-btn")
                await generate_button.wait_for(state="visible", timeout=timeout_ms)
                await generate_button.click(timeout=timeout_ms)

                deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000.0)
                while asyncio.get_running_loop().time() < deadline:
                    value = (await email_input.input_value()).strip()
                    if value and value != previous_value and cls.EMAIL_PATTERN.fullmatch(value):
                        return value
                    await asyncio.sleep(0.5)

                raise TikTokAutomationRetryableError(
                    "Tinyhost did not generate a new email before timeout."
                )
            finally:
                await context.close()
                await browser.close()

    @classmethod
    def _extract_code(cls, text: str) -> Optional[str]:
        match = cls.CODE_PATTERN.search(text or "")
        if not match:
            return None
        return match.group(1) or match.group(2)

    @classmethod
    async def fetch_verification_code(
        cls,
        email: str,
        *,
        previous_code: Optional[str] = None,
        timeout_seconds: int = 120,
    ) -> str:
        cls._ensure_provider_available()
        deadline = asyncio.get_running_loop().time() + float(timeout_seconds)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            page = await context.new_page()
            try:
                while asyncio.get_running_loop().time() < deadline:
                    await page.goto(
                        cls.DEFAULT_URL,
                        wait_until="domcontentloaded",
                        timeout=60_000,
                    )
                    await asyncio.sleep(2)

                    email_input = page.locator("#email")
                    await email_input.wait_for(state="visible", timeout=60_000)
                    await email_input.click(timeout=30_000)
                    await email_input.fill(email, timeout=30_000)
                    current_value = (await email_input.input_value()).strip()
                    if current_value != email:
                        await email_input.fill("", timeout=30_000)
                        await email_input.type(email, delay=20, timeout=30_000)

                    await email_input.press("Enter", timeout=30_000)
                    await page.evaluate(
                        """() => {
                            const el = document.querySelector('#email');
                            if (!el) return;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }"""
                    )
                    await asyncio.sleep(5)

                    rows = page.locator("#emailList tr")
                    count = await rows.count()
                    for index in range(count):
                        row = rows.nth(index)
                        row_text = await row.inner_text(timeout=5_000)
                        if "TikTok" not in row_text:
                            continue
                        code = cls._extract_code(row_text)
                        if not code:
                            try:
                                button = row.locator("button.view-btn").first
                                await button.click(timeout=5_000)
                                await asyncio.sleep(1)
                                code = cls._extract_code(
                                    await page.inner_text("body", timeout=5_000)
                                )
                            except Exception:
                                code = None
                        if code and code != previous_code:
                            return code

                    await asyncio.sleep(5)

                raise TikTokAutomationRetryableError(
                    "Tinyhost verification code did not arrive before timeout."
                )
            finally:
                await context.close()
                await browser.close()
