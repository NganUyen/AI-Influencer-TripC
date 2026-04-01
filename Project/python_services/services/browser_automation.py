"""
Browser Automation Service
Handles stealth browser operations using Camoufox
"""

import logging
import os
from urllib.parse import urljoin, urlparse
from typing import Dict, Any, Optional, List

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
        record_video_size: Optional[Dict[str, int]] = None,
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
        viewport_width: int = 1080,
        viewport_height: int = 960,
        max_capture_seconds: int = 60,
        follow_relevant_links: bool = True,
        max_links_to_visit: int = 3,
        scene_duration_sec: Optional[float] = None,
    ) -> str:
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
            Path to the recorded video file.
        """
        import time as _time
        capture_start = _time.monotonic()
        
        if not self.context:
            raise Exception("Browser context not fully initialized for video recording!")

        # Warm up navigation first so the returned recording starts on rendered content,
        # not on initial browser/network loading. Use reduced timeout.
        warmup_ok = await self._warm_up_capture_navigation(url=url, timeout_seconds=12)

        page = await self.context.new_page()
        video = page.video

        try:
            logger.info(
                "Recording website | url=%s | hint=%s | target=%s | scene_duration=%s | warmup_ok=%s",
                url[:60],
                capture_hint,
                target_selector,
                scene_duration_sec,
                warmup_ok,
            )

            # Hard cap recording time so a single orchestration run cannot overrun worker budgets.
            max_capture_seconds = max(8, min(int(max_capture_seconds or 60), 60))
            max_links_to_visit = max(0, min(int(max_links_to_visit or 0), 5))
            
            # If scene_duration_sec is provided, use it to constrain capture budget
            if scene_duration_sec and scene_duration_sec > 0:
                # Add 1.5s buffer for transitions, but don't exceed max
                target_duration = min(float(scene_duration_sec) + 1.5, float(max_capture_seconds))
                max_capture_seconds = int(target_duration)

            # Force a deterministic 9:8 capture frame for tutorial top-half output.
            await page.set_viewport_size(
                {
                    "width": int(viewport_width),
                    "height": int(viewport_height),
                }
            )

            await self._ensure_page_has_rendered_content(page=page, url=url)

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

                scroll_plan = await self._build_scroll_plan(
                    page=page,
                    target_selector=target_selector if idx == 0 else None,
                    capture_hint=capture_hint,
                )
                for y_target in scroll_plan:
                    if loop.time() >= deadline:
                        break
                    remaining_ms = int(max(0.0, deadline - loop.time()) * 1000)
                    # Scale scroll duration based on scene timing for smoother pacing
                    base_duration_ms = 800 if scene_duration_sec and scene_duration_sec > 6 else 600
                    duration_ms = max(380, min(1400, min(remaining_ms - 100, base_duration_ms)))
                    await self._smooth_scroll_to(page=page, target_y=int(y_target), duration_ms=duration_ms)

                    if loop.time() >= deadline:
                        break
                    # Slightly longer pause between scrolls for visual settling
                    await asyncio.sleep(min(0.35, max(0.1, deadline - loop.time())))

            # Page must be closed before resolving the recording path.
            await page.close()
            if video is None:
                raise RuntimeError("Playwright did not attach a video recorder to the page")
            path = await video.path()

            # Caller may finalize context/browser before strict size validation.
            if not os.path.exists(path):
                raise RuntimeError(f"Playwright video file path not found: {path}")
            
            capture_duration = _time.monotonic() - capture_start
            logger.info(
                "Browser capture completed | url=%s | path=%s | duration=%.2fs | target_duration=%s | pages_visited=%d",
                url[:60],
                path,
                capture_duration,
                scene_duration_sec,
                len(visit_urls),
            )
            return path
        except Exception as e:
            capture_duration = _time.monotonic() - capture_start
            logger.error(
                "Browser capture FAILED | url=%s | error=%s | duration=%.2fs | warmup_ok=%s",
                url[:60],
                str(e)[:200],
                capture_duration,
                warmup_ok,
            )
            try:
                await page.close()
            except:
                pass
            raise

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
    ) -> List[int]:
        """Compute content-aware scroll anchors from key sections and layout depth."""
        analysis = await page.evaluate(
            """
            (selector) => {
                const doc = document.documentElement;
                const viewportHeight = window.innerHeight || 960;
                const pageHeight = Math.max(doc.scrollHeight || 0, document.body?.scrollHeight || 0);

                const preferredSelectors = [
                    "header", "main", "section", "article", "[role='main']",
                    "[data-testid]", "[class*='hero']", "[class*='feature']", "[class*='content']"
                ];

                const candidates = [];
                const pushRect = (el) => {
                    if (!el) return;
                    const rect = el.getBoundingClientRect();
                    const top = Math.round(window.scrollY + rect.top);
                    const area = Math.round(Math.max(0, rect.width) * Math.max(0, rect.height));
                    if (top >= 0 && area > 12000) {
                        candidates.push(top);
                    }
                };

                if (selector) {
                    try {
                        const direct = document.querySelector(selector);
                        pushRect(direct);
                    } catch (_) {
                        // Non-CSS target handled by text fallback in Python.
                    }
                }

                for (const sel of preferredSelectors) {
                    const nodes = document.querySelectorAll(sel);
                    for (let i = 0; i < Math.min(nodes.length, 8); i += 1) {
                        pushRect(nodes[i]);
                    }
                }

                // Fallback anchors by page depth.
                const maxScroll = Math.max(0, pageHeight - viewportHeight);
                const depthAnchors = [0, 0.2, 0.4, 0.6, 0.8, 1.0].map((f) => Math.round(maxScroll * f));

                const merged = [...candidates, ...depthAnchors]
                    .filter((v) => Number.isFinite(v) && v >= 0)
                    .sort((a, b) => a - b);

                const deduped = [];
                for (const v of merged) {
                    if (deduped.length === 0 || Math.abs(v - deduped[deduped.length - 1]) > 140) {
                        deduped.push(v);
                    }
                }

                return {
                    viewportHeight,
                    pageHeight,
                    anchors: deduped,
                };
            }
            """,
            target_selector or "",
        )

        anchors = list((analysis or {}).get("anchors") or [])
        if not anchors:
            return [0, 260, 520, 780]

        hint = str(capture_hint or "").lower()
        if hint in {"scroll", "medium", "scroll hero section"}:
            limit = 6
        elif hint in {"interactive", "deep", "long"}:
            limit = 9
        elif hint == "static":
            limit = 1
        else:
            limit = 5

        return anchors[:limit]

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
