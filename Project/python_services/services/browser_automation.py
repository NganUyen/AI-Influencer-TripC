"""
Browser Automation Service
Handles stealth browser operations using Camoufox
"""

import logging
import os
from typing import Dict, Any, Optional

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:  # pragma: no cover - exercised in slim API runtime images
    async_playwright = None
    Browser = BrowserContext = Page = Any

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

    @staticmethod
    def _ensure_playwright_available() -> None:
        if async_playwright is None:
            raise RuntimeError(
                "Browser automation dependencies are not installed in this runtime image."
            )

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
        record_video_dir: Optional[str] = None,
    ):
        """
        Initialize stealth browser with optional proxy

        Args:
            proxy_config: Proxy configuration (server, username, password)
            record_video_dir: Directory to save recorded videos into
        """
        logger.info("Initializing Camoufox browser")
        self._ensure_playwright_available()

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
            
        if record_video_dir:
            import os
            os.makedirs(record_video_dir, exist_ok=True)
            context_options["record_video_dir"] = record_video_dir
            context_options["record_video_size"] = {"width": 1080, "height": 960}
            
        self.context = await self.browser.new_context(
            **context_options
        )

        # Add anti-detection scripts
        await self.context.add_init_script(
            """
            // 1. Hide Webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // 2. Mock Languages
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });

            // 3. Mock Plugins
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

            // 4. Mock WebGL
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel(R) Iris(R) Xe Graphics';
                return getParameter.apply(this, [parameter]);
            };

            // 5. Fix Permissions
            const query = window.navigator.permissions.query;
            if (query) {
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    query(parameters)
                );
            }
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
        self._ensure_playwright_available()

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

    async def record_video_for_tutorial(
        self, 
        url: str, 
        capture_hint: str = "scroll",
        target_selector: Optional[str] = None
    ) -> str:
        """
        Record a video of a website for the top-half of a split-screen video.
        
        Args:
            url: The website URL to record
            capture_hint: How to capture the page ("scroll", "static", "interactive")
            target_selector: Specific CSS selector or section name to record.
        """
        if not self.context:
            raise Exception("Browser context not fully initialized for video recording!")

        page = await self.context.new_page()
        video = page.video

        try:
            logger.info(f"Recording website | url={url} | hint={capture_hint} | target={target_selector}")

            await self._ensure_page_has_rendered_content(page=page, url=url)

            # Wait for page to stabilize
            import asyncio
            await asyncio.sleep(2.0)
            
            # 1. Handle target-specific scrolling if provided
            if target_selector:
                logger.info(f"Targeting specific section: {target_selector}")
                # Try to use as CSS selector first
                try:
                    locator = page.locator(target_selector).first
                    if await locator.count() > 0:
                        await locator.scroll_into_view_if_needed()
                        await asyncio.sleep(1.0)
                    else:
                        # Try searching by text if CSS failed
                        text_locator = page.get_by_text(target_selector).first
                        if await text_locator.count() > 0:
                            await text_locator.scroll_into_view_if_needed()
                            await asyncio.sleep(1.0)
                except Exception as e:
                    logger.warning(f"Could not scroll to target {target_selector}: {e}")

            # 2. Simulate user interaction based on capture_hint
            if capture_hint in ("scroll", "medium", "Scroll hero section"):
                # Smooth scroll through the page
                for _ in range(5):
                    await page.evaluate("window.scrollBy(0, 300)")
                    await asyncio.sleep(0.8)
            elif capture_hint == "static":
                # Just wait to capture static content
                await asyncio.sleep(3.0)
            else:
                # Default: gentle scroll
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 200)")
                    await asyncio.sleep(1.0)

            # Page must be closed before resolving the recording path.
            await page.close()
            if video is None:
                raise RuntimeError("Playwright did not attach a video recorder to the page")
            path = await video.path()

            # Caller may finalize context/browser before strict size validation.
            if not os.path.exists(path):
                raise RuntimeError(f"Playwright video file path not found: {path}")
            
            logger.info(f"Video recorded successfully | path={path}")
            return path
        except Exception as e:
            logger.error(f"Failed to record video from {url}: {e}")
            try:
                await page.close()
            except:
                pass
            raise

    async def _ensure_page_has_rendered_content(self, page: Any, url: str) -> None:
        """Helper to navigate and ensure that we don't just have a blank shell."""
        import asyncio
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        last_metrics: Dict[str, Any] = {}
        for attempt in range(1, 5):
            await asyncio.sleep(1.0)
            metrics = await page.evaluate(
                """
                () => {
                    const body = document.body;
                    const text = body ? (body.innerText || '').trim() : '';
                    const mediaCount = document.querySelectorAll('img, video, canvas, svg').length;
                    const childCount = body ? body.querySelectorAll('*').length : 0;
                    const readyState = document.readyState;
                    const hasMedia = mediaCount > 0;
                    const hasText = text.length > 24;
                    const looksBlank = !hasMedia && !hasText && childCount < 10;
                    return {
                        readyState,
                        hasMedia,
                        hasText,
                        mediaCount,
                        childCount,
                        textLength: text.length,
                        looksBlank,
                    };
                }
                """
            )
            last_metrics = metrics or {}

            logger.info(
                "Render probe attempt %s | url=%s | has_media=%s | ready_state=%s | looks_blank=%s",
                attempt,
                url,
                last_metrics.get("hasMedia"),
                last_metrics.get("readyState"),
                last_metrics.get("looksBlank"),
            )

            if not last_metrics.get("looksBlank"):
                return

            if attempt < 4:
                await page.reload(wait_until="domcontentloaded", timeout=30000)

        raise RuntimeError(
            "Website rendered as blank/empty page before recording "
            f"(metrics={last_metrics})"
        )

    async def get_page_content(self, url: str) -> str:
        """Get text content from a webpage for AI analysis"""
        if not self.context:
            await self.initialize_browser()
        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.evaluate("document.body.innerText")
            return content[:5000]  # Limit to 5k chars for AI processing
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
