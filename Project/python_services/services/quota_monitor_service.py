"""
Quota monitoring helpers for AI/provider spend visibility.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config.settings import settings
from services.content_persistence_service import ContentPersistenceService

logger = logging.getLogger(__name__)


def _normalize_provider(provider: str) -> str:
    return str(provider).strip().lower().replace(" ", "_").replace("-", "_")


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, "", []):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, "", []):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_clone(value: Any) -> Any:
    if value is None:
        return {}
    return json.loads(json.dumps(value, default=str))


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _read_env_float(name: str) -> Optional[float]:
    return _safe_float(os.getenv(name))


def _read_env_int(name: str) -> Optional[int]:
    return _safe_int(os.getenv(name))


def _looks_like_real_secret(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    placeholder_prefixes = (
        "your_",
        "changeme",
        "change-this",
        "replace-me",
        "example_",
    )
    if lowered.startswith(placeholder_prefixes):
        return False
    if lowered in {
        "none",
        "null",
        "placeholder",
        "todo",
        "tbd",
    }:
        return False
    return True


class QuotaMonitorService:
    """
    Tracks provider usage, cost, and quota snapshots.

    v1 focuses on:
    - manual snapshot ingestion
    - DB-backed persistence when asyncpg is available
    - safe in-memory fallback for local dev
    - provider inventory derived from current environment
    """

    _memory_lock = asyncio.Lock()
    _memory_snapshots: List[Dict[str, Any]] = []
    _live_refresh_lock = asyncio.Lock()
    _last_live_refresh_at: Dict[str, datetime] = {}

    PROVIDERS = {
        "openai": {
            "label": "OpenAI",
            "api_key_attr": "OPENAI_API_KEY",
            "usage_unit": "tokens",
            "limit_attr": "OPENAI_MONTHLY_TOKEN_LIMIT",
            "remaining_support": "provider_headers",
            "remaining_note": (
                "Exact remaining tokens come from OpenAI rate-limit response headers"
                " captured by this app's requests."
            ),
        },
        "anthropic": {
            "label": "Anthropic",
            "api_key_attr": "ANTHROPIC_API_KEY",
            "usage_unit": "tokens",
            "limit_attr": "ANTHROPIC_MONTHLY_TOKEN_LIMIT",
            "remaining_support": "provider_headers",
            "remaining_note": (
                "Exact remaining tokens come from Anthropic response headers."
            ),
        },
        "gemini": {
            "label": "Google Gemini",
            "api_key_attr": "GOOGLE_AI_API_KEY",
            "usage_unit": "tokens",
            "limit_attr": "GOOGLE_AI_MONTHLY_TOKEN_LIMIT",
            "remaining_support": "configured_limit_only",
            "remaining_note": (
                "This integration can track Gemini usage locally, but Google does not"
                " expose live remaining quota through the current API-key workflow."
            ),
        },
        "fal_ai": {
            "label": "fal.ai",
            "api_key_attr": "FAL_AI_API_KEY",
            "usage_unit": "requests",
            "limit_attr": "FAL_AI_MONTHLY_REQUEST_LIMIT",
            "remaining_support": "configured_limit_only",
            "remaining_note": (
                "fal exposes usage analytics, but not a live remaining-balance value"
                " in the current integration."
            ),
        },
        "google_tts": {
            "label": "Google TTS",
            "api_key_attr": "GOOGLE_TTS_API_KEY",
            "usage_unit": "characters",
            "limit_attr": "GOOGLE_TTS_MONTHLY_CHAR_LIMIT",
            "remaining_support": "configured_limit_only",
            "remaining_note": (
                "This integration can track Google TTS usage locally, but live remaining"
                " quota is not available via the current API-key workflow."
            ),
        },
        "heygen": {
            "label": "HeyGen",
            "api_key_attr": "HEYGEN_API_KEY",
            "usage_unit": "jobs",
            "limit_attr": "HEYGEN_MONTHLY_JOB_LIMIT",
            "remaining_support": "live_endpoint",
            "remaining_note": (
                "Remaining quota is refreshed from HeyGen's remaining quota endpoint."
            ),
        },
    }

    @classmethod
    async def _get_pool(cls) -> Any:
        return await ContentPersistenceService._get_pool()

    @classmethod
    def clear_memory_snapshots(cls) -> None:
        cls._memory_snapshots = []

    @classmethod
    def _provider_definition(cls, provider: str) -> Dict[str, Any]:
        provider_key = _normalize_provider(provider)
        definition = dict(cls.PROVIDERS.get(provider_key, {}))
        api_key_attr = definition.get("api_key_attr")
        api_key = getattr(settings, api_key_attr, None) if api_key_attr else None
        limit_attr = definition.get("limit_attr")
        configured_monthly_limit = (
            getattr(settings, limit_attr, None) if limit_attr else None
        )

        definition.update(
            {
                "provider": provider_key,
                "configured": _looks_like_real_secret(api_key),
                "api_key_attr": api_key_attr,
                "api_key_present": _looks_like_real_secret(api_key),
                "monthly_limit": configured_monthly_limit
                if configured_monthly_limit is not None
                else _read_env_float(f"QUOTA_{provider_key.upper()}_MONTHLY_LIMIT"),
                "monthly_limit_usd": _read_env_float(
                    f"QUOTA_{provider_key.upper()}_MONTHLY_LIMIT_USD"
                ),
                "warn_at_percent": _read_env_float(
                    f"QUOTA_{provider_key.upper()}_WARN_AT_PERCENT"
                )
                or settings.API_QUOTA_ALERT_THRESHOLD,
                "reset_at": os.getenv(f"QUOTA_{provider_key.upper()}_RESET_AT"),
                "spend_limit_usd": _read_env_float(
                    f"QUOTA_{provider_key.upper()}_SPEND_LIMIT_USD"
                ),
            }
        )
        return definition

    @classmethod
    async def record_runtime_usage(
        cls,
        provider: str,
        usage: Optional[Dict[str, Any]] = None,
        cost_usd: Optional[float] = None,
        quota: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        provider_profile = cls._provider_definition(provider)
        normalized_quota = _json_clone(quota or {})
        if provider_profile.get("monthly_limit") is not None and "limit" not in normalized_quota:
            quota_unit = normalized_quota.get("unit")
            if quota_unit in (None, provider_profile.get("usage_unit")):
                normalized_quota["limit"] = provider_profile["monthly_limit"]

        try:
            await cls.record_snapshot(
                provider=provider,
                usage=usage,
                cost_usd=cost_usd,
                quota=normalized_quota,
                source="runtime",
                metadata=metadata,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Failed to record runtime usage for %s: %s", provider, exc)

    @classmethod
    def provider_catalog(cls) -> List[Dict[str, Any]]:
        return [cls._provider_definition(provider) for provider in cls.PROVIDERS]

    @classmethod
    def _live_refresh_ttl_seconds(cls) -> int:
        ttl = _safe_int(getattr(settings, "API_QUOTA_REFRESH_TTL_SECONDS", 60))
        return max(ttl or 60, 5)

    @classmethod
    async def _refresh_provider_live_snapshot(
        cls,
        provider: str,
        force: bool = False,
    ) -> None:
        provider_key = _normalize_provider(provider)
        provider_profile = cls._provider_definition(provider_key)
        if not provider_profile.get("configured"):
            return
        if provider_profile.get("remaining_support") != "live_endpoint":
            return

        now = datetime.utcnow()
        async with cls._live_refresh_lock:
            last_refresh = cls._last_live_refresh_at.get(provider_key)
            if (
                not force
                and last_refresh is not None
                and (now - last_refresh).total_seconds() < cls._live_refresh_ttl_seconds()
            ):
                return
            cls._last_live_refresh_at[provider_key] = now

        try:
            if provider_key == "heygen":
                from services.heygen_service import HeyGenService

                service = HeyGenService()
                await service.get_remaining_quota()
        except Exception as exc:
            logger.warning("Failed to refresh live quota for %s: %s", provider_key, exc)

    @classmethod
    async def refresh_live_provider_snapshots(cls, force: bool = False) -> None:
        for provider_profile in cls.provider_catalog():
            await cls._refresh_provider_live_snapshot(
                provider=provider_profile["provider"],
                force=force,
            )

    @classmethod
    def _build_snapshot_record(
        cls,
        provider: str,
        usage: Optional[Dict[str, Any]] = None,
        cost_usd: Optional[float] = None,
        quota: Optional[Dict[str, Any]] = None,
        source: str = "manual",
        observed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        snapshot_time = observed_at or datetime.utcnow()
        return {
            "id": str(uuid4()),
            "provider": _normalize_provider(provider),
            "source": source or "manual",
            "usage": _json_clone(usage or {}),
            "cost_usd": _safe_float(cost_usd),
            "quota": _json_clone(quota or {}),
            "observed_at": snapshot_time.isoformat(),
            "metadata": _json_clone(metadata or {}),
            "created_at": datetime.utcnow().isoformat(),
        }

    @classmethod
    async def _store_snapshot_db(cls, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        pool = await cls._get_pool()
        event_metadata = {
            "snapshot_id": snapshot["id"],
            "provider": snapshot["provider"],
            "source": snapshot["source"],
            "usage": snapshot["usage"],
            "cost_usd": snapshot["cost_usd"],
            "quota": snapshot["quota"],
            "observed_at": snapshot["observed_at"],
            "captured_at": snapshot["created_at"],
            "metadata": snapshot["metadata"],
        }
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.analytics_events (
                    content_id,
                    event_type,
                    platform,
                    metadata
                )
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                None,
                "api_usage",
                snapshot["provider"],
                json.dumps(event_metadata),
            )
        return snapshot

    @classmethod
    async def _store_snapshot_memory(cls, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        async with cls._memory_lock:
            cls._memory_snapshots.append(snapshot)
        return snapshot

    @classmethod
    async def record_snapshot(
        cls,
        provider: str,
        usage: Optional[Dict[str, Any]] = None,
        cost_usd: Optional[float] = None,
        quota: Optional[Dict[str, Any]] = None,
        source: str = "manual",
        observed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        snapshot = cls._build_snapshot_record(
            provider=provider,
            usage=usage,
            cost_usd=cost_usd,
            quota=quota,
            source=source,
            observed_at=observed_at,
            metadata=metadata,
        )

        try:
            return await cls._store_snapshot_db(snapshot)
        except Exception as exc:
            logger.warning("Using in-memory quota snapshot fallback: %s", exc)
            return await cls._store_snapshot_memory(snapshot)

    @classmethod
    def _normalize_row(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _json_clone(row.get("metadata") or {})
        provider = _normalize_provider(row.get("platform") or metadata.get("provider"))
        snapshot_id = metadata.get("snapshot_id") or metadata.get("id")
        return {
            "id": str(snapshot_id or row.get("id") or uuid4()),
            "provider": provider,
            "source": metadata.get("source") or "manual",
            "usage": _json_clone(metadata.get("usage") or {}),
            "cost_usd": _safe_float(metadata.get("cost_usd")),
            "quota": _json_clone(metadata.get("quota") or {}),
            "observed_at": (
                metadata.get("observed_at")
                or (
                    row["created_at"].isoformat()
                    if isinstance(row.get("created_at"), datetime)
                    else str(row.get("created_at") or "")
                )
            ),
            "metadata": _json_clone(metadata.get("metadata") or {}),
            "created_at": (
                row["created_at"].isoformat()
                if isinstance(row.get("created_at"), datetime)
                else str(row.get("created_at") or row.get("observed_at") or "")
            ),
        }

    @classmethod
    async def _list_memory_snapshots(
        cls,
        provider: Optional[str] = None,
        limit: int = 100,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        provider_key = _normalize_provider(provider) if provider else None
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with cls._memory_lock:
            snapshots = list(cls._memory_snapshots)

        filtered: List[Dict[str, Any]] = []
        for snapshot in snapshots:
            if provider_key and snapshot["provider"] != provider_key:
                continue
            observed_at = _parse_datetime(snapshot.get("observed_at"))
            if observed_at and observed_at < cutoff:
                continue
            filtered.append(snapshot)

        filtered.sort(
            key=lambda item: _parse_datetime(item.get("observed_at")) or datetime.min,
            reverse=True,
        )
        return filtered[:limit]

    @classmethod
    async def list_snapshots(
        cls,
        provider: Optional[str] = None,
        limit: int = 100,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        provider_key = _normalize_provider(provider) if provider else None
        try:
            pool = await cls._get_pool()
            async with pool.acquire() as conn:
                if provider_key:
                    rows = await conn.fetch(
                        """
                        SELECT content_id, platform, metadata, created_at
                        FROM public.analytics_events
                        WHERE event_type = 'api_usage'
                          AND platform = $1
                          AND created_at >= NOW() - make_interval(days => $2)
                        ORDER BY created_at DESC
                        LIMIT $3
                        """,
                        provider_key,
                        days,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT content_id, platform, metadata, created_at
                        FROM public.analytics_events
                        WHERE event_type = 'api_usage'
                          AND created_at >= NOW() - make_interval(days => $1)
                        ORDER BY created_at DESC
                        LIMIT $2
                        """,
                        days,
                        limit,
                    )
            return [cls._normalize_row(dict(row)) for row in rows]
        except Exception as exc:
            logger.warning("Falling back to in-memory quota snapshots: %s", exc)
            return await cls._list_memory_snapshots(
                provider=provider_key, limit=limit, days=days
            )

    @classmethod
    def _aggregate_snapshots(
        cls,
        snapshots: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        provider_rollup: Dict[str, Dict[str, Any]] = {}
        for snapshot in snapshots:
            provider = snapshot["provider"]
            rollup = provider_rollup.setdefault(
                provider,
                {
                    "provider": provider,
                    "snapshot_count": 0,
                    "cost_usd": 0.0,
                    "usage": {},
                    "latest_snapshot": None,
                    "latest_observed_at": None,
                },
            )

            rollup["snapshot_count"] += 1
            rollup["cost_usd"] += _safe_float(snapshot.get("cost_usd")) or 0.0

            usage = snapshot.get("usage") or {}
            if isinstance(usage, dict):
                for key, value in usage.items():
                    numeric_value = _safe_float(value)
                    if numeric_value is None:
                        continue
                    rollup["usage"][key] = rollup["usage"].get(key, 0.0) + numeric_value

            observed_at = _parse_datetime(snapshot.get("observed_at"))
            if observed_at and (
                rollup["latest_observed_at"] is None
                or observed_at > rollup["latest_observed_at"]
            ):
                rollup["latest_snapshot"] = snapshot
                rollup["latest_observed_at"] = observed_at

        return provider_rollup

    @classmethod
    def _remaining_message(
        cls,
        provider_profile: Dict[str, Any],
        remaining_source: str,
        remaining_exact: bool,
        remaining_value: Optional[float],
    ) -> str:
        if remaining_value is not None:
            if remaining_exact:
                if remaining_source == "provider_live_endpoint":
                    return "Exact remaining quota refreshed from the provider."
                if remaining_source == "provider_response_headers":
                    return (
                        "Exact remaining quota captured from the latest provider"
                        " API response handled by this app."
                    )
            return "Remaining quota derived from locally tracked usage and configured limits."

        support = provider_profile.get("remaining_support")
        if support == "provider_headers":
            return (
                "Exact remaining quota will appear after this app makes a successful"
                " request to the provider."
            )
        if support == "live_endpoint":
            return provider_profile.get("remaining_note") or "Live quota refresh is supported."
        return provider_profile.get("remaining_note") or "Live remaining quota is unavailable."

    @classmethod
    def _derive_remaining_details(
        cls,
        provider_profile: Dict[str, Any],
        provider_rollup: Dict[str, Any],
    ) -> Dict[str, Any]:
        latest_snapshot = provider_rollup.get("latest_snapshot") or {}
        latest_quota = latest_snapshot.get("quota") or {}

        remaining_value = _safe_float(latest_quota.get("remaining"))
        remaining_limit = _safe_float(latest_quota.get("limit"))
        remaining_unit = latest_quota.get("unit") or provider_profile.get("usage_unit")
        remaining_source = str(
            latest_quota.get("source")
            or (
                "provider_response_headers"
                if latest_quota.get("exact")
                else provider_profile.get("remaining_support") or "unavailable"
            )
        )
        remaining_exact = bool(latest_quota.get("exact"))
        remaining_reset_at = latest_quota.get("reset_at")
        remaining_reset_after = latest_quota.get("reset_after")
        requests_remaining = _safe_float(latest_quota.get("requests_remaining"))
        requests_limit = _safe_float(latest_quota.get("requests_limit"))
        requests_reset_at = latest_quota.get("requests_reset_at")
        requests_reset_after = latest_quota.get("requests_reset_after")

        if remaining_value is None:
            monthly_limit = _safe_float(provider_profile.get("monthly_limit"))
            usage_unit = provider_profile.get("usage_unit")
            usage_total = _safe_float((provider_rollup.get("usage") or {}).get(usage_unit))
            if monthly_limit not in (None, 0) and usage_total is not None:
                remaining_value = max(monthly_limit - usage_total, 0.0)
                remaining_limit = monthly_limit
                remaining_unit = usage_unit
                remaining_source = "tracked_usage"
                remaining_exact = False

        return {
            "remaining_value": remaining_value,
            "remaining_limit": remaining_limit,
            "remaining_unit": remaining_unit,
            "remaining_exact": remaining_exact,
            "remaining_source": remaining_source,
            "remaining_reset_at": remaining_reset_at,
            "remaining_reset_after": remaining_reset_after,
            "remaining_observed_at": latest_snapshot.get("observed_at"),
            "remaining_requests": requests_remaining,
            "remaining_requests_limit": requests_limit,
            "remaining_requests_reset_at": requests_reset_at,
            "remaining_requests_reset_after": requests_reset_after,
            "remaining_message": cls._remaining_message(
                provider_profile=provider_profile,
                remaining_source=remaining_source,
                remaining_exact=remaining_exact,
                remaining_value=remaining_value,
            ),
        }

    @classmethod
    def _derive_status(
        cls,
        provider_profile: Dict[str, Any],
        provider_rollup: Dict[str, Any],
    ) -> str:
        if not provider_profile.get("api_key_present"):
            return "not_configured"

        remaining_details = cls._derive_remaining_details(provider_profile, provider_rollup)
        remaining = remaining_details.get("remaining_value")
        limit = remaining_details.get("remaining_limit")
        warn_at_percent = _safe_float(provider_profile.get("warn_at_percent")) or 80.0
        threshold = warn_at_percent / 100.0

        if remaining is not None and limit not in (None, 0):
            ratio = remaining / limit
            if ratio <= 0:
                return "critical"
            if ratio <= (1 - threshold):
                return "warning"
            return "ok"

        spend_limit = provider_profile.get("spend_limit_usd")
        if spend_limit is not None:
            current_spend = _safe_float(provider_rollup.get("cost_usd")) or 0.0
            if current_spend >= spend_limit:
                return "critical"
            if current_spend >= spend_limit * threshold:
                return "warning"
            return "ok"

        usage_unit = provider_profile.get("usage_unit")
        monthly_limit = _safe_float(provider_profile.get("monthly_limit"))
        usage_totals = provider_rollup.get("usage") or {}
        usage_total = _safe_float(usage_totals.get(usage_unit))
        if monthly_limit not in (None, 0) and usage_total is not None:
            if usage_total >= monthly_limit:
                return "critical"
            if usage_total >= monthly_limit * threshold:
                return "warning"
            return "ok"

        if provider_rollup.get("snapshot_count"):
            return "ok"

        return "unknown"

    @classmethod
    async def get_summary(cls, days: int = 30) -> Dict[str, Any]:
        await cls.refresh_live_provider_snapshots()
        snapshots = await cls.list_snapshots(limit=1000, days=days)
        rollups = cls._aggregate_snapshots(snapshots)

        provider_items: List[Dict[str, Any]] = []
        total_cost = 0.0
        total_snapshots = 0
        total_usage: Dict[str, float] = {}
        covered_providers = set()

        for provider_profile in cls.provider_catalog():
            provider_key = provider_profile["provider"]
            covered_providers.add(provider_key)
            provider_rollup = rollups.get(
                provider_key,
                {
                    "provider": provider_key,
                    "snapshot_count": 0,
                    "cost_usd": 0.0,
                    "usage": {},
                    "latest_snapshot": None,
                },
            )

            status = cls._derive_status(provider_profile, provider_rollup)
            remaining_details = cls._derive_remaining_details(
                provider_profile=provider_profile,
                provider_rollup=provider_rollup,
            )
            provider_item = {
                **provider_profile,
                "status": status,
                "snapshot_count": provider_rollup["snapshot_count"],
                "cost_usd": round(provider_rollup["cost_usd"], 4),
                "usage": provider_rollup["usage"],
                "usage_value": _safe_float(
                    provider_rollup["usage"].get(provider_profile.get("usage_unit"))
                ),
                "latest_snapshot": provider_rollup["latest_snapshot"],
                **remaining_details,
            }
            provider_items.append(provider_item)
            total_cost += provider_rollup["cost_usd"]
            total_snapshots += provider_rollup["snapshot_count"]

            for key, value in provider_rollup["usage"].items():
                total_usage[key] = total_usage.get(key, 0.0) + value

        for provider_key, provider_rollup in rollups.items():
            if provider_key in covered_providers:
                continue

            provider_profile = {
                "provider": provider_key,
                "label": provider_key.replace("_", " ").title(),
                "configured": False,
                "api_key_attr": None,
                "api_key_present": False,
                "usage_unit": "custom",
                "monthly_limit": None,
                "monthly_limit_usd": None,
                "warn_at_percent": 80.0,
                "reset_at": None,
                "spend_limit_usd": None,
                "remaining_support": "configured_limit_only",
                "remaining_note": "No provider metadata is registered for this provider.",
            }
            status = cls._derive_status(provider_profile, provider_rollup)
            remaining_details = cls._derive_remaining_details(
                provider_profile=provider_profile,
                provider_rollup=provider_rollup,
            )
            provider_item = {
                **provider_profile,
                "status": status,
                "snapshot_count": provider_rollup["snapshot_count"],
                "cost_usd": round(provider_rollup["cost_usd"], 4),
                "usage": provider_rollup["usage"],
                "usage_value": _safe_float(
                    provider_rollup["usage"].get(provider_profile.get("usage_unit"))
                ),
                "latest_snapshot": provider_rollup["latest_snapshot"],
                **remaining_details,
            }
            provider_items.append(provider_item)
            total_cost += provider_rollup["cost_usd"]
            total_snapshots += provider_rollup["snapshot_count"]

            for key, value in provider_rollup["usage"].items():
                total_usage[key] = total_usage.get(key, 0.0) + value

        recent_snapshots = snapshots[:20]
        return {
            "time_period": f"{days}_days",
            "total_snapshots": total_snapshots,
            "total_cost_usd": round(total_cost, 4),
            "usage_totals": total_usage,
            "providers": provider_items,
            "recent_snapshots": recent_snapshots,
        }

    @classmethod
    async def get_provider_overview(cls, days: int = 30) -> Dict[str, Any]:
        summary = await cls.get_summary(days=days)
        return {
            "time_period": summary["time_period"],
            "providers": summary["providers"],
            "total_cost_usd": summary["total_cost_usd"],
            "total_snapshots": summary["total_snapshots"],
        }

    @classmethod
    async def get_provider_detail(
        cls, provider: str, days: int = 30
    ) -> Dict[str, Any]:
        provider_key = _normalize_provider(provider)
        summary = await cls.get_summary(days=days)
        for item in summary["providers"]:
            if item["provider"] == provider_key:
                return {
                    "time_period": summary["time_period"],
                    "provider": item,
                    "recent_snapshots": [
                        snapshot
                        for snapshot in summary["recent_snapshots"]
                        if snapshot["provider"] == provider_key
                    ],
                }

        raise KeyError(f"Unknown provider: {provider_key}")
