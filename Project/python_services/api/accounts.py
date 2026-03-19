"""
Accounts API Routes

Concrete planning and execution surface for proxy-driven account onboarding.
"""

import logging
from collections.abc import Iterable
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.security import require_internal_api_token
from services.proxy_manager_service import (
    ProxyManagerService,
    _redact_sensitive_response_data,
)

router = APIRouter(dependencies=[Depends(require_internal_api_token)])
logger = logging.getLogger(__name__)


def _resolve_account_key(platform: str, payload: Dict[str, Any]) -> str:
    persona = payload.get("persona_config") or {}
    account_key = (
        payload.get("account_key")
        or payload.get("handle")
        or payload.get("email")
        or persona.get("account_key")
        or persona.get("handle")
        or persona.get("email")
        or persona.get("name")
    )
    return str(account_key or f"{platform}-account")


def _normalize_proxy_sources(proxy_sources: Any) -> Optional[List[str]]:
    if proxy_sources is None:
        return None
    if isinstance(proxy_sources, str):
        return [proxy_sources]
    if isinstance(proxy_sources, Iterable):
        return [str(item) for item in proxy_sources if str(item).strip()]
    return [str(proxy_sources)]


def _build_onboarding_payload(platform: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    platform = ProxyManagerService.normalize_platform(platform)
    persona_config = payload.get("persona_config") or {}
    account_key = _resolve_account_key(platform, payload)

    return {
        "account_key": account_key,
        "platform": platform,
        "persona_config": persona_config,
        "region_code": (
            payload.get("region_code")
            or payload.get("country_code")
            or persona_config.get("region_code")
            or persona_config.get("country_code")
            or persona_config.get("countryCode")
        ),
        "region_name": payload.get("region_name") or persona_config.get("region"),
        "proxy_sources": _normalize_proxy_sources(
            payload.get("proxy_sources") or persona_config.get("proxy_sources")
        ),
        "sticky": bool(payload.get("sticky", True)),
    }


def _build_browser_profile(platform: str, account_key: str) -> Dict[str, str]:
    safe_platform = ProxyManagerService._sanitize_segment(platform)
    safe_account = ProxyManagerService._sanitize_segment(account_key)
    profile_name = f"{safe_platform}/{safe_account}"
    return {
        "profile_name": profile_name,
        "storage_state_path": f"/app/browser_profiles/{profile_name}/storage_state.json",
    }


@router.get("/proxies")
async def list_proxies() -> Dict[str, Any]:
    """Return proxy inventory and active leases."""
    try:
        return ProxyManagerService.list_state()
    except Exception as exc:
        logger.error("Failed to list proxies: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/proxies/refresh")
async def refresh_proxies(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reload proxy inventory from env-like inputs."""
    try:
        payload = payload or {}
        proxy_sources = _normalize_proxy_sources(payload.get("proxy_sources"))
        inventory = ProxyManagerService.refresh_inventory(proxy_sources)
        return {
            "status": "refreshed",
            "count": len(inventory),
            "inventory": [item.to_dict() for item in inventory],
        }
    except Exception as exc:
        logger.error("Failed to refresh proxies: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/proxies/lease")
async def lease_proxy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Lease a sticky proxy for an account key."""
    try:
        account_key = payload.get("account_key")
        if not account_key:
            raise HTTPException(status_code=400, detail="account_key is required")

        platform = payload.get("platform", "generic")
        lease = await ProxyManagerService.lease_proxy(
            account_key=str(account_key),
            platform=platform,
            region_code=payload.get("region_code"),
            region_name=payload.get("region_name"),
            sticky=bool(payload.get("sticky", True)),
        )
        return {"status": "leased", "lease": lease}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to lease proxy: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/onboarding/plan")
async def plan_onboarding(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a region-aware onboarding plan for TikTok, YouTube, or Facebook."""
    try:
        platform = payload.get("platform")
        if not platform:
            raise HTTPException(status_code=400, detail="platform is required")

        plan_input = _build_onboarding_payload(platform, payload)
        plan = await ProxyManagerService.build_onboarding_plan(**plan_input)
        plan["browser_profile"] = _build_browser_profile(
            plan["platform"], plan["account_key"]
        )
        return {"status": "planned", "plan": plan}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to build onboarding plan: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/onboarding/execute")
async def execute_onboarding(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Record an onboarding execution and return the prepared plan."""
    try:
        platform = payload.get("platform")
        if not platform:
            raise HTTPException(status_code=400, detail="platform is required")

        plan_input = _build_onboarding_payload(platform, payload)
        execution = await ProxyManagerService.execute_onboarding(**plan_input)
        execution["plan"]["browser_profile"] = _build_browser_profile(
            execution["platform"], execution["account_key"]
        )
        registry = await ProxyManagerService.register_account_record(
            owner_key=str(
                payload.get("owner_key")
                or payload.get("user_id")
                or execution["account_key"]
            ),
            platform=execution["platform"],
            account_key=execution["account_key"],
            plan=execution["plan"],
            status=execution["status"],
            is_primary=bool(payload.get("is_primary", False)),
            oauth_token=payload.get("oauth_token") or payload.get("access_token"),
        )
        return {
            "status": execution["status"],
            "execution": execution,
            "registry": registry,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to execute onboarding: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/onboarding/{execution_id}")
async def get_onboarding_execution(execution_id: str) -> Dict[str, Any]:
    """Fetch a stored onboarding execution."""
    execution = ProxyManagerService.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.get("/accounts/{account_key}")
async def get_account_state(account_key: str) -> Dict[str, Any]:
    """Return the current lease and onboarding history for an account key."""
    try:
        registry = await ProxyManagerService.list_registry(owner_key=account_key, limit=20)
        return {
            "account_key": account_key,
            "state": _redact_sensitive_response_data(
                ProxyManagerService.get_account_state(account_key)
            ),
            "registry": _redact_sensitive_response_data(registry),
        }
    except Exception as exc:
        logger.error("Failed to get account state: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/stealth/create")
async def create_stealth_account(platform: str, persona_config: Dict[str, Any]):
    """
    Backward-compatible alias that now prepares a concrete onboarding execution.
    """
    try:
        payload = {"platform": platform, "persona_config": persona_config}
        plan_input = _build_onboarding_payload(platform, payload)
        execution = await ProxyManagerService.execute_onboarding(**plan_input)
        execution["plan"]["browser_profile"] = _build_browser_profile(
            execution["platform"], execution["account_key"]
        )
        registry = await ProxyManagerService.register_account_record(
            owner_key=str(persona_config.get("owner_key") or persona_config.get("user_id") or execution["account_key"]),
            platform=execution["platform"],
            account_key=execution["account_key"],
            plan=execution["plan"],
            status=execution["status"],
            is_primary=bool(persona_config.get("is_primary", False)),
            oauth_token=persona_config.get("oauth_token") or persona_config.get("access_token"),
        )
        return {"execution": execution, "registry": registry}
    except Exception as exc:
        logger.error("Failed to create onboarding execution: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stealth/{account_id}")
async def get_account_status(account_id: str):
    """Backward-compatible alias that returns the account state snapshot."""
    try:
        registry = await ProxyManagerService.list_registry(owner_key=account_id, limit=20)
        return {
            "account_key": account_id,
            "state": _redact_sensitive_response_data(
                ProxyManagerService.get_account_state(account_id)
            ),
            "registry": _redact_sensitive_response_data(registry),
        }
    except Exception as exc:
        logger.error("Failed to get account state: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/connect/{platform}")
async def connect_platform_account(platform: str, credentials: Dict[str, Any]):
    """
    Prepare a platform account connection/onboarding workflow.
    """
    try:
        payload = {
            "platform": platform,
            "persona_config": credentials,
            "account_key": credentials.get("account_key")
            or credentials.get("handle")
            or credentials.get("email")
            or credentials.get("username")
            or credentials.get("name"),
            "region_code": credentials.get("region_code")
            or credentials.get("country_code")
            or credentials.get("countryCode"),
            "region_name": credentials.get("region"),
            "proxy_sources": credentials.get("proxy_sources"),
            "sticky": credentials.get("sticky", True),
        }
        execution = await ProxyManagerService.execute_onboarding(
            **_build_onboarding_payload(platform, payload)
        )
        execution["plan"]["browser_profile"] = _build_browser_profile(
            execution["platform"], execution["account_key"]
        )
        registry = await ProxyManagerService.register_account_record(
            owner_key=str(
                credentials.get("owner_key")
                or credentials.get("user_id")
                or execution["account_key"]
            ),
            platform=execution["platform"],
            account_key=execution["account_key"],
            plan=execution["plan"],
            status="connected" if credentials.get("oauth_token") or credentials.get("access_token") else execution["status"],
            is_primary=True,
            oauth_token=credentials.get("oauth_token") or credentials.get("access_token"),
        )
        return {
            "platform": ProxyManagerService.normalize_platform(platform),
            "status": registry["status"],
            "execution_id": execution["execution_id"],
            "account_key": execution["account_key"],
            "plan": execution["plan"],
            "registry": registry,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to connect platform account: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/list")
async def list_connected_accounts():
    """List proxy inventory, active leases, and onboarding executions."""
    try:
        registry = await ProxyManagerService.list_registry(limit=100)
        state = ProxyManagerService.list_state()
        return {
            "registry": _redact_sensitive_response_data(registry),
            "inventory": _redact_sensitive_response_data(state["inventory"]),
            "leases": _redact_sensitive_response_data(state["leases"]),
            "executions": _redact_sensitive_response_data(state["executions"]),
        }
    except Exception as exc:
        logger.error("Failed to list account state: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
