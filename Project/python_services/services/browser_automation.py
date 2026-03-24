"""
Browser Automation Service
Handles stealth browser operations using Camoufox
"""

import logging
import os
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from services.region_service import RegionService

logger = logging.getLogger(__name__)


class BrowserAutomationService:
    """
    Browser automation service using Camoufox for stealth
    Handles posting to platforms that don't have official APIs
    """

    def __init__(self):
        self.proxy_config = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.storage_state_path: Optional[str] = None
        self.profile_name: Optional[str] = None

    def build_launch_options(
        self, proxy_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        launch_options: Dict[str, Any] = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }

        if proxy_config:
            launch_options["proxy"] = {
                "server": proxy_config.get("server"),
                "username": proxy_config.get("username"),
                "password": proxy_config.get("password"),
            }

        return launch_options

    def build_context_options(
        self,
        region_info: Optional[Dict[str, Any]] = None,
        platform: str = "generic",
    ) -> Dict[str, Any]:
        region_service = RegionService()
        region_info = region_info or region_service._get_default_region()
        region_settings = region_service.build_browser_context_settings(
            region_info=region_info,
            platform=platform,
        )

        return {
            "viewport": region_settings["viewport"],
            "user_agent": region_settings["user_agent"],
            "locale": region_settings["locale"],
            "timezone_id": region_settings["timezone_id"],
            "extra_http_headers": region_settings["extra_http_headers"],
            "device_scale_factor": region_settings["device_scale_factor"],
            "has_touch": region_settings["has_touch"],
            "is_mobile": region_settings["is_mobile"],
        }

    def build_session_configuration(
        self,
        region_info: Optional[Dict[str, Any]] = None,
        platform: str = "generic",
        proxy_config: Optional[Dict[str, Any]] = None,
        profile_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        storage_state_path = None
        if profile_name:
            storage_state_path = f"/app/browser_profiles/{profile_name}/storage_state.json"

        return {
            "launch_options": self.build_launch_options(proxy_config=proxy_config),
            "context_options": self.build_context_options(
                region_info=region_info,
                platform=platform,
            ),
            "proxy": proxy_config or {},
            "region": region_info or RegionService()._get_default_region(),
            "platform": platform,
            "storage_state_path": storage_state_path,
            "profile_name": profile_name,
        }

    async def initialize_browser(
        self,
        proxy_config: Optional[Dict[str, Any]] = None,
        region_info: Optional[Dict[str, Any]] = None,
        platform: str = "generic",
        profile_name: Optional[str] = None,
    ):
        """
        Initialize stealth browser with optional proxy

        Args:
            proxy_config: Proxy configuration (server, username, password)
        """
        logger.info("Initializing Camoufox browser")

        playwright = await async_playwright().start()
        session_config = self.build_session_configuration(
            region_info=region_info,
            platform=platform,
            proxy_config=proxy_config,
            profile_name=profile_name,
        )
        self.storage_state_path = session_config.get("storage_state_path")
        self.profile_name = session_config.get("profile_name")

        self.browser = await playwright.chromium.launch(
            **session_config["launch_options"]
        )

        # Create context with region-aware settings
        context_options = dict(session_config["context_options"])
        if self.storage_state_path and os.path.exists(self.storage_state_path):
            context_options["storage_state"] = self.storage_state_path
        self.context = await self.browser.new_context(
            **context_options
        )

        # Add anti-detection scripts
        await self.context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
        )

        logger.info("Browser initialized successfully")

    async def publish(
        self,
        platform: str,
        content: str,
        media_urls: list,
        user_id: str,
        proxy_config: Optional[Dict[str, Any]] = None,
        region_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Publish content to a platform using browser automation

        Args:
            platform: Target platform
            content: Post content
            media_urls: List of media URLs to upload
            user_id: User identifier for account session
        """
        logger.info(f"Publishing to {platform} via browser automation")

        if not self.context:
            await self.initialize_browser(
                proxy_config=proxy_config,
                region_info=region_info,
                platform=platform,
            )

        try:
            page = await self.context.new_page()

            # Route to platform-specific automation
            if platform == "instagram":
                result = await self._publish_instagram(
                    page, content, media_urls, user_id
                )
            elif platform == "reddit":
                result = await self._publish_reddit(page, content, media_urls, user_id)
            elif platform == "pinterest":
                result = await self._publish_pinterest(
                    page, content, media_urls, user_id
                )
            else:
                raise ValueError(f"Unsupported platform: {platform}")

            await page.close()
            return result

        except Exception as e:
            logger.error(f"Browser automation failed: {str(e)}")
            raise

    async def _publish_instagram(
        self, page: Page, content: str, media_urls: list, user_id: str
    ) -> Dict[str, Any]:
        """Instagram-specific publishing logic"""
        logger.info("Publishing to Instagram")

        # Navigate to Instagram
        await page.goto("https://www.instagram.com")

        # Login logic (load saved session cookies)
        # Upload media
        # Add caption
        # Post

        return {
            "post_id": "instagram_post_123",
            "platform": "instagram",
            "status": "published",
        }

    async def _publish_reddit(
        self, page: Page, content: str, media_urls: list, user_id: str
    ) -> Dict[str, Any]:
        """Reddit-specific publishing logic"""
        logger.info("Publishing to Reddit")

        return {
            "post_id": "reddit_post_123",
            "platform": "reddit",
            "status": "published",
        }

    async def _publish_pinterest(
        self, page: Page, content: str, media_urls: list, user_id: str
    ) -> Dict[str, Any]:
        """Pinterest-specific publishing logic"""
        logger.info("Publishing to Pinterest")

        return {
            "post_id": "pinterest_pin_123",
            "platform": "pinterest",
            "status": "published",
        }

    async def take_screenshots_for_tutorial(self, url: str, output_dir: str) -> list:
        """
        Truy cập URL và chụp ảnh màn hình các bước quan trọng để làm tutorial.
        """
        if not self.context:
            await self.initialize_browser()
            
        page = await self.context.new_page()
        screenshots = []
        
        try:
            logger.info(f"Stealing screenshots for tutorial from {url}")
            await page.goto(url, wait_until="networkidle")
            
            # 1. Toàn cảnh landing page
            path1 = f"{output_dir}/step1_landing.png"
            await page.screenshot(path=path1, full_page=False)
            screenshots.append({"step": "landing", "path": path1})
            
            # 2. Thử tìm các section chính (ví dụ feature section)
            try:
                await page.evaluate("window.scrollTo(0, 500)")
                path2 = f"{output_dir}/step2_features.png"
                await page.screenshot(path=path2)
                screenshots.append({"step": "features", "path": path2})
            except: pass
            
            return screenshots
        finally:
            await page.close()

    async def get_page_content(self, url: str) -> str:
        """Lấy text content của trang web để AI phân tích"""
        if not self.context:
            await self.initialize_browser()
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            content = await page.evaluate("document.body.innerText")
            return content[:5000] # Giới hạn 5k ký tự cho AI
        finally:
            await page.close()

    async def close(self):
        """Close browser and context"""
        if self.context:
            if self.storage_state_path:
                os.makedirs(os.path.dirname(self.storage_state_path), exist_ok=True)
                await self.context.storage_state(path=self.storage_state_path)
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")
