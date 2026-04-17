"""
Browser Automation Service
Handles stealth browser operations using Camoufox

Checkpoint Logging (CP-BR*):
- CP-BR1: Browser init complete (proxy, region, viewport)
- CP-BR2: Warm-up navigation started (url, timeout)
- CP-BR3: Warm-up result (success/fail, duration_ms)
- CP-BR4: Main capture started (url, hint, max_seconds)
- CP-BR5: Page rendered (DOM metrics, blank_check)
- CP-BR6: Scroll complete (scroll_steps, pages_visited)
- CP-BR7: Page closed (video_path exists)
- CP-BR8: File validated (size, path)
"""

import logging
import os
import asyncio
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urljoin, urlparse
from typing import Dict, Any, Optional, List

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:  # pragma: no cover - exercised in slim API runtime images
    async_playwright = None
    Browser = BrowserContext = Page = Any

from services.region_service import RegionService

logger = logging.getLogger(__name__)


class CaptureHint(Enum):
    """Capture hint with associated timeout multiplier."""
    STATIC = ("static", 0.5)
    SCROLL = ("scroll", 1.0)
    MEDIUM = ("medium", 1.0)
    INTERACTIVE = ("interactive", 1.2)
    DEEP = ("deep", 1.5)
    LONG = ("long", 1.5)
    ORCHESTRATED = ("orchestrated", 1.5)
    NONE = ("none", 0.5)

    def __init__(self, hint_name: str, timeout_multiplier: float):
        self.hint_name = hint_name
        self.timeout_multiplier = timeout_multiplier

    @classmethod
    def from_string(cls, hint: str) -> "CaptureHint":
        """Convert string hint to CaptureHint enum."""
        hint_lower = (hint or "scroll").lower().strip()
        for member in cls:
            if member.hint_name == hint_lower:
                return member
        return cls.SCROLL  # Default


@dataclass
class CaptureMetrics:
    """Structured metrics from a browser capture operation."""
    capture_duration_ms: int = 0
    warmup_ok: bool = False
    warmup_duration_ms: int = 0
    pages_visited: int = 0
    scroll_steps: int = 0
    file_size_bytes: int = 0
    stabilization_wait_ms: int = 0
    video_path: Optional[str] = None
    failure_reason: Optional[str] = None
    checkpoints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture_duration_ms": self.capture_duration_ms,
            "warmup_ok": self.warmup_ok,
            "warmup_duration_ms": self.warmup_duration_ms,
            "pages_visited": self.pages_visited,
            "scroll_steps": self.scroll_steps,
            "file_size_bytes": self.file_size_bytes,
            "stabilization_wait_ms": self.stabilization_wait_ms,
            "video_path": self.video_path,
            "failure_reason": self.failure_reason,
            "checkpoints": self.checkpoints,
        }


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
        # State tracking for cleanup guards
        self._browser_initialized: bool = False
        self._page_created: bool = False
        self._capture_started: bool = False
        self._current_metrics: Optional[CaptureMetrics] = None

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
            # Base Playwright headless config (new-mode preference is applied
            # at launch time with fallback for compatibility).
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                # Enable GPU for better video encoding
                "--enable-gpu",
                # Use software rendering as fallback in containers
                "--use-gl=swiftshader",
                # Disable shared memory for containers
                "--disable-gpu-sandbox",
            ],
        }

        if proxy_config:
            server = proxy_config.get("server")
            if isinstance(server, str) and server.strip():
                proxy_payload: Dict[str, Any] = {"server": server.strip()}
                username = proxy_config.get("username")
                password = proxy_config.get("password")
                if isinstance(username, str) and username:
                    proxy_payload["username"] = username
                if isinstance(password, str) and password:
                    proxy_payload["password"] = password
                launch_options["proxy"] = proxy_payload

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
        record_video_size: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize stealth browser with optional proxy

        Args:
            proxy_config: Proxy configuration (server, username, password)
            record_video_dir: Directory to save recorded videos into
        """
        init_start = _time.monotonic()
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

        base_launch_options = dict(session_config["launch_options"])
        preferred_launch_options = dict(base_launch_options)
        preferred_args = list(preferred_launch_options.get("args", []))

        # Prefer Chromium's newer headless mode for recording reliability.
        # Some environments may not support it, so we fall back automatically.
        if preferred_launch_options.get("headless", True):
            preferred_launch_options["headless"] = False
            if "--headless=new" not in preferred_args:
                preferred_args.insert(0, "--headless=new")
            preferred_launch_options["args"] = preferred_args

        headless_mode = "default"
        try:
            self.browser = await playwright.chromium.launch(**preferred_launch_options)
            if "--headless=new" in preferred_args:
                headless_mode = "new"
        except Exception as launch_err:
            logger.warning(
                "Chromium launch with headless=new failed; falling back to default headless | err=%s",
                str(launch_err)[:200],
            )
            self.browser = await playwright.chromium.launch(**base_launch_options)
            headless_mode = "default_fallback"

        # Create context with region-aware settings
        context_options = dict(session_config["context_options"])
        if self.storage_state_path and os.path.exists(self.storage_state_path):
            context_options["storage_state"] = self.storage_state_path
            
        if record_video_dir:
            import os
            os.makedirs(record_video_dir, exist_ok=True)
            context_options["record_video_dir"] = record_video_dir
            context_options["record_video_size"] = record_video_size or {"width": 1080, "height": 960}
            
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

        self._browser_initialized = True
        init_duration_ms = int((_time.monotonic() - init_start) * 1000)
        
        # CP-BR1: Browser init complete
        logger.info(
            "CP-BR1: Browser init complete | duration_ms=%d | proxy=%s | region=%s | viewport=%s | record_video=%s | headless_mode=%s",
            init_duration_ms,
            bool(proxy_config),
            (region_info or {}).get("country", "default"),
            record_video_size or {"width": 1080, "height": 960},
            bool(record_video_dir),
            headless_mode,
        )

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
            except Exception:
                logger.exception(
                    "Failed to capture feature section screenshot",
                    extra={"url": url, "output_dir": output_dir},
                )
            
            return screenshots
        finally:
            await page.close()

    async def record_video_for_tutorial(
        self, 
        url: str, 
        capture_hint: str = "scroll",
        target_selector: Optional[str] = None,
        action_text: Optional[str] = None,
        visual_success_criteria: Optional[str] = None,
        viewport_width: int = 1080,
        viewport_height: int = 960,
        max_capture_seconds: int = 60,
        follow_relevant_links: bool = True,
        max_links_to_visit: int = 3,
        scene_duration_sec: Optional[float] = None,
    ) -> tuple[str, CaptureMetrics]:
        """
        Record a video of a website for the top-half of a split-screen video.
        
        Args:
            url: The website URL to record
            capture_hint: How to capture the page ("scroll", "static", "interactive")
            target_selector: Specific CSS selector or section name to record.
            viewport_width: Recording viewport width (default 1080)
            viewport_height: Recording viewport height (default 960)
            max_capture_seconds: Maximum capture duration budget
            follow_relevant_links: Whether to navigate to related pages
            max_links_to_visit: Max number of links to traverse
            scene_duration_sec: Target scene duration to sync capture pacing
            
        Returns:
            Tuple of (path to recorded video file, CaptureMetrics).
        """
        capture_start = _time.monotonic()
        metrics = CaptureMetrics()
        self._current_metrics = metrics
        self._capture_started = True
        page = None
        video = None
        
        if not self.context:
            metrics.failure_reason = "Browser context not initialized"
            raise Exception("Browser context not fully initialized for video recording!")

        # Parse capture hint for timeout multiplier
        hint_enum = CaptureHint.from_string(capture_hint)
        
        # CP-BR2: Warm-up navigation started
        warmup_start = _time.monotonic()
        logger.info(
            "CP-BR2: Warm-up navigation started | url=%s | timeout=12s",
            url[:80],
        )
        
        warmup_ok = await self._warm_up_capture_navigation(url=url, timeout_seconds=12)
        warmup_duration_ms = int((_time.monotonic() - warmup_start) * 1000)
        metrics.warmup_ok = warmup_ok
        metrics.warmup_duration_ms = warmup_duration_ms
        
        # CP-BR3: Warm-up result
        logger.info(
            "CP-BR3: Warm-up result | success=%s | duration_ms=%d | url=%s",
            warmup_ok,
            warmup_duration_ms,
            url[:80],
        )

        try:
            page = await self.context.new_page()
            self._page_created = True
            video = page.video
            
            # CRITICAL FIX: Set a non-white background immediately after page creation.
            # Recording starts when the page is created (showing blank white by default).
            # By setting a colored background, we avoid recording pure white frames.
            # When the actual page loads, it will replace this background.
            await page.evaluate("""
                () => {
                    document.documentElement.style.backgroundColor = '#1a1a2e';
                    document.body.style.backgroundColor = '#1a1a2e';
                }
            """)
            
            # CP-BR4: Main capture started
            logger.info(
                "CP-BR4: Main capture started | url=%s | hint=%s | hint_multiplier=%.1f | target=%s | scene_duration=%s | max_capture_seconds=%s",
                url[:60],
                capture_hint,
                hint_enum.timeout_multiplier,
                target_selector,
                scene_duration_sec,
                max_capture_seconds,
            )

            # Hard cap recording time so a single orchestration run cannot overrun worker budgets.
            max_capture_seconds = max(8, min(int(max_capture_seconds or 60), 60))
            max_links_to_visit = max(0, min(int(max_links_to_visit or 0), 5))
            
            # If scene_duration_sec is provided, use it to constrain capture budget.
            # CRITICAL: Assembly skips the first 8 seconds (TOP_SCENE_SKIP_SECONDS) to
            # exclude blank page loading frames. We must capture enough footage so that
            # scene_duration remains AFTER the 8-second skip.
            # Formula: 8s (skip) + scene_duration + 2s (buffer for transitions)
            ASSEMBLY_SKIP_SECONDS = 8.0
            if scene_duration_sec and scene_duration_sec > 0:
                target_duration = ASSEMBLY_SKIP_SECONDS + float(scene_duration_sec) + 2.0
                # Don't exceed the hard cap
                target_duration = min(target_duration, float(max_capture_seconds))
                max_capture_seconds = int(target_duration)

            # Force a deterministic 9:8 capture frame for tutorial top-half output.
            await page.set_viewport_size(
                {
                    "width": int(viewport_width),
                    "height": int(viewport_height),
                }
            )

            await self._ensure_page_has_rendered_content(page=page, url=url)
            
            # CP-BR5: Page rendered
            dom_metrics = await page.evaluate("""
                () => ({
                    bodyChildCount: document.body ? document.body.childElementCount : 0,
                    documentHeight: document.documentElement.scrollHeight,
                    hasImages: document.images.length,
                    title: document.title || ''
                })
            """)
            logger.info(
                "CP-BR5: Page rendered | url=%s | body_children=%d | doc_height=%d | images=%d | title=%s",
                url[:60],
                dom_metrics.get("bodyChildCount", 0),
                dom_metrics.get("documentHeight", 0),
                dom_metrics.get("hasImages", 0),
                dom_metrics.get("title", "")[:50],
            )
            metrics.checkpoints["CP-BR5"] = dom_metrics

            # Short settle to let CSS/hero transitions finish before motion capture starts.
            import asyncio
            await asyncio.sleep(0.35)

            loop = asyncio.get_running_loop()
            deadline = loop.time() + float(max_capture_seconds)

            capture_mode = str(capture_hint or "").lower()
            traversal_enabled = follow_relevant_links and capture_mode in {
                "scroll",
                "medium",
                "interactive",
                "deep",
                "long",
                "orchestrated",
            }

            visit_urls: List[str] = [url]
            if traversal_enabled and max_links_to_visit > 0:
                discovered_links = await self._discover_relevant_links(
                    page=page,
                    base_url=url,
                    limit=max_links_to_visit,
                )
                visit_urls.extend(discovered_links)

            logger.info(
                "Capture orchestration | mode=%s | max_seconds=%s | links=%s",
                capture_mode,
                max_capture_seconds,
                visit_urls,
            )

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

            if capture_mode == "orchestrated":
                await self._attempt_guided_interaction(
                    page=page,
                    target_selector=target_selector,
                    action_text=action_text,
                    visual_success_criteria=visual_success_criteria,
                )

            # 2. Walk through relevant pages and scroll each one until budget is consumed.
            for idx, visit_url in enumerate(visit_urls):
                if loop.time() >= deadline - 1.0:
                    break

                if idx > 0:
                    try:
                        await self._ensure_page_has_rendered_content(page=page, url=visit_url)
                        await asyncio.sleep(0.8)
                    except Exception as nav_exc:
                        logger.warning("Skipping link due to navigation failure | url=%s | err=%s", visit_url, nav_exc)
                        continue

                remaining = max(0.0, deadline - loop.time())
                logger.info(
                    "Capturing page segment | index=%s/%s | url=%s | remaining=%.2fs",
                    idx + 1,
                    len(visit_urls),
                    visit_url,
                    remaining,
                )

                if capture_mode == "static":
                    await asyncio.sleep(min(2.8, remaining))
                    continue

                # SMART SCROLLING: Get scroll plan with page analysis
                scroll_plan, page_analysis = await self._build_scroll_plan(
                    page=page,
                    target_selector=target_selector if idx == 0 else None,
                    capture_hint=capture_hint,
                    scene_duration_sec=scene_duration_sec,
                )
                
                # Store page analysis in metrics
                if idx == 0:
                    metrics.checkpoints["page_analysis"] = page_analysis
                
                scroll_step_count = 0
                for y_target in scroll_plan:
                    if loop.time() >= deadline:
                        break
                    remaining_ms = int(max(0.0, deadline - loop.time()) * 1000)
                    # Scale scroll duration based on scene timing for smoother pacing
                    base_duration_ms = 800 if scene_duration_sec and scene_duration_sec > 6 else 600
                    duration_ms = max(380, min(1400, min(remaining_ms - 100, base_duration_ms)))
                    await self._smooth_scroll_to(page=page, target_y=int(y_target), duration_ms=duration_ms)
                    scroll_step_count += 1

                    if loop.time() >= deadline:
                        break
                    # Slightly longer pause between scrolls for visual settling
                    await asyncio.sleep(min(0.35, max(0.1, deadline - loop.time())))
                
                metrics.scroll_steps += scroll_step_count
            
            metrics.pages_visited = len(visit_urls)
            
            # CP-BR6: Scroll complete
            logger.info(
                "CP-BR6: Scroll complete | pages_visited=%d | total_scroll_steps=%d | remaining_budget=%.2fs",
                metrics.pages_visited,
                metrics.scroll_steps,
                max(0.0, deadline - loop.time()),
            )

            # Page must be closed before resolving the recording path.
            await page.close()
            self._page_created = False
            
            if video is None:
                metrics.failure_reason = "Playwright did not attach a video recorder"
                raise RuntimeError("Playwright did not attach a video recorder to the page")
            
            path = await video.path()
            
            # CP-BR7: Page closed
            path_exists = os.path.exists(path)
            logger.info(
                "CP-BR7: Page closed | video_path=%s | path_exists=%s",
                path,
                path_exists,
            )

            if not path_exists:
                metrics.failure_reason = f"Video file not found: {path}"
                raise RuntimeError(f"Playwright video file path not found: {path}")
            
            # ═══════════════════════════════════════════════════════════════════════════
            # CRITICAL: Wait for video file to be finalized by ffmpeg
            # ═══════════════════════════════════════════════════════════════════════════
            # Playwright/ffmpeg may still be encoding the video after page.close().
            # We need to wait for the file to have actual content and stabilize.
            MIN_VALID_SIZE = 2000  # Minimum valid video size in bytes
            MAX_FINALIZE_WAIT = 30.0  # Maximum wait for video finalization
            finalize_start = _time.monotonic()
            finalize_iterations = 0
            last_size = 0
            stable_count = 0
            
            while (_time.monotonic() - finalize_start) < MAX_FINALIZE_WAIT:
                finalize_iterations += 1
                
                if not os.path.exists(path):
                    await asyncio.sleep(0.3)
                    continue
                
                current_size = os.path.getsize(path)
                
                # Check if file has grown to valid size
                if current_size >= MIN_VALID_SIZE:
                    # Wait for size to stabilize (same size 2 times in a row)
                    if current_size == last_size:
                        stable_count += 1
                        if stable_count >= 2:
                            logger.info(
                                "Video file finalized | path=%s | size=%d | iterations=%d | wait_ms=%d",
                                path,
                                current_size,
                                finalize_iterations,
                                int((_time.monotonic() - finalize_start) * 1000),
                            )
                            break
                    else:
                        stable_count = 0
                
                last_size = current_size
                await asyncio.sleep(0.5)
            else:
                # Timeout reached
                final_size = os.path.getsize(path) if os.path.exists(path) else 0
                logger.warning(
                    "Video finalization timeout | path=%s | final_size=%d | wait_sec=%.1f",
                    path,
                    final_size,
                    MAX_FINALIZE_WAIT,
                )
            
            # Get final file size after stabilization
            initial_size = os.path.getsize(path) if os.path.exists(path) else 0
            metrics.video_path = path
            metrics.file_size_bytes = initial_size
            
            capture_duration = _time.monotonic() - capture_start
            metrics.capture_duration_ms = int(capture_duration * 1000)
            
            # CP-BR8: File validated
            logger.info(
                "CP-BR8: File validated | path=%s | size_bytes=%d | capture_duration_ms=%d | pages_visited=%d | scroll_steps=%d",
                path,
                initial_size,
                metrics.capture_duration_ms,
                metrics.pages_visited,
                metrics.scroll_steps,
            )
            
            logger.info(
                "Browser capture completed | url=%s | path=%s | duration=%.2fs | target_duration=%s | pages_visited=%d | metrics=%s",
                url[:60],
                path,
                capture_duration,
                scene_duration_sec,
                len(visit_urls),
                metrics.to_dict(),
            )
            return path, metrics
        except Exception as e:
            capture_duration = _time.monotonic() - capture_start
            metrics.capture_duration_ms = int(capture_duration * 1000)
            metrics.failure_reason = str(e)[:300]
            
            logger.error(
                "Browser capture FAILED | url=%s | error=%s | duration=%.2fs | warmup_ok=%s | metrics=%s",
                url[:60],
                str(e)[:200],
                capture_duration,
                metrics.warmup_ok,
                metrics.to_dict(),
            )
            
            # Cleanup: try to close page with timeout guard
            if page is not None and self._page_created:
                try:
                    import asyncio
                    await asyncio.wait_for(page.close(), timeout=10.0)
                except Exception as close_err:
                    logger.warning("Failed to close page after error: %s", close_err)
                finally:
                    self._page_created = False
            
            raise

    async def _attempt_guided_interaction(
        self,
        *,
        page: Any,
        target_selector: Optional[str],
        action_text: Optional[str],
        visual_success_criteria: Optional[str],
    ) -> None:
        action_lower = str(action_text or "").lower()
        if not any(token in action_lower for token in ["click", "open", "select", "tap", "press"]):
            return

        candidate_texts: List[str] = []
        for raw in [target_selector, visual_success_criteria, action_text]:
            text = str(raw or "").strip()
            if not text:
                continue
            cleaned = text.replace("'", " ").replace('"', " ").strip()
            if cleaned and cleaned not in candidate_texts:
                candidate_texts.append(cleaned)

        for candidate in candidate_texts[:3]:
            try:
                locator = page.get_by_text(candidate, exact=False).first
                if await locator.count() > 0:
                    await locator.click(timeout=1500)
                    await page.wait_for_load_state("networkidle", timeout=2500)
                    await asyncio.sleep(0.6)
                    logger.info(
                        "Guided interaction succeeded | target=%s | action=%s",
                        candidate[:80],
                        str(action_text or "")[:120],
                    )
                    return
            except Exception:
                continue

        logger.info(
            "Guided interaction skipped | target=%s | action=%s",
            str(target_selector or "")[:80],
            str(action_text or "")[:120],
        )

    async def _warm_up_capture_navigation(self, url: str, timeout_seconds: int = 15) -> bool:
        """
        Prime the browser cache/session so the returned video avoids initial loading screens.
        
        Returns:
            True if warm-up succeeded, False if it failed (capture can still proceed).
        """
        import asyncio
        warmup_page = await self.context.new_page()
        success = False
        try:
            # Use a shorter timeout for warm-up to avoid blocking capture
            await asyncio.wait_for(
                self._ensure_page_has_rendered_content(page=warmup_page, url=url),
                timeout=float(timeout_seconds),
            )
            # Tiny delay to allow pending image decode/font settle in warm cache.
            await asyncio.sleep(0.2)
            success = True
        except asyncio.TimeoutError:
            logger.warning(
                "Warm-up navigation timed out after %ss; proceeding with direct capture | url=%s",
                timeout_seconds,
                url[:80],
            )
        except Exception as exc:
            # Best-effort only: do not fail capture if warm-up cannot complete.
            logger.warning(
                "Warm-up navigation failed; proceeding with direct capture | url=%s | err=%s",
                url[:80],
                str(exc)[:100],
            )
        finally:
            try:
                await warmup_page.close()
            except Exception:
                pass
        return success

    async def _smooth_scroll_to(self, page: Any, target_y: int, duration_ms: int = 900) -> None:
        """
        Frame-synced scroll animation using requestAnimationFrame (~60fps).
        
        Uses an improved easing function for smoother, more cinematic scrolling
        that feels natural in video recordings.
        """
        await page.evaluate(
            """
            async ({ targetY, durationMs }) => {
                const startY = window.scrollY || window.pageYOffset || 0;
                const maxY = Math.max(
                    0,
                    (document.documentElement.scrollHeight || 0) - (window.innerHeight || 0)
                );
                const endY = Math.max(0, Math.min(Number(targetY) || 0, maxY));
                const delta = endY - startY;
                const duration = Math.max(300, Math.min(Number(durationMs) || 900, 2500));

                // Improved easing: ease-out-quint for smoother deceleration
                // More natural feel when reaching scroll destinations
                const easeOutQuint = (t) => 1 - Math.pow(1 - t, 5);
                
                // For short scrolls use ease-in-out, for long scrolls use ease-out
                const scrollDistance = Math.abs(delta);
                const useEaseOut = scrollDistance > 400;
                
                const easeInOutCubic = (t) => (
                    t < 0.5
                        ? 4 * t * t * t
                        : 1 - Math.pow(-2 * t + 2, 3) / 2
                );
                
                const easingFn = useEaseOut ? easeOutQuint : easeInOutCubic;

                await new Promise((resolve) => {
                    if (Math.abs(delta) < 5) {
                        resolve();
                        return;
                    }
                    
                    const startedAt = performance.now();
                    const step = (now) => {
                        const elapsed = now - startedAt;
                        const progress = Math.min(1, elapsed / duration);
                        const eased = easingFn(progress);
                        window.scrollTo({ top: Math.round(startY + delta * eased), behavior: 'instant' });
                        
                        if (progress < 1) {
                            requestAnimationFrame(step);
                            return;
                        }
                        // Ensure we land exactly on target
                        window.scrollTo({ top: endY, behavior: 'instant' });
                        resolve();
                    };
                    requestAnimationFrame(step);
                });
            }
            """,
            {"targetY": int(target_y), "durationMs": int(duration_ms)},
        )

    async def _build_scroll_plan(
        self,
        page: Any,
        target_selector: Optional[str],
        capture_hint: str,
        scene_duration_sec: Optional[float] = None,
    ) -> tuple[List[int], Dict[str, Any]]:
        """
        Compute content-aware scroll anchors from key sections and layout depth.
        
        SMART SCROLLING FEATURES:
        - Detects if page fits in viewport (skip scrolling)
        - Calculates scroll speed based on page height and capture duration
        - Uses content-aware anchors (sections, features, etc.)
        - Returns scroll plan and page analysis metadata
        
        Returns:
            Tuple of (scroll_anchors: List[int], page_analysis: Dict)
        """
        analysis = await page.evaluate(
            """
            (selector) => {
                const doc = document.documentElement;
                const viewportHeight = window.innerHeight || 960;
                const viewportWidth = window.innerWidth || 1080;
                const pageHeight = Math.max(doc.scrollHeight || 0, document.body?.scrollHeight || 0);
                const pageWidth = Math.max(doc.scrollWidth || 0, document.body?.scrollWidth || 0);
                
                // Check if page fits in viewport (no scroll needed)
                const fitsInViewport = pageHeight <= viewportHeight + 50;
                const maxScroll = Math.max(0, pageHeight - viewportHeight);

                const preferredSelectors = [
                    "header", "main", "section", "article", "[role='main']",
                    "[data-testid]", "[class*='hero']", "[class*='feature']", 
                    "[class*='content']", "[class*='benefits']", "[class*='pricing']",
                    "[class*='testimonial']", "[class*='cta']", "footer"
                ];

                const candidates = [];
                const sectionInfo = [];
                
                const pushRect = (el, sectionType) => {
                    if (!el) return;
                    const rect = el.getBoundingClientRect();
                    const top = Math.round(window.scrollY + rect.top);
                    const height = Math.round(Math.max(0, rect.height));
                    const area = Math.round(Math.max(0, rect.width) * height);
                    if (top >= 0 && area > 12000) {
                        candidates.push(top);
                        sectionInfo.push({ type: sectionType, top, height });
                    }
                };

                if (selector) {
                    try {
                        const direct = document.querySelector(selector);
                        pushRect(direct, 'target');
                    } catch (_) {
                        // Non-CSS target handled by text fallback in Python.
                    }
                }

                for (const sel of preferredSelectors) {
                    const nodes = document.querySelectorAll(sel);
                    for (let i = 0; i < Math.min(nodes.length, 8); i += 1) {
                        pushRect(nodes[i], sel);
                    }
                }

                // Fallback anchors by page depth (more granular for long pages)
                const numDepthAnchors = Math.min(10, Math.max(3, Math.ceil(pageHeight / viewportHeight)));
                const depthAnchors = [];
                for (let i = 0; i <= numDepthAnchors; i++) {
                    depthAnchors.push(Math.round(maxScroll * (i / numDepthAnchors)));
                }

                const merged = [...candidates, ...depthAnchors]
                    .filter((v) => Number.isFinite(v) && v >= 0)
                    .sort((a, b) => a - b);

                // Dedupe with larger gap for smooth scrolling
                const deduped = [];
                for (const v of merged) {
                    if (deduped.length === 0 || Math.abs(v - deduped[deduped.length - 1]) > 180) {
                        deduped.push(v);
                    }
                }

                return {
                    viewportHeight,
                    viewportWidth,
                    pageHeight,
                    pageWidth,
                    maxScroll,
                    fitsInViewport,
                    sectionsFound: sectionInfo.length,
                    anchors: deduped,
                };
            }
            """,
            target_selector or "",
        )
        
        page_analysis = analysis or {}
        viewport_height = page_analysis.get("viewportHeight", 960)
        page_height = page_analysis.get("pageHeight", 960)
        fits_in_viewport = page_analysis.get("fitsInViewport", False)
        anchors = list(page_analysis.get("anchors") or [])
        
        # SMART SCROLLING: Skip if page fits in viewport
        if fits_in_viewport:
            logger.info(
                "Page fits in viewport, skipping scroll | page_height=%d | viewport=%d",
                page_height,
                viewport_height,
            )
            return [0], page_analysis  # Single anchor at top, no scroll needed
        
        if not anchors:
            anchors = [0, 260, 520, 780]

        hint = str(capture_hint or "").lower()
        hint_enum = CaptureHint.from_string(hint)
        
        # Determine anchor limit based on hint
        if hint in {"static", "none"}:
            limit = 1
        elif hint in {"scroll", "medium", "scroll hero section"}:
            limit = 6
        elif hint in {"interactive", "deep", "long"}:
            limit = 9
        else:
            limit = 5
        
        # SMART SCROLLING: Adjust anchor count based on scene duration
        if scene_duration_sec and scene_duration_sec > 0:
            # Calculate how many scroll steps fit in the duration
            # Assume ~1.5s per scroll step (scroll + pause)
            max_steps_for_duration = max(1, int(scene_duration_sec / 1.5))
            limit = min(limit, max_steps_for_duration)
            logger.info(
                "Adjusted scroll anchors for scene duration | duration=%.1f | max_steps=%d | limit=%d",
                scene_duration_sec,
                max_steps_for_duration,
                limit,
            )
        
        selected_anchors = anchors[:limit]
        
        logger.info(
            "Scroll plan built | hint=%s | page_height=%d | fits_viewport=%s | sections=%d | anchors=%d/%d",
            hint,
            page_height,
            fits_in_viewport,
            page_analysis.get("sectionsFound", 0),
            len(selected_anchors),
            len(anchors),
        )
        
        return selected_anchors, page_analysis

    async def _discover_relevant_links(
        self,
        page: Any,
        base_url: str,
        limit: int = 3,
    ) -> List[str]:
        """Discover meaningful same-site links to capture a guided walkthrough."""
        raw_links = await page.evaluate(
            """
            () => {
                const selectors = ["main a[href]", "nav a[href]", "section a[href]", "article a[href]"];
                const nodes = [];
                for (const sel of selectors) {
                    const found = document.querySelectorAll(sel);
                    for (const node of found) {
                        nodes.push(node);
                    }
                }

                const scored = [];
                for (const anchor of nodes) {
                    const href = (anchor.getAttribute("href") || "").trim();
                    if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) {
                        continue;
                    }

                    const text = (anchor.textContent || "").trim().toLowerCase();
                    const parentText = (anchor.closest("section,article,main,nav")?.textContent || "").toLowerCase();

                    let score = 0;
                    const importantTokens = [
                        "feature", "pricing", "product", "demo", "about", "how", "workflow", "solution", "case", "story", "benefit"
                    ];
                    for (const token of importantTokens) {
                        if (text.includes(token) || parentText.includes(token)) {
                            score += 2;
                        }
                    }
                    score += Math.min(2, Math.floor((text.length || 0) / 14));

                    scored.push({ href, score });
                }

                scored.sort((a, b) => b.score - a.score);
                return scored.map((entry) => entry.href);
            }
            """
        )

        if not isinstance(raw_links, list):
            return []

        base = urlparse(base_url)
        selected: List[str] = []
        for href in raw_links:
            if len(selected) >= limit:
                break
            if not isinstance(href, str):
                continue

            resolved = urljoin(base_url, href.strip())
            parsed = urlparse(resolved)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc and parsed.netloc != base.netloc:
                continue
            normalized = resolved.split("#", 1)[0]
            if normalized == base_url or normalized in selected:
                continue
            selected.append(normalized)

        return selected

    async def _ensure_page_has_rendered_content(self, page: Any, url: str) -> None:
        """Helper to navigate and ensure that we don't just have a blank shell."""
        import asyncio
        
        # First, navigate with networkidle to wait for most resources
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as nav_err:
            logger.warning(
                "Navigation with networkidle failed, falling back to domcontentloaded | url=%s | error=%s",
                url[:60],
                str(nav_err)[:100],
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait additional time for lazy-loaded content and CSS transitions
        await asyncio.sleep(2.0)

        last_metrics: Dict[str, Any] = {}
        max_attempts = 6  # Increased from 4 to 6
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(1.5)  # Increased from 1.0 to 1.5
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
                    
                    // Check if page has a white/blank background
                    const bgColor = window.getComputedStyle(document.body).backgroundColor;
                    const isWhiteBg = bgColor === 'rgb(255, 255, 255)' || bgColor === 'rgba(0, 0, 0, 0)';
                    
                    return {
                        readyState,
                        hasMedia,
                        hasText,
                        mediaCount,
                        childCount,
                        textLength: text.length,
                        looksBlank,
                        bgColor,
                        isWhiteBg,
                    };
                }
                """
            )
            last_metrics = metrics or {}

            logger.info(
                "Render probe attempt %s/%s | url=%s | has_media=%s | child_count=%s | ready_state=%s | looks_blank=%s | bg=%s",
                attempt,
                max_attempts,
                url[:60],
                last_metrics.get("hasMedia"),
                last_metrics.get("childCount"),
                last_metrics.get("readyState"),
                last_metrics.get("looksBlank"),
                last_metrics.get("bgColor", "unknown")[:30],
            )

            if not last_metrics.get("looksBlank"):
                # Page has content - wait a bit more for visual stability
                await asyncio.sleep(1.0)
                return

            if attempt < max_attempts:
                # Try reloading if page looks blank
                try:
                    await page.reload(wait_until="networkidle", timeout=20000)
                except Exception:
                    await page.reload(wait_until="domcontentloaded", timeout=20000)

        # Don't raise error - let the capture proceed and we'll see what happens
        # Some pages may appear "blank" to our detection but still have visual content
        logger.warning(
            "Page may be blank after %s attempts | url=%s | metrics=%s | proceeding anyway",
            max_attempts,
            url[:60],
            last_metrics,
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
        """Close browser and context with timeout guards."""
        import asyncio
        close_start = _time.monotonic()
        
        try:
            if self.context:
                if self.storage_state_path:
                    os.makedirs(os.path.dirname(self.storage_state_path), exist_ok=True)
                    try:
                        await asyncio.wait_for(
                            self.context.storage_state(path=self.storage_state_path),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Timeout saving storage state, continuing with close")
                
                try:
                    await asyncio.wait_for(self.context.close(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout closing browser context")
                finally:
                    self.context = None
            
            if self.browser:
                try:
                    await asyncio.wait_for(self.browser.close(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning("Timeout closing browser")
                finally:
                    self.browser = None
            
            close_duration_ms = int((_time.monotonic() - close_start) * 1000)
            self._browser_initialized = False
            self._page_created = False
            self._capture_started = False
            
            logger.info("Browser closed | duration_ms=%d", close_duration_ms)
        except Exception as e:
            logger.error("Error during browser close: %s", e)
            # Reset state even on error
            self.context = None
            self.browser = None
            self._browser_initialized = False
            self._page_created = False
            self._capture_started = False
            raise
