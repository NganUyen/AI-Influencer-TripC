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
from services.errors import QuotaExceededError

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


def _json_loads_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


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


def _quota_enforcement_enabled() -> bool:
    raw = os.getenv("API_QUOTA_ENFORCEMENT_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


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

    # Estimated costs per unit if not provided by response headers
    PRICE_MAP = {
        "openai": 0.00001,  # $10 per 1M tokens (blended input/output)
        "anthropic": 0.00001,  # $10 per 1M tokens
        "gemini": 0.000005,  # $5 per 1M tokens
        "google_tts": 0.000004,  # $4 per 1M chars
        "fal_ai": 0.05,  # $0.05 per request avg
        "heygen": 2.0,  # $2.00 per job
    }

    PROVIDERS = {
        "openai": {
            "label": "OpenAI",
            "api_key_attr": "OPENAI_API_KEY",
            "usage_unit": "tokens",
            "billing_type": "pay_as_you_go",
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
            "billing_type": "pay_as_you_go",
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
            "billing_type": "pay_as_you_go",
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
            "billing_type": "pay_as_you_go",
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
            "billing_type": "pay_as_you_go",
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
            "billing_type": "subscription",
            "limit_attr": "HEYGEN_MONTHLY_JOB_LIMIT",
            "remaining_support": "live_endpoint",
            "remaining_note": (
                "Remaining quota is refreshed from HeyGen's remaining quota endpoint."
            ),
        },
        "openclaw": {
            "label": "OpenClaw",
            "api_key_attr": "OPENCLAW_API_KEY",
            "usage_unit": "requests",
            "billing_type": "subscription",
            "limit_attr": None,
            "remaining_support": "configured_limit_only",
            "remaining_note": "OpenClaw status monitoring.",
        },
        "postiz": {
            "label": "Postiz",
            "api_key_attr": "POSTIZ_API_KEY",
            "usage_unit": "posts",
            "billing_type": "subscription",
            "limit_attr": None,
            "remaining_support": "configured_limit_only",
            "remaining_note": "Postiz social publishing monitoring.",
        },
        "growchief": {
            "label": "GrowChief",
            "api_key_attr": "GROWCHIEF_API_KEY",
            "usage_unit": "workflows",
            "billing_type": "subscription",
            "limit_attr": None,
            "remaining_support": "configured_limit_only",
            "remaining_note": "GrowChief automation monitoring.",
        },
        "telegram": {
            "label": "Telegram Bot",
            "api_key_attr": "TELEGRAM_BOT_TOKEN",
            "usage_unit": "messages",
            "billing_type": "subscription",
            "limit_attr": None,
            "remaining_support": "configured_limit_only",
            "remaining_note": "Telegram bot API monitoring.",
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
        user_id: Optional[str] = None,
    ) -> None:
        provider_profile = cls._provider_definition(provider)
        normalized_quota = _json_clone(quota or {})

        # Estimate cost if missing for pay-as-you-go providers
        if cost_usd is None and usage:
            usage_unit = provider_profile.get("usage_unit")
            unit_usage = _safe_float(usage.get(usage_unit))
            if unit_usage is not None:
                price_per_unit = cls.PRICE_MAP.get(_normalize_provider(provider))
                if price_per_unit:
                    cost_usd = round(unit_usage * price_per_unit, 6)

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
                user_id=user_id,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Failed to record runtime usage for %s: %s", provider, exc)

    @classmethod
    async def assert_within_budget(
        cls,
        provider: str,
        *,
        estimated_usage: Optional[Dict[str, Any]] = None,
        estimated_cost_usd: Optional[float] = None,
        operation: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        if not _quota_enforcement_enabled():
            return

        provider_key = _normalize_provider(provider)
        provider_profile = cls._provider_definition(provider_key)
        if not provider_profile.get("configured"):
            return

        if provider_profile.get("remaining_support") == "live_endpoint":
            await cls._refresh_provider_live_snapshot(provider_key)

        snapshots = await cls.list_snapshots(
            provider=provider_key,
            limit=50000,
            days=0,
            user_id=user_id,
        )
        provider_rollup = cls._aggregate_snapshots(snapshots).get(
            provider_key,
            {
                "provider": provider_key,
                "snapshot_count": 0,
                "cost_usd": 0.0,
                "usage": {},
                "latest_snapshot": None,
            },
        )
        remaining_details = cls._derive_remaining_details(
            provider_profile=provider_profile,
            provider_rollup=provider_rollup,
        )

        normalized_usage: Dict[str, Any] = {"requests": 1}
        if estimated_usage:
            normalized_usage.update(
                {
                    key: value
                    for key, value in estimated_usage.items()
                    if value is not None
                }
            )

        reasons: List[str] = []
        remaining_requests = _safe_float(remaining_details.get("remaining_requests"))
        requests_needed = _safe_float(normalized_usage.get("requests")) or 0.0
        if remaining_requests is not None and requests_needed > remaining_requests:
            reasons.append(
                f"needs {requests_needed:g} requests but only {remaining_requests:g} remain"
            )

        usage_unit = provider_profile.get("usage_unit")
        unit_needed = _safe_float(normalized_usage.get(usage_unit)) if usage_unit else None
        remaining_value = _safe_float(remaining_details.get("remaining_value"))
        remaining_unit = str(remaining_details.get("remaining_unit") or "").strip() or None
        remaining_exact = bool(remaining_details.get("remaining_exact"))

        if (
            unit_needed is not None
            and remaining_value is not None
            and usage_unit
            and remaining_unit == usage_unit
            and unit_needed > remaining_value
        ):
            reasons.append(
                f"needs {unit_needed:g} {usage_unit} but only {remaining_value:g} remain"
            )
        elif (
            remaining_value is not None
            and remaining_value <= 0
            and (requests_needed > 0 or (unit_needed is not None and unit_needed > 0))
            and (remaining_exact or remaining_unit in {usage_unit, None})
        ):
            reasons.append(
                f"remaining {remaining_unit or usage_unit or 'quota'} is exhausted"
            )

        spend_needed = estimated_cost_usd
        if spend_needed is None and usage_unit and unit_needed is not None:
            price_per_unit = cls.PRICE_MAP.get(provider_key)
            if price_per_unit is not None:
                spend_needed = round(unit_needed * price_per_unit, 6)

        remaining_usd = _safe_float(remaining_details.get("remaining_usd"))
        if (
            spend_needed is not None
            and remaining_usd is not None
            and spend_needed > remaining_usd
        ):
            reasons.append(
                f"needs about ${spend_needed:.4f} but only ${remaining_usd:.4f} remain"
            )

        if not reasons:
            return

        provider_label = provider_profile.get("label") or provider_key
        action = operation or "requested operation"
        message = f"{provider_label} quota exhausted before {action}: {'; '.join(reasons)}."
        blocked_error = QuotaExceededError(message)

        quota_snapshot = {
            "remaining": remaining_value,
            "limit": remaining_details.get("remaining_limit"),
            "unit": remaining_unit,
            "source": remaining_details.get("remaining_source"),
            "exact": remaining_exact,
            "requests_remaining": remaining_requests,
            "requests_limit": remaining_details.get("remaining_requests_limit"),
        }
        await cls.record_runtime_usage(
            provider=provider_key,
            usage={},
            cost_usd=0.0,
            quota=quota_snapshot,
            metadata={
                "service": "quota_monitor_service",
                "operation": operation or "quota_guard",
                "status": "blocked",
                "error_type": type(blocked_error).__name__,
                "error_message": str(blocked_error),
                "estimated_usage": normalized_usage,
                "estimated_cost_usd": spend_needed,
            },
            user_id=user_id,
        )
        raise blocked_error

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
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot_time = observed_at or datetime.utcnow()
        return {
            "id": str(uuid4()),
            "user_id": user_id,
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
        user_id = snapshot.get("user_id") or "00000000-0000-0000-0000-000000000001"
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
                    user_id,
                    event_type,
                    platform,
                    metadata
                )
                VALUES ($1, $2::uuid, $3, $4, $5::jsonb)
                """,
                None,
                user_id,
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
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot = cls._build_snapshot_record(
            provider=provider,
            usage=usage,
            cost_usd=cost_usd,
            quota=quota,
            source=source,
            observed_at=observed_at,
            metadata=metadata,
            user_id=user_id,
        )

        try:
            return await cls._store_snapshot_db(snapshot)
        except Exception as exc:
            logger.warning("Using in-memory quota snapshot fallback: %s", exc)
            return await cls._store_snapshot_memory(snapshot)

    @classmethod
    def _normalize_row(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        metadata = _json_loads_if_needed(row.get("metadata") or {})
        if not isinstance(metadata, dict):
            metadata = {}

        usage = _json_loads_if_needed(metadata.get("usage") or {})
        if not isinstance(usage, dict):
            usage = {}

        quota = _json_loads_if_needed(metadata.get("quota") or {})
        if not isinstance(quota, dict):
            quota = {}

        nested_metadata = _json_loads_if_needed(metadata.get("metadata") or {})
        if not isinstance(nested_metadata, dict):
            nested_metadata = {}

        provider = _normalize_provider(
            row.get("platform") or metadata.get("provider") or "unknown"
        )
        snapshot_id = metadata.get("snapshot_id") or metadata.get("id")
        return {
            "id": str(snapshot_id or row.get("id") or uuid4()),
            "provider": provider,
            "source": metadata.get("source") or "manual",
            "usage": _json_clone(usage),
            "cost_usd": _safe_float(metadata.get("cost_usd")),
            "quota": _json_clone(quota),
            "observed_at": (
                metadata.get("observed_at")
                or (
                    row["created_at"].isoformat()
                    if isinstance(row.get("created_at"), datetime)
                    else str(row.get("created_at") or "")
                )
            ),
            "metadata": _json_clone(nested_metadata),
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
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        provider_key = _normalize_provider(provider) if provider else None
        cutoff = datetime.utcnow() - timedelta(days=days)

        async with cls._memory_lock:
            snapshots = list(cls._memory_snapshots)

        filtered: List[Dict[str, Any]] = []
        for snapshot in snapshots:
            if provider_key and snapshot["provider"] != provider_key:
                continue
            
            if user_id and snapshot.get("user_id") != user_id:
                continue
            
            if days > 0:
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
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        provider_key = _normalize_provider(provider) if provider else None
        try:
            pool = await cls._get_pool()
            where_clauses = ["event_type = 'api_usage'"]
            params = []
            
            if provider_key:
                params.append(provider_key)
                where_clauses.append(f"platform = ${len(params)}")
            
            if user_id:
                params.append(user_id)
                where_clauses.append(f"user_id = ${len(params)}::uuid")
            
            if days > 0:
                params.append(days)
                where_clauses.append(f"created_at >= NOW() - make_interval(days => ${len(params)})")
                
            query = f"""
                SELECT content_id, platform, metadata, created_at, user_id
                FROM public.analytics_events
                WHERE {" AND ".join(where_clauses)}
                ORDER BY created_at DESC
                LIMIT ${len(params) + 1}
            """
            
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params, limit)
            return [cls._normalize_row(dict(row)) for row in rows]
        except Exception as exc:
            logger.warning("Falling back to in-memory quota snapshots: %s", exc)
            return await cls._list_memory_snapshots(
                provider=provider_key, limit=limit, days=days, user_id=user_id
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
            
            # Retroactive cost estimation for old snapshots
            cost = _safe_float(snapshot.get("cost_usd"))
            if cost is None:
                usage = snapshot.get("usage") or {}
                provider_profile = cls.PROVIDERS.get(provider, {})
                unit = provider_profile.get("usage_unit")
                unit_usage = _safe_float(usage.get(unit))
                if unit_usage and provider in cls.PRICE_MAP:
                    cost = round(unit_usage * cls.PRICE_MAP[provider], 6)
            
            rollup["cost_usd"] += cost or 0.0

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

        if (
            remaining_value is None
            and provider_profile.get("monthly_limit") is not None
        ):
            usage_unit = provider_profile.get("usage_unit")
            usage_totals = provider_rollup.get("usage") or {}
            usage_total = _safe_float(usage_totals.get(usage_unit))
            if usage_total is not None:
                remaining_value = max(
                    provider_profile["monthly_limit"] - usage_total, 0.0
                )
                remaining_limit = provider_profile["monthly_limit"]
                remaining_source = "tracked_usage"
                remaining_exact = False

        billing_type = provider_profile.get("billing_type") or "subscription"
        remaining_usd = None
        if billing_type == "pay_as_you_go":
            spend_limit = _safe_float(provider_profile.get("spend_limit_usd"))
            current_cost = _safe_float(provider_rollup.get("cost_usd")) or 0.0
            if spend_limit is not None:
                remaining_usd = max(spend_limit - current_cost, 0.0)

        return {
            "billing_type": billing_type,
            "remaining_usd": remaining_usd,
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
            "last_error": latest_snapshot.get("metadata", {}).get("error_message")
            if latest_snapshot.get("metadata", {}).get("status") == "error"
            else None,
            "last_error_type": latest_snapshot.get("metadata", {}).get("error_type")
            if latest_snapshot.get("metadata", {}).get("status") == "error"
            else None,
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

        if (provider_rollup.get("latest_snapshot") or {}).get("metadata", {}).get("status") == "error":
            return "critical"

        if provider_rollup.get("snapshot_count"):
            return "ok"

        return "configured"

    @classmethod
    async def get_summary(cls, days: int = 30, user_id: Optional[str] = None) -> Dict[str, Any]:
        await cls.refresh_live_provider_snapshots()
        # Use a high limit for all-time stats to ensure we don't miss project totals
        fetch_limit = 50000 if (days == 0 or days is None) else 1000
        snapshots = await cls.list_snapshots(limit=fetch_limit, days=days, user_id=user_id)
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
    async def get_provider_overview(cls, days: int = 30, user_id: Optional[str] = None) -> Dict[str, Any]:
        summary = await cls.get_summary(days=days, user_id=user_id)
        return {
            "time_period": summary["time_period"],
            "providers": summary["providers"],
            "total_cost_usd": summary["total_cost_usd"],
            "total_snapshots": summary["total_snapshots"],
        }

    @classmethod
    async def get_provider_detail(
        cls, provider: str, days: int = 30, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        provider_key = _normalize_provider(provider)
        summary = await cls.get_summary(days=days, user_id=user_id)
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
