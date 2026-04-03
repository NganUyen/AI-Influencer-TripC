"""
Browser Capture Metrics & Domain Intelligence

Provides:
1. Prometheus-style metrics collection (counters, histograms)
2. Domain success rate tracking in Redis (24h TTL)
3. Debug mode with HTML snapshots & timeline reports
4. Health check functionality

Usage:
    from services.browser_capture_metrics import capture_metrics, domain_tracker

    # Record a capture attempt
    capture_metrics.record_capture(
        success=True,
        domain="example.com",
        duration_sec=5.2,
        file_size_bytes=3_500_000,
        fallback_used=False,
    )

    # Check if domain should use AI fallback
    should_fallback = await domain_tracker.should_use_fallback("problematic-site.com")

    # Get Prometheus-format metrics
    metrics_text = capture_metrics.prometheus_format()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:
    Redis = None

from config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOMAIN_TTL_SECONDS = 86400  # 24 hours
DOMAIN_FAILURE_THRESHOLD = 0.5  # 50% failure rate triggers fallback suggestion
MIN_SAMPLES_FOR_FALLBACK = 3  # Need at least 3 attempts before suggesting fallback
DEBUG_SNAPSHOT_DIR = Path("/tmp/browser_capture_debug")
HEALTH_CHECK_URL = "https://playwright.dev"
HEALTH_CHECK_TIMEOUT_SEC = 30


# ---------------------------------------------------------------------------
# Prometheus-Style Metrics Collector
# ---------------------------------------------------------------------------

@dataclass
class MetricsBucket:
    """Histogram bucket for latency/size distribution."""
    le: float  # Less than or equal
    count: int = 0


@dataclass
class CaptureMetricsCollector:
    """
    Collects browser capture metrics in Prometheus-style format.

    Metrics tracked:
    - browser_capture_total: Counter of total capture attempts
    - browser_capture_success_total: Counter of successful captures
    - browser_capture_fallback_total: Counter of fallback usage
    - browser_capture_duration_seconds: Histogram of capture durations
    - browser_capture_file_size_bytes: Histogram of file sizes
    - browser_capture_errors_total: Counter by error type
    """

    # Counters
    total_captures: int = 0
    successful_captures: int = 0
    failed_captures: int = 0
    fallback_used: int = 0

    # Error breakdown
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Domain breakdown
    captures_by_domain: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"success": 0, "failure": 0})
    )

    # Duration histogram buckets (seconds)
    duration_buckets: List[MetricsBucket] = field(default_factory=lambda: [
        MetricsBucket(le=1.0),
        MetricsBucket(le=2.0),
        MetricsBucket(le=5.0),
        MetricsBucket(le=10.0),
        MetricsBucket(le=20.0),
        MetricsBucket(le=30.0),
        MetricsBucket(le=60.0),
        MetricsBucket(le=float("inf")),
    ])
    duration_sum: float = 0.0
    duration_count: int = 0

    # File size histogram buckets (bytes)
    size_buckets: List[MetricsBucket] = field(default_factory=lambda: [
        MetricsBucket(le=10_000),       # 10KB (likely failed)
        MetricsBucket(le=100_000),      # 100KB
        MetricsBucket(le=500_000),      # 500KB
        MetricsBucket(le=1_000_000),    # 1MB
        MetricsBucket(le=3_000_000),    # 3MB
        MetricsBucket(le=5_000_000),    # 5MB
        MetricsBucket(le=10_000_000),   # 10MB
        MetricsBucket(le=float("inf")),
    ])
    size_sum: float = 0.0
    size_count: int = 0

    # Timestamps
    _start_time: float = field(default_factory=time.time)
    _last_success_time: Optional[float] = None
    _last_failure_time: Optional[float] = None

    def record_capture(
        self,
        success: bool,
        domain: str,
        duration_sec: float,
        file_size_bytes: int = 0,
        fallback_used: bool = False,
        error_type: Optional[str] = None,
    ) -> None:
        """Record a capture attempt with all metrics."""
        self.total_captures += 1

        if success:
            self.successful_captures += 1
            self._last_success_time = time.time()
            self.captures_by_domain[domain]["success"] += 1
        else:
            self.failed_captures += 1
            self._last_failure_time = time.time()
            self.captures_by_domain[domain]["failure"] += 1
            if error_type:
                self.errors_by_type[error_type] += 1

        if fallback_used:
            self.fallback_used += 1

        # Update duration histogram
        self.duration_sum += duration_sec
        self.duration_count += 1
        for bucket in self.duration_buckets:
            if duration_sec <= bucket.le:
                bucket.count += 1

        # Update size histogram
        if file_size_bytes > 0:
            self.size_sum += file_size_bytes
            self.size_count += 1
            for bucket in self.size_buckets:
                if file_size_bytes <= bucket.le:
                    bucket.count += 1

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate (0.0 - 1.0)."""
        if self.total_captures == 0:
            return 1.0
        return self.successful_captures / self.total_captures

    @property
    def fallback_rate(self) -> float:
        """Calculate fallback usage rate (0.0 - 1.0)."""
        if self.total_captures == 0:
            return 0.0
        return self.fallback_used / self.total_captures

    @property
    def average_duration_sec(self) -> float:
        """Calculate average capture duration."""
        if self.duration_count == 0:
            return 0.0
        return self.duration_sum / self.duration_count

    @property
    def average_file_size_bytes(self) -> float:
        """Calculate average file size."""
        if self.size_count == 0:
            return 0.0
        return self.size_sum / self.size_count

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary as dictionary."""
        return {
            "total_captures": self.total_captures,
            "successful_captures": self.successful_captures,
            "failed_captures": self.failed_captures,
            "success_rate": round(self.success_rate * 100, 2),
            "fallback_used": self.fallback_used,
            "fallback_rate": round(self.fallback_rate * 100, 2),
            "average_duration_sec": round(self.average_duration_sec, 2),
            "average_file_size_mb": round(self.average_file_size_bytes / 1_000_000, 2),
            "uptime_seconds": round(time.time() - self._start_time, 0),
            "last_success_ago_sec": (
                round(time.time() - self._last_success_time, 0)
                if self._last_success_time
                else None
            ),
            "last_failure_ago_sec": (
                round(time.time() - self._last_failure_time, 0)
                if self._last_failure_time
                else None
            ),
            "top_error_types": dict(
                sorted(self.errors_by_type.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
        }

    def prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = [
            "# HELP browser_capture_total Total number of browser capture attempts",
            "# TYPE browser_capture_total counter",
            f"browser_capture_total {self.total_captures}",
            "",
            "# HELP browser_capture_success_total Successful browser captures",
            "# TYPE browser_capture_success_total counter",
            f"browser_capture_success_total {self.successful_captures}",
            "",
            "# HELP browser_capture_fallback_total Captures that used AI fallback",
            "# TYPE browser_capture_fallback_total counter",
            f"browser_capture_fallback_total {self.fallback_used}",
            "",
            "# HELP browser_capture_duration_seconds Capture duration histogram",
            "# TYPE browser_capture_duration_seconds histogram",
        ]

        for bucket in self.duration_buckets:
            le_str = "+Inf" if bucket.le == float("inf") else str(bucket.le)
            lines.append(f'browser_capture_duration_seconds_bucket{{le="{le_str}"}} {bucket.count}')
        lines.append(f"browser_capture_duration_seconds_sum {self.duration_sum:.3f}")
        lines.append(f"browser_capture_duration_seconds_count {self.duration_count}")

        lines.extend([
            "",
            "# HELP browser_capture_file_size_bytes Capture file size histogram",
            "# TYPE browser_capture_file_size_bytes histogram",
        ])

        for bucket in self.size_buckets:
            le_str = "+Inf" if bucket.le == float("inf") else str(int(bucket.le))
            lines.append(f'browser_capture_file_size_bytes_bucket{{le="{le_str}"}} {bucket.count}')
        lines.append(f"browser_capture_file_size_bytes_sum {self.size_sum:.0f}")
        lines.append(f"browser_capture_file_size_bytes_count {self.size_count}")

        # Error counters
        lines.extend([
            "",
            "# HELP browser_capture_errors_total Capture errors by type",
            "# TYPE browser_capture_errors_total counter",
        ])
        for error_type, count in self.errors_by_type.items():
            safe_type = error_type.replace('"', '\\"')
            lines.append(f'browser_capture_errors_total{{type="{safe_type}"}} {count}')

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Domain Success Tracker (Redis-backed)
# ---------------------------------------------------------------------------

class DomainSuccessTracker:
    """
    Tracks domain-specific capture success rates in Redis.

    Used to:
    1. Identify domains that consistently fail browser capture
    2. Suggest AI fallback for problematic domains
    3. Build intelligence about domain behavior over time
    """

    _redis_client: Optional[Any] = None
    _redis_enabled: bool = False
    _redis_init_attempted: bool = False
    _memory_cache: Dict[str, Dict[str, int]] = {}

    @classmethod
    def _domain_key(cls, domain: str) -> str:
        return f"browser_capture:domain:{domain}"

    @classmethod
    def _init_redis(cls) -> None:
        if cls._redis_init_attempted:
            return
        cls._redis_init_attempted = True

        if Redis is None:
            logger.debug("Redis not installed, using in-memory domain tracking")
            cls._redis_enabled = False
            return

        redis_url = getattr(settings, "REDIS_URL", None)
        if not redis_url:
            logger.debug("REDIS_URL not configured, using in-memory domain tracking")
            cls._redis_enabled = False
            return

        try:
            cls._redis_client = Redis.from_url(redis_url, decode_responses=True)
            cls._redis_enabled = True
            logger.info("Domain success tracker connected to Redis")
        except Exception as exc:
            logger.warning("Redis unavailable for domain tracking: %s", exc)
            cls._redis_client = None
            cls._redis_enabled = False

    @classmethod
    async def record_attempt(cls, url: str, success: bool) -> None:
        """Record a capture attempt for a domain."""
        cls._init_redis()

        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not domain:
                return
        except Exception:
            return

        key = cls._domain_key(domain)
        field = "success" if success else "failure"

        # Always update memory cache
        if domain not in cls._memory_cache:
            cls._memory_cache[domain] = {"success": 0, "failure": 0}
        cls._memory_cache[domain][field] += 1

        if cls._redis_enabled and cls._redis_client:
            try:
                await cls._redis_client.hincrby(key, field, 1)
                await cls._redis_client.expire(key, DOMAIN_TTL_SECONDS)
            except Exception as exc:
                logger.warning("Failed to record domain attempt in Redis: %s", exc)

    @classmethod
    async def get_domain_stats(cls, domain: str) -> Dict[str, int]:
        """Get success/failure counts for a domain."""
        cls._init_redis()
        key = cls._domain_key(domain.lower())

        if cls._redis_enabled and cls._redis_client:
            try:
                stats = await cls._redis_client.hgetall(key)
                return {
                    "success": int(stats.get("success", 0)),
                    "failure": int(stats.get("failure", 0)),
                }
            except Exception as exc:
                logger.warning("Failed to get domain stats from Redis: %s", exc)

        # Fallback to memory
        return cls._memory_cache.get(domain.lower(), {"success": 0, "failure": 0})

    @classmethod
    async def should_use_fallback(cls, url: str) -> tuple[bool, str]:
        """
        Check if a URL's domain has poor capture success rate.

        Returns:
            (should_fallback, reason)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not domain:
                return False, ""
        except Exception:
            return False, ""

        stats = await cls.get_domain_stats(domain)
        total = stats["success"] + stats["failure"]

        if total < MIN_SAMPLES_FOR_FALLBACK:
            return False, ""

        failure_rate = stats["failure"] / total

        if failure_rate >= DOMAIN_FAILURE_THRESHOLD:
            reason = (
                f"Domain {domain} has {failure_rate*100:.0f}% failure rate "
                f"({stats['failure']}/{total} attempts)"
            )
            logger.info("Suggesting AI fallback: %s", reason)
            return True, reason

        return False, ""

    @classmethod
    async def get_all_domain_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Get stats for all tracked domains (for dashboard)."""
        cls._init_redis()
        result = {}

        if cls._redis_enabled and cls._redis_client:
            try:
                # Scan for all domain keys
                cursor = 0
                pattern = cls._domain_key("*")
                while True:
                    cursor, keys = await cls._redis_client.scan(cursor, match=pattern)
                    for key in keys:
                        domain = key.split(":")[-1]
                        stats = await cls._redis_client.hgetall(key)
                        success = int(stats.get("success", 0))
                        failure = int(stats.get("failure", 0))
                        total = success + failure
                        result[domain] = {
                            "success": success,
                            "failure": failure,
                            "total": total,
                            "success_rate": round(success / total * 100, 1) if total > 0 else 100,
                        }
                    if cursor == 0:
                        break
                return result
            except Exception as exc:
                logger.warning("Failed to scan domain stats from Redis: %s", exc)

        # Fallback to memory
        for domain, stats in cls._memory_cache.items():
            total = stats["success"] + stats["failure"]
            result[domain] = {
                "success": stats["success"],
                "failure": stats["failure"],
                "total": total,
                "success_rate": round(stats["success"] / total * 100, 1) if total > 0 else 100,
            }

        return result


# ---------------------------------------------------------------------------
# Debug Mode Handler
# ---------------------------------------------------------------------------

class CaptureDebugHandler:
    """
    Handles debug artifacts when BROWSER_CAPTURE_DEBUG=1.

    When enabled, saves:
    - HTML snapshots before/after scroll
    - Screenshots at each checkpoint
    - Timeline report with all events
    """

    def __init__(self, capture_id: str):
        self.capture_id = capture_id
        self.enabled = os.environ.get("BROWSER_CAPTURE_DEBUG", "").lower() in ("1", "true", "yes")
        self.events: List[Dict[str, Any]] = []
        self.start_time = time.time()

        if self.enabled:
            self.debug_dir = DEBUG_SNAPSHOT_DIR / capture_id
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Debug mode enabled for capture %s | dir=%s", capture_id, self.debug_dir)

    def log_event(self, event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log a debug event with timestamp."""
        event = {
            "timestamp": time.time() - self.start_time,
            "type": event_type,
            "details": details or {},
        }
        self.events.append(event)

        if self.enabled:
            logger.debug(
                "DEBUG[%s] %.3fs %s: %s",
                self.capture_id[:8],
                event["timestamp"],
                event_type,
                json.dumps(details) if details else "",
            )

    async def save_html_snapshot(self, page: Any, label: str) -> Optional[str]:
        """Save HTML content of the page."""
        if not self.enabled:
            return None

        try:
            html_content = await page.content()
            filename = f"{label}.html"
            filepath = self.debug_dir / filename
            filepath.write_text(html_content, encoding="utf-8")
            self.log_event("html_snapshot", {"label": label, "size": len(html_content)})
            return str(filepath)
        except Exception as exc:
            logger.warning("Failed to save HTML snapshot: %s", exc)
            return None

    async def save_screenshot(self, page: Any, label: str) -> Optional[str]:
        """Save screenshot of the page."""
        if not self.enabled:
            return None

        try:
            filename = f"{label}.png"
            filepath = self.debug_dir / filename
            await page.screenshot(path=str(filepath), full_page=False)
            self.log_event("screenshot", {"label": label, "path": str(filepath)})
            return str(filepath)
        except Exception as exc:
            logger.warning("Failed to save screenshot: %s", exc)
            return None

    def save_timeline_report(self) -> Optional[str]:
        """Generate and save timeline report."""
        if not self.enabled or not self.events:
            return None

        try:
            report = {
                "capture_id": self.capture_id,
                "total_duration_sec": time.time() - self.start_time,
                "event_count": len(self.events),
                "events": self.events,
                "generated_at": datetime.utcnow().isoformat(),
            }

            filepath = self.debug_dir / "timeline_report.json"
            filepath.write_text(json.dumps(report, indent=2), encoding="utf-8")
            logger.info(
                "Debug timeline saved | capture=%s | events=%d | path=%s",
                self.capture_id[:8],
                len(self.events),
                filepath,
            )
            return str(filepath)
        except Exception as exc:
            logger.warning("Failed to save timeline report: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

async def check_browser_capture_health() -> Dict[str, Any]:
    """
    Perform health check on browser capture subsystem.

    Tests capture against a known-good URL (playwright.dev) and returns status.
    """
    from services.browser_automation import BrowserAutomation

    result = {
        "status": "unknown",
        "checked_at": datetime.utcnow().isoformat(),
        "url": HEALTH_CHECK_URL,
        "duration_sec": None,
        "file_size_bytes": None,
        "error": None,
    }

    start_time = time.time()
    browser = None

    try:
        browser = BrowserAutomation()
        video_path, metrics = await asyncio.wait_for(
            browser.record_video_for_tutorial(
                url=HEALTH_CHECK_URL,
                scene_duration_sec=3.0,
                capture_mode="static",
            ),
            timeout=HEALTH_CHECK_TIMEOUT_SEC,
        )

        duration = time.time() - start_time
        result["duration_sec"] = round(duration, 2)

        # Check file exists and has reasonable size
        if video_path:
            video_file = Path(video_path)
            if video_file.exists():
                file_size = video_file.stat().st_size
                result["file_size_bytes"] = file_size

                if file_size > 2000:
                    result["status"] = "healthy"
                else:
                    result["status"] = "degraded"
                    result["error"] = f"File too small: {file_size} bytes"
            else:
                result["status"] = "unhealthy"
                result["error"] = "Video file not created"
        else:
            result["status"] = "unhealthy"
            result["error"] = "No video path returned"

    except asyncio.TimeoutError:
        result["status"] = "unhealthy"
        result["duration_sec"] = HEALTH_CHECK_TIMEOUT_SEC
        result["error"] = f"Timeout after {HEALTH_CHECK_TIMEOUT_SEC}s"
    except Exception as exc:
        result["status"] = "unhealthy"
        result["duration_sec"] = round(time.time() - start_time, 2)
        result["error"] = str(exc)
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    # Add metrics summary
    result["metrics_summary"] = capture_metrics.get_summary()

    return result


# ---------------------------------------------------------------------------
# Module-level instances
# ---------------------------------------------------------------------------

# Global metrics collector (in-memory, resets on restart)
capture_metrics = CaptureMetricsCollector()

# Global domain tracker (Redis-backed with memory fallback)
domain_tracker = DomainSuccessTracker()
