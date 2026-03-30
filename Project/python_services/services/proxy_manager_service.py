"""
Proxy inventory and onboarding planning helpers.

This module keeps the proxy/account foundation intentionally small and safe:
it parses proxy inventory from env-like inputs, provides sticky leasing, and
builds region-aware onboarding plans for supported social platforms.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import parse_qsl, urlparse

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - depends on local env
    asyncpg = None

from services.region_service import RegionService
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

SUPPORTED_ONBOARDING_PLATFORMS = {"tiktok", "youtube", "facebook", "generic"}
DEFAULT_LEASE_MINUTES = 480
USER_NAMESPACE = uuid.UUID("2d9d5f55-2d26-4e34-b0bb-2d2d2f67eaa1")
SENSITIVE_RESPONSE_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "oauth_token",
    "password",
    "raw",
    "refresh_token",
    "secret",
    "token",
    "username",
}


def _redact_secret_value(value: Any) -> str:
    return "[redacted]"


def _redact_sensitive_response_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in SENSITIVE_RESPONSE_KEYS:
                redacted[key] = _redact_secret_value(item)
            else:
                redacted[key] = _redact_sensitive_response_data(item)
        return redacted

    if isinstance(value, list):
        return [_redact_sensitive_response_data(item) for item in value]

    return value


@dataclass
class ProxyRecord:
    id: str
    raw: str
    server: str
    host: str
    port: int
    scheme: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    label: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(
        self,
        *,
        include_credentials: bool = False,
        include_raw: bool = False,
    ) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "server": self.server,
            "host": self.host,
            "port": self.port,
            "scheme": self.scheme,
            "country_code": self.country_code,
            "region": self.region,
            "timezone": self.timezone,
            "label": self.label,
            "source": self.source,
            "metadata": dict(self.metadata),
            "requires_auth": bool(self.username or self.password),
        }
        if include_raw:
            payload["raw"] = self.raw
        if include_credentials:
            payload["username"] = self.username
            payload["password"] = self.password
        return payload

    def proxy_payload(self, *, include_credentials: bool = False) -> Dict[str, Any]:
        payload = {"server": self.server}
        if include_credentials and self.username:
            payload["username"] = self.username
        if include_credentials and self.password:
            payload["password"] = self.password
        if not include_credentials:
            payload["requires_auth"] = bool(self.username or self.password)
        return payload


@dataclass
class ProxyLease:
    lease_id: str
    account_key: str
    platform: str
    proxy: ProxyRecord
    leased_at: datetime
    expires_at: datetime
    sticky: bool = True

    def is_active(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return now < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "account_key": self.account_key,
            "platform": self.platform,
            "proxy": self.proxy.proxy_payload(),
            "proxy_details": self.proxy.to_dict(),
            "leased_at": self.leased_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "sticky": self.sticky,
        }


class ProxyManagerService:
    _inventory: List[ProxyRecord] = []
    _leases: Dict[str, ProxyLease] = {}
    _executions: Dict[str, Dict[str, Any]] = {}
    _db_pool: Optional[Any] = None
    _db_lock = asyncio.Lock()
    _lock = asyncio.Lock()

    @classmethod
    def reset_state(cls) -> None:
        cls._inventory = []
        cls._leases = {}
        cls._executions = {}

    @classmethod
    def supported_platforms(cls) -> List[str]:
        return sorted(SUPPORTED_ONBOARDING_PLATFORMS)

    @classmethod
    def _split_inventory_blob(cls, blob: str) -> List[str]:
        entries: List[str] = []
        for chunk in blob.replace("\r", "\n").replace(";", "\n").split("\n"):
            for token in chunk.split(","):
                token = token.strip()
                if token:
                    entries.append(token)
        return entries

    @classmethod
    def _inventory_sources_from_env(
        cls, environ: Optional[Mapping[str, str]] = None
    ) -> List[str]:
        env = environ or os.environ
        if env.get("PROXY_INVENTORY"):
            return cls._split_inventory_blob(env["PROXY_INVENTORY"])

        indexed = [
            env.get(f"PROXY_{index}")
            for index in range(1, 100)
            if env.get(f"PROXY_{index}")
        ]
        if indexed:
            return indexed

        proxy_server = env.get("PROXY_SERVER")
        username = env.get("IPROYAL_USERNAME")
        password = env.get("IPROYAL_PASSWORD")
        if proxy_server and username and password:
            normalized_server = proxy_server
            if "://" not in normalized_server:
                normalized_server = f"http://{normalized_server}"
            parsed = urlparse(normalized_server)
            auth_server = f"http://{username}:{password}@{parsed.hostname}:{parsed.port}"
            return [f"{auth_server}|source=iproyal|label=iproxy"]

        iproyal_host = env.get("IPROYAL_PROXY_HOST")
        iproyal_port = env.get("IPROYAL_PROXY_PORT")
        if iproyal_host and iproyal_port and username and password:
            return [
                (
                    f"http://{username}:{password}"
                    f"@{iproyal_host}:{iproyal_port}|source=iproyal"
                )
            ]

        return []

    @classmethod
    def _parse_proxy_entry(
        cls,
        raw_entry: str,
        index: int = 0,
        source: Optional[str] = None,
        fallback_username: Optional[str] = None,
        fallback_password: Optional[str] = None,
    ) -> ProxyRecord:
        entry = raw_entry.strip()
        metadata: Dict[str, Any] = {}

        if "|" in entry:
            proxy_text, *metadata_parts = entry.split("|")
            entry = proxy_text.strip()
            for item in metadata_parts:
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                metadata[key.strip().lower()] = value.strip()

        if "://" not in entry:
            entry = f"http://{entry}"

        parsed = urlparse(entry)
        if not parsed.hostname or not parsed.port:
            raise ValueError(f"Invalid proxy entry: {raw_entry}")

        label = metadata.get("label") or f"proxy-{index + 1}"
        country_code = metadata.get("country_code") or metadata.get("country")
        if isinstance(country_code, str):
            country_code = country_code.upper()

        region = metadata.get("region")
        timezone_name = metadata.get("timezone")
        scheme = parsed.scheme or "http"
        server = f"{scheme}://{parsed.hostname}:{parsed.port}"
        username = parsed.username or fallback_username
        password = parsed.password or fallback_password

        return ProxyRecord(
            id=label,
            raw=raw_entry.strip(),
            server=server,
            host=parsed.hostname,
            port=parsed.port,
            scheme=scheme,
            username=username,
            password=password,
            country_code=country_code,
            region=region,
            timezone=timezone_name,
            label=label,
            source=source,
            metadata=metadata,
        )

    @classmethod
    def refresh_inventory(
        cls, raw_sources: Optional[Iterable[str]] = None, environ: Optional[Mapping[str, str]] = None
    ) -> List[ProxyRecord]:
        env = environ or os.environ
        sources = list(raw_sources) if raw_sources is not None else cls._inventory_sources_from_env(environ=env)
        inventory: List[ProxyRecord] = []
        seen: set[tuple[str, Optional[str], Optional[str]]] = set()
        fallback_username = env.get("IPROYAL_USERNAME")
        fallback_password = env.get("IPROYAL_PASSWORD")

        for index, raw_entry in enumerate(sources):
            proxy = cls._parse_proxy_entry(
                raw_entry,
                index=index,
                source="env",
                fallback_username=fallback_username,
                fallback_password=fallback_password,
            )
            dedupe_key = (proxy.server, proxy.username, proxy.password)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            inventory.append(proxy)

        cls._inventory = inventory
        logger.info("Loaded %s proxy entries", len(inventory))
        return inventory

    @classmethod
    def ensure_inventory(cls) -> List[ProxyRecord]:
        if not cls._inventory:
            return cls.refresh_inventory()
        return cls._inventory

    @classmethod
    def list_inventory(cls) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in cls.ensure_inventory()]

    @classmethod
    async def _active_leases(cls) -> Dict[str, ProxyLease]:
        now = datetime.now(timezone.utc)
        active: Dict[str, ProxyLease] = {}
        for account_key, lease in list(cls._leases.items()):
            if lease.is_active(now):
                active[account_key] = lease
            else:
                cls._leases.pop(account_key, None)
        return active

    @classmethod
    def _region_matches(
        cls, proxy: ProxyRecord, region_code: Optional[str], region_name: Optional[str]
    ) -> bool:
        if not region_code and not region_name:
            return True

        if region_code:
            candidate = region_code.upper()
            if proxy.country_code and proxy.country_code.upper() == candidate:
                return True
            if proxy.metadata.get("country_code", "").upper() == candidate:
                return True

        if region_name:
            candidate = region_name.lower()
            if proxy.region and proxy.region.lower() == candidate:
                return True
            if str(proxy.metadata.get("region", "")).lower() == candidate:
                return True

        return False

    @classmethod
    def _select_proxy(
        cls,
        account_key: str,
        platform: str,
        region_code: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> ProxyRecord:
        inventory = cls.ensure_inventory()
        active_leases = cls._leases

        eligible = [
            proxy
            for proxy in inventory
            if not any(lease.proxy.id == proxy.id and lease.is_active() for lease in active_leases.values())
        ]
        if not eligible:
            eligible = list(inventory)

        region_filtered = [
            proxy for proxy in eligible if cls._region_matches(proxy, region_code, region_name)
        ]
        if region_filtered:
            eligible = region_filtered

        if not eligible:
            raise RuntimeError("No proxy inventory available")

        seed = f"{account_key}:{platform}:{region_code or ''}:{region_name or ''}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(eligible)
        return eligible[index]

    @classmethod
    async def lease_proxy(
        cls,
        account_key: str,
        platform: str = "generic",
        region_code: Optional[str] = None,
        region_name: Optional[str] = None,
        sticky: bool = True,
        lease_minutes: int = DEFAULT_LEASE_MINUTES,
    ) -> Dict[str, Any]:
        if not account_key:
            raise ValueError("account_key is required")

        platform = cls.normalize_platform(platform)
        async with cls._lock:
            cls.ensure_inventory()
            now = datetime.now(timezone.utc)
            existing = cls._leases.get(account_key)
            if sticky and existing and existing.is_active(now):
                return existing.to_dict()

            proxy = cls._select_proxy(
                account_key=account_key,
                platform=platform,
                region_code=region_code,
                region_name=region_name,
            )

            lease = ProxyLease(
                lease_id=str(uuid.uuid4()),
                account_key=account_key,
                platform=platform,
                proxy=proxy,
                leased_at=now,
                expires_at=now + timedelta(minutes=lease_minutes),
                sticky=sticky,
            )
            cls._leases[account_key] = lease
            return lease.to_dict()

    @classmethod
    async def release_proxy(cls, account_key: str) -> Dict[str, Any]:
        async with cls._lock:
            lease = cls._leases.pop(account_key, None)
            if not lease:
                return {"released": False, "account_key": account_key}

            return {
                "released": True,
                "account_key": account_key,
                "lease_id": lease.lease_id,
                "proxy": lease.proxy.proxy_payload(),
            }

    @classmethod
    def normalize_platform(cls, platform: str) -> str:
        normalized = (platform or "").strip().lower()
        if normalized not in SUPPORTED_ONBOARDING_PLATFORMS:
            raise ValueError(
                f"Unsupported platform: {platform}. Supported platforms: "
                + ", ".join(sorted(SUPPORTED_ONBOARDING_PLATFORMS))
            )
        return normalized

    @classmethod
    def onboarding_steps(cls, platform: str) -> List[str]:
        platform = cls.normalize_platform(platform)
        step_map = {
            "tiktok": [
                "prepare account identity and profile assets",
                "open a mobile-shaped browser session with sticky proxy",
                "fill profile basics and region-local metadata",
                "queue manual review or verification inputs if required",
            ],
            "youtube": [
                "prepare brand or creator account identity",
                "open a desktop browser session with sticky proxy",
                "configure channel basics and profile branding",
                "queue Google account linking and review inputs if required",
            ],
            "facebook": [
                "prepare profile or page identity",
                "open a desktop browser session with sticky proxy",
                "configure locale-aware profile fields",
                "queue review and confirmation inputs if required",
            ],
        }
        return step_map[platform]

    @classmethod
    async def build_onboarding_plan(
        cls,
        account_key: str,
        platform: str,
        persona_config: Optional[Dict[str, Any]] = None,
        region_code: Optional[str] = None,
        region_name: Optional[str] = None,
        proxy_sources: Optional[Iterable[str]] = None,
        sticky: bool = True,
    ) -> Dict[str, Any]:
        persona_config = persona_config or {}
        platform = cls.normalize_platform(platform)

        if proxy_sources is not None:
            cls.refresh_inventory(proxy_sources)
        else:
            cls.ensure_inventory()

        requested_region_code = (
            region_code
            or persona_config.get("country_code")
            or persona_config.get("region_code")
            or persona_config.get("countryCode")
        )
        requested_region_name = region_name or persona_config.get("region")

        region_service = RegionService()
        region_info = await region_service.build_region_profile(
            country_code_override=requested_region_code
        )
        if requested_region_name and not region_info.get("region"):
            region_info["region"] = requested_region_name

        lease = await cls.lease_proxy(
            account_key=account_key,
            platform=platform,
            region_code=requested_region_code,
            region_name=requested_region_name,
            sticky=sticky,
        )
        browser_settings = region_service.build_browser_context_settings(
            region_info=region_info,
            platform=platform,
        )
        platform_policy = cls._platform_policy(platform)
        profile_name = f"{cls._sanitize_segment(platform)}/{cls._sanitize_segment(account_key)}"

        return {
            "account_key": account_key,
            "platform": platform,
            "status": "planned",
            "mode": "proxy_onboarding",
            "account_type": platform_policy["account_type"],
            "automation_scope": platform_policy["automation_scope"],
            "bootstrap_mode": platform_policy["bootstrap_mode"],
            "conservative": platform_policy["conservative"],
            "region": region_info,
            "proxy_lease": lease,
            "browser_context": browser_settings,
            "browser_profile": {
                "profile_name": profile_name,
                "storage_state_path": f"/app/browser_profiles/{profile_name}/storage_state.json",
            },
            "persona": persona_config,
            "steps": cls.onboarding_steps(platform),
            "platform_policy": platform_policy,
            "warnings": [
                "This plan prepares a region-aware onboarding session. Actual platform account creation flows still need platform-specific automation.",
            ],
        }

    @classmethod
    async def execute_onboarding(
        cls,
        account_key: str,
        platform: str,
        persona_config: Optional[Dict[str, Any]] = None,
        region_code: Optional[str] = None,
        region_name: Optional[str] = None,
        proxy_sources: Optional[Iterable[str]] = None,
        sticky: bool = True,
    ) -> Dict[str, Any]:
        plan = await cls.build_onboarding_plan(
            account_key=account_key,
            platform=platform,
            persona_config=persona_config,
            region_code=region_code,
            region_name=region_name,
            proxy_sources=proxy_sources,
            sticky=sticky,
        )
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        execution = {
            "execution_id": execution_id,
            "account_key": account_key,
            "platform": plan["platform"],
            "status": "prepared",
            "created_at": now,
            "updated_at": now,
            "plan": plan,
        }
        cls._executions[execution_id] = execution
        return execution

    @classmethod
    def get_execution(cls, execution_id: str) -> Optional[Dict[str, Any]]:
        execution = cls._executions.get(execution_id)
        if not execution:
            return None
        return dict(execution)

    @classmethod
    def get_account_state(cls, account_key: str) -> Dict[str, Any]:
        lease = cls._leases.get(account_key)
        executions = [
            execution
            for execution in cls._executions.values()
            if execution["account_key"] == account_key
        ]
        return {
            "account_key": account_key,
            "lease": lease.to_dict() if lease else None,
            "executions": executions,
        }

    @classmethod
    def list_state(cls) -> Dict[str, Any]:
        return {
            "inventory": cls.list_inventory(),
            "leases": [lease.to_dict() for lease in cls._leases.values()],
            "executions": list(cls._executions.values()),
        }

    @classmethod
    async def _get_db_pool(cls) -> Any:
        return await DatabaseService.get_pool()

    @classmethod
    async def close_db_pool(cls) -> None:
        return None

    @classmethod
    def _resolve_owner_uuid(cls, owner_key: str) -> uuid.UUID:
        try:
            return uuid.UUID(str(owner_key))
        except (TypeError, ValueError):
            return uuid.uuid5(USER_NAMESPACE, str(owner_key))

    @classmethod
    async def _ensure_user(cls, conn: Any, owner_key: str) -> uuid.UUID:
        owner_uuid = cls._resolve_owner_uuid(owner_key)
        synthetic_email = f"{owner_uuid.hex}@local.proxy-registry.invalid"
        display_name = str(owner_key)[:255]
        await conn.execute(
            """
            INSERT INTO public.users (id, email, name)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET name = COALESCE(public.users.name, EXCLUDED.name)
            """,
            owner_uuid,
            synthetic_email,
            display_name,
        )
        return owner_uuid

    @classmethod
    def _platform_policy(cls, platform: str) -> Dict[str, Any]:
        platform = cls.normalize_platform(platform)
        if platform == "youtube":
            return {
                "account_type": "primary_oauth",
                "automation_scope": "oauth_link",
                "bootstrap_mode": "human_assisted",
                "conservative": True,
                "notes": [
                    "Keep YouTube to a primary OAuth linking flow in v1.",
                    "Avoid autonomous signup until the platform-specific policy is approved.",
                ],
            }

        return {
            "account_type": "proxy_bootstrap",
            "automation_scope": "browser_session",
            "bootstrap_mode": "human_assisted",
            "conservative": False,
            "notes": [
                "Use a sticky proxy and region-aware browser session.",
                "Keep final confirmation human-assisted for the first v1 flow.",
            ],
        }

    @staticmethod
    def _sanitize_segment(value: str) -> str:
        cleaned = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in str(value)
        )
        return cleaned.strip("_") or "account"

    @classmethod
    async def register_account_record(
        cls,
        owner_key: str,
        platform: str,
        account_key: str,
        plan: Dict[str, Any],
        status: str = "prepared",
        is_primary: bool = False,
        oauth_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Persist a registry row in public.social_accounts using the existing schema.
        """
        if asyncpg is None:
            return {
                "registry_persisted": False,
                "reason": "asyncpg is not installed",
                "owner_key": owner_key,
                "platform": platform,
                "account_key": account_key,
                "status": status,
                "is_primary": is_primary,
                "plan": plan,
            }

        pool = await cls._get_db_pool()
        owner_uuid = cls._resolve_owner_uuid(owner_key)
        platform = cls.normalize_platform(platform)
        account_name = (
            plan.get("persona", {}).get("name")
            or plan.get("persona", {}).get("handle")
            or account_key
        )
        account_handle = (
            plan.get("persona", {}).get("handle")
            or cls._sanitize_segment(account_key).lower()
        )
        registry_payload = {
            "account_key": account_key,
            "platform": platform,
            "status": status,
            "account_type": cls._platform_policy(platform)["account_type"],
            "bootstrap_mode": cls._platform_policy(platform)["bootstrap_mode"],
            "proxy_lease": plan.get("proxy_lease"),
            "browser_profile": plan.get("browser_profile"),
            "browser_context": plan.get("browser_context"),
            "region": plan.get("region"),
            "plan": plan,
        }

        async with pool.acquire() as conn:
            async with conn.transaction():
                await cls._ensure_user(conn, owner_key)
                existing = await conn.fetchrow(
                    """
                    SELECT id
                    FROM public.social_accounts
                    WHERE user_id = $1
                      AND platform = $2
                      AND account_handle = $3
                      AND is_primary = $4
                    LIMIT 1
                    """,
                    owner_uuid,
                    platform,
                    account_handle,
                    is_primary,
                )

                if existing:
                    await conn.execute(
                        """
                        UPDATE public.social_accounts
                        SET account_name = $1,
                            oauth_token = COALESCE($2, oauth_token),
                            proxy_config = $3::jsonb,
                            last_api_response = $4::jsonb,
                            is_active = TRUE,
                            last_used_at = NOW(),
                            updated_at = NOW()
                        WHERE id = $5
                        """,
                        account_name,
                        oauth_token,
                        cls._json_dumps(
                            {
                                "proxy_lease": registry_payload["proxy_lease"],
                                "browser_profile": registry_payload["browser_profile"],
                            }
                        ),
                        cls._json_dumps(_redact_sensitive_response_data(registry_payload)),
                        existing["id"],
                    )
                    registry_id = existing["id"]
                else:
                    registry_id = await conn.fetchval(
                        """
                        INSERT INTO public.social_accounts (
                            user_id,
                            platform,
                            account_name,
                            account_handle,
                            is_primary,
                            oauth_token,
                            proxy_config,
                            is_active,
                            last_used_at,
                            last_api_response
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, TRUE, NOW(), $8::jsonb)
                        RETURNING id
                        """,
                        owner_uuid,
                        platform,
                        account_name,
                        account_handle,
                        is_primary,
                        oauth_token,
                        cls._json_dumps(
                            {
                                "proxy_lease": registry_payload["proxy_lease"],
                                "browser_profile": registry_payload["browser_profile"],
                            }
                        ),
                        cls._json_dumps(_redact_sensitive_response_data(registry_payload)),
                    )

        return {
            "registry_persisted": True,
            "registry_id": str(registry_id),
            "owner_key": owner_key,
            "platform": platform,
            "account_key": account_key,
            "status": status,
            "is_primary": is_primary,
            "account_type": cls._platform_policy(platform)["account_type"],
            "plan": plan,
        }

    @staticmethod
    def _json_dumps(value: Any) -> str:
        import json

        return json.dumps(value or {}, sort_keys=True, default=str)

    @classmethod
    async def list_registry(
        cls, owner_key: Optional[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        if asyncpg is None:
            return {
                "registry_persisted": False,
                "accounts": [],
                "owner_key": owner_key,
                "limit": limit,
            }

        pool = await cls._get_db_pool()
        params: List[Any] = [limit]
        where_clause = ""
        if owner_key:
            owner_uuid = cls._resolve_owner_uuid(owner_key)
            params.insert(0, owner_uuid)
            where_clause = "WHERE user_id = $1"

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, user_id, platform, account_name, account_handle, is_primary,
                       oauth_token, proxy_config, is_active, last_used_at,
                       last_api_response, warnings, ban_risk_level, account_health,
                       created_at, updated_at
                FROM public.social_accounts
                {where_clause}
                ORDER BY COALESCE(last_used_at, created_at) DESC
                LIMIT ${len(params)}
                """,
                *params,
            )

        accounts = []
        for row in rows:
            accounts.append(
                {
                    "id": str(row["id"]),
                    "user_id": str(row["user_id"]),
                    "platform": row["platform"],
                    "account_name": row["account_name"],
                    "account_handle": row["account_handle"],
                    "is_primary": row["is_primary"],
                    "oauth_token_present": bool(row["oauth_token"]),
                    "proxy_config": _redact_sensitive_response_data(
                        row["proxy_config"]
                    ),
                    "is_active": row["is_active"],
                    "last_used_at": (
                        row["last_used_at"].isoformat() if row["last_used_at"] else None
                    ),
                    "last_api_response": _redact_sensitive_response_data(
                        row["last_api_response"]
                    ),
                    "warnings": row["warnings"],
                    "ban_risk_level": row["ban_risk_level"],
                    "account_health": row["account_health"],
                    "created_at": (
                        row["created_at"].isoformat() if row["created_at"] else None
                    ),
                    "updated_at": (
                        row["updated_at"].isoformat() if row["updated_at"] else None
                    ),
                }
            )

        return {
            "registry_persisted": True,
            "accounts": accounts,
            "owner_key": owner_key,
            "limit": limit,
        }
