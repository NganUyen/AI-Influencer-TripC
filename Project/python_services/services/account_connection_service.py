"""
Customer-owned OAuth account connection helpers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from uuid import uuid4

import httpx

from config.settings import settings
from services.customer_auth_service import CustomerSession
from services.customer_token_vault import CustomerTokenVault
from services.database_service import DatabaseService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _json_dumps(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_loads(payload: bytes) -> Dict[str, Any]:
    return json.loads(payload.decode("utf-8"))


@dataclass
class OAuthProviderConfig:
    platform: str
    authorize_url: str
    token_url: str
    profile_url: str
    client_id: Optional[str]
    client_secret: Optional[str]
    scopes: List[str]
    use_basic_auth: bool = False
    profile_fields: Optional[Dict[str, str]] = None


class OAuthConfigurationError(RuntimeError):
    pass


class OAuthExchangeError(RuntimeError):
    pass


class AccountConnectionService:
    STATE_TTL = timedelta(minutes=20)

    PROVIDERS: Dict[str, OAuthProviderConfig] = {
        "linkedin": OAuthProviderConfig(
            platform="linkedin",
            authorize_url="https://www.linkedin.com/oauth/v2/authorization",
            token_url="https://www.linkedin.com/oauth/v2/accessToken",
            profile_url="https://api.linkedin.com/v2/userinfo",
            client_id=None,
            client_secret=None,
            scopes=["openid", "profile", "email", "w_member_social"],
        ),
        "facebook": OAuthProviderConfig(
            platform="facebook",
            authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
            token_url="https://graph.facebook.com/v19.0/oauth/access_token",
            profile_url="https://graph.facebook.com/me?fields=id,name,email",
            client_id=None,
            client_secret=None,
            scopes=["pages_manage_posts", "pages_read_engagement", "public_profile", "email"],
        ),
        "twitter": OAuthProviderConfig(
            platform="twitter",
            authorize_url="https://twitter.com/i/oauth2/authorize",
            token_url="https://api.twitter.com/2/oauth2/token",
            profile_url="https://api.twitter.com/2/users/me?user.fields=profile_image_url,username",
            client_id=None,
            client_secret=None,
            scopes=["tweet.read", "tweet.write", "users.read", "offline.access"],
            use_basic_auth=True,
        ),
        "youtube": OAuthProviderConfig(
            platform="youtube",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            profile_url="https://www.googleapis.com/oauth2/v3/userinfo",
            client_id=None,
            client_secret=None,
            scopes=["openid", "email", "profile", "https://www.googleapis.com/auth/youtube.upload"],
        ),
    }

    @classmethod
    def _load_provider(cls, platform: str) -> OAuthProviderConfig:
        key = platform.strip().lower()
        if key not in cls.PROVIDERS:
            raise OAuthConfigurationError(f"Unsupported OAuth platform '{platform}'")

        provider = cls.PROVIDERS[key]
        client_id = getattr(settings, f"{key.upper()}_OAUTH_CLIENT_ID", None)
        client_secret = getattr(settings, f"{key.upper()}_OAUTH_CLIENT_SECRET", None)
        if not client_id or not client_secret:
            raise OAuthConfigurationError(
                f"{key.upper()} OAuth client credentials are not configured"
            )

        return OAuthProviderConfig(
            **{
                **provider.__dict__,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )

    @staticmethod
    def _callback_url(platform: str) -> str:
        base = (settings.BACKEND_PUBLIC_URL or "http://localhost:8000").rstrip("/")
        return f"{base}/api/customer/social-accounts/{platform}/oauth/callback"

    @staticmethod
    def _sign_state(payload: Dict[str, Any]) -> str:
        body = _json_dumps(payload)
        key = (settings.JWT_SECRET_KEY or settings.SUPABASE_SERVICE_ROLE_KEY).encode("utf-8")
        signature = hmac.new(key, body, hashlib.sha256).digest()
        return f"{_b64url_encode(body)}.{_b64url_encode(signature)}"

    @staticmethod
    def _unsign_state(token: str) -> Dict[str, Any]:
        body_part, signature_part = token.split(".", 1)
        body = _b64url_decode(body_part)
        signature = _b64url_decode(signature_part)
        key = (settings.JWT_SECRET_KEY or settings.SUPABASE_SERVICE_ROLE_KEY).encode("utf-8")
        expected = hmac.new(key, body, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise OAuthExchangeError("OAuth state signature is invalid")
        payload = _json_loads(body)
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if _utcnow() > expires_at:
            raise OAuthExchangeError("OAuth state has expired")
        return payload

    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        verifier = _b64url_encode(os.urandom(48))
        challenge = _b64url_encode(hashlib.sha256(verifier.encode("utf-8")).digest())
        return verifier, challenge

    @classmethod
    async def start_oauth(cls, session: CustomerSession, platform: str) -> Dict[str, Any]:
        provider = cls._load_provider(platform)
        verifier, challenge = cls._pkce_pair()
        state = cls._sign_state(
            {
                "user_id": session.user_id,
                "platform": provider.platform,
                "code_verifier": verifier,
                "issued_at": _utcnow().isoformat(),
                "expires_at": (_utcnow() + cls.STATE_TTL).isoformat(),
            }
        )

        params = {
            "client_id": provider.client_id,
            "redirect_uri": cls._callback_url(provider.platform),
            "response_type": "code",
            "scope": " ".join(provider.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if provider.platform == "youtube":
            params["access_type"] = "offline"
            params["prompt"] = "consent"

        return {
            "platform": provider.platform,
            "auth_url": f"{provider.authorize_url}?{urlencode(params)}",
        }

    @classmethod
    async def _exchange_code(
        cls,
        provider: OAuthProviderConfig,
        code: str,
        state_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        redirect_uri = cls._callback_url(provider.platform)
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code_verifier": state_payload["code_verifier"],
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if provider.use_basic_auth and provider.client_id and provider.client_secret:
            raw = f"{provider.client_id}:{provider.client_secret}".encode("utf-8")
            headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('ascii')}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(provider.token_url, data=body, headers=headers)
        if response.status_code >= 400:
            raise OAuthExchangeError(
                f"{provider.platform} token exchange failed with status {response.status_code}"
            )
        return response.json()

    @classmethod
    async def _fetch_profile(
        cls,
        provider: OAuthProviderConfig,
        access_token: str,
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(provider.profile_url, headers=headers)
        if response.status_code >= 400:
            raise OAuthExchangeError(
                f"{provider.platform} profile lookup failed with status {response.status_code}"
            )
        payload = response.json()
        if provider.platform == "twitter" and isinstance(payload.get("data"), dict):
            payload = payload["data"]
        return payload

    @classmethod
    async def complete_oauth(
        cls,
        platform: str,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        provider = cls._load_provider(platform)
        state_payload = cls._unsign_state(state)
        if state_payload.get("platform") != provider.platform:
            raise OAuthExchangeError("OAuth state does not match requested platform")

        token_payload = await cls._exchange_code(provider, code, state_payload)
        profile = await cls._fetch_profile(provider, token_payload["access_token"])

        provider_account_id = (
            profile.get("sub")
            or profile.get("id")
            or profile.get("user_id")
        )
        account_handle = (
            profile.get("preferred_username")
            or profile.get("username")
            or profile.get("email")
            or provider_account_id
        )
        display_name = (
            profile.get("name")
            or profile.get("given_name")
            or account_handle
        )
        scopes = str(token_payload.get("scope") or "").split()
        encrypted_bundle = CustomerTokenVault.seal(
            {
                "access_token": token_payload.get("access_token"),
                "refresh_token": token_payload.get("refresh_token"),
                "scope": token_payload.get("scope"),
                "token_type": token_payload.get("token_type"),
                "provider_profile": profile,
            }
        )
        expires_in = int(token_payload.get("expires_in") or 3600)
        token_expires_at = _utcnow() + timedelta(seconds=expires_in)
        token_ref = f"tok_{uuid4().hex}"

        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO public.social_accounts (
                    user_id,
                    platform,
                    account_name,
                    account_handle,
                    is_primary,
                    is_active,
                    connection_status,
                    provider_account_id,
                    display_name,
                    connection_method,
                    scopes,
                    token_ref,
                    encrypted_token_bundle,
                    token_expires_at,
                    last_sync_at,
                    last_error,
                    publish_capabilities,
                    oauth_token
                )
                VALUES (
                    $1::uuid, $2, $3, $4, TRUE, TRUE, 'connected', $5, $6, 'oauth', $7::text[],
                    $8, $9, $10, NOW(), NULL, $11::jsonb, NULL
                )
                ON CONFLICT (user_id, platform, account_handle, is_primary) DO UPDATE
                SET account_name = EXCLUDED.account_name,
                    provider_account_id = EXCLUDED.provider_account_id,
                    display_name = EXCLUDED.display_name,
                    connection_status = 'connected',
                    connection_method = 'oauth',
                    scopes = EXCLUDED.scopes,
                    token_ref = EXCLUDED.token_ref,
                    encrypted_token_bundle = EXCLUDED.encrypted_token_bundle,
                    token_expires_at = EXCLUDED.token_expires_at,
                    last_sync_at = NOW(),
                    last_error = NULL,
                    publish_capabilities = EXCLUDED.publish_capabilities,
                    is_active = TRUE,
                    updated_at = NOW()
                RETURNING *
                """,
                state_payload["user_id"],
                provider.platform,
                display_name,
                str(account_handle),
                str(provider_account_id or account_handle),
                str(display_name),
                scopes,
                token_ref,
                encrypted_bundle,
                token_expires_at,
                json.dumps(
                    {
                        "direct_publish": False,
                        "oauth_connected": True,
                        "platform": provider.platform,
                        "strategy": "postiz_fallback",
                    },
                    sort_keys=True,
                ),
            )

        return {
            "platform": provider.platform,
            "user_id": state_payload["user_id"],
            "social_account_id": str(row["id"]),
            "account_handle": row["account_handle"],
            "display_name": row["display_name"],
            "connection_status": row["connection_status"],
        }

    @classmethod
    async def list_accounts(cls, user_id: str) -> List[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, platform, account_name, account_handle, display_name,
                       provider_account_id, connection_status, connection_method, scopes,
                       token_ref, token_expires_at, last_sync_at, last_error, publish_capabilities,
                       is_active, created_at, updated_at
                FROM public.social_accounts
                WHERE user_id = $1::uuid
                ORDER BY updated_at DESC, created_at DESC
                """,
                user_id,
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
                    "display_name": row["display_name"],
                    "provider_account_id": row["provider_account_id"],
                    "connection_status": row["connection_status"],
                    "connection_method": row["connection_method"],
                    "scopes": row["scopes"] or [],
                    "token_ref": row["token_ref"],
                    "token_expires_at": row["token_expires_at"].isoformat()
                    if row["token_expires_at"]
                    else None,
                    "last_sync_at": row["last_sync_at"].isoformat()
                    if row["last_sync_at"]
                    else None,
                    "last_error": row["last_error"],
                    "publish_capabilities": row["publish_capabilities"] or {},
                    "is_active": row["is_active"],
                    "created_at": row["created_at"].isoformat()
                    if row["created_at"]
                    else None,
                    "updated_at": row["updated_at"].isoformat()
                    if row["updated_at"]
                    else None,
                }
            )
        return accounts

    @classmethod
    async def get_account_by_id(
        cls,
        social_account_id: str,
        *,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        query = """
            SELECT *
            FROM public.social_accounts
            WHERE id = $1::uuid
        """
        args: List[Any] = [social_account_id]
        if user_id:
            query += " AND user_id = $2::uuid"
            args.append(user_id)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)

        if row is None:
            return None
        return dict(row)

    @classmethod
    async def disconnect_account(cls, user_id: str, social_account_id: str) -> None:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.social_accounts
                SET connection_status = 'disconnected',
                    encrypted_token_bundle = NULL,
                    token_ref = NULL,
                    token_expires_at = NULL,
                    last_error = NULL,
                    is_active = FALSE,
                    updated_at = NOW()
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                social_account_id,
                user_id,
            )

    @classmethod
    async def get_connected_account(
        cls,
        user_id: str,
        platform: str,
    ) -> Optional[Dict[str, Any]]:
        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM public.social_accounts
                WHERE user_id = $1::uuid
                  AND platform = $2
                  AND connection_status = 'connected'
                  AND is_active = TRUE
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                user_id,
                platform,
            )
        if row is None:
            return None
        return dict(row)

    @classmethod
    async def upsert_browser_session_account(
        cls,
        *,
        user_id: str,
        platform: str,
        account_name: str,
        account_handle: str,
        display_name: Optional[str] = None,
        provider_account_id: Optional[str] = None,
        social_account_id: Optional[str] = None,
        encrypted_bundle_payload: Optional[Dict[str, Any]] = None,
        token_expires_at: Optional[datetime] = None,
        publish_capabilities: Optional[Dict[str, Any]] = None,
        proxy_config: Optional[Dict[str, Any]] = None,
        last_api_response: Optional[Dict[str, Any]] = None,
        is_primary: bool = True,
        is_active: bool = True,
        connection_status: str = "connected",
        connection_method: str = "browser_session",
        last_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        token_ref = None
        encrypted_bundle = None
        if encrypted_bundle_payload:
            encrypted_bundle = CustomerTokenVault.seal(encrypted_bundle_payload)
            token_ref = f"tok_{uuid4().hex}"

        publish_capabilities_json = json.dumps(
            publish_capabilities or {},
            sort_keys=True,
        )
        proxy_config_json = json.dumps(proxy_config or {}, sort_keys=True)
        last_api_response_json = json.dumps(last_api_response or {}, sort_keys=True)

        pool = await DatabaseService.get_pool()
        async with pool.acquire() as conn:
            if social_account_id:
                row = await conn.fetchrow(
                    """
                    UPDATE public.social_accounts
                    SET platform = $3,
                        account_name = $4,
                        account_handle = $5,
                        is_primary = $6,
                        is_active = $7,
                        connection_status = $8,
                        provider_account_id = COALESCE($9, provider_account_id),
                        display_name = COALESCE($10, display_name),
                        connection_method = $11,
                        token_ref = COALESCE($12, token_ref),
                        encrypted_token_bundle = COALESCE($13, encrypted_token_bundle),
                        token_expires_at = COALESCE($14, token_expires_at),
                        last_sync_at = CASE
                            WHEN $8 = 'connected' THEN NOW()
                            ELSE last_sync_at
                        END,
                        last_error = $15,
                        publish_capabilities = COALESCE(publish_capabilities, '{}'::jsonb) || $16::jsonb,
                        proxy_config = COALESCE(proxy_config, '{}'::jsonb) || $17::jsonb,
                        last_api_response = COALESCE(last_api_response, '{}'::jsonb) || $18::jsonb,
                        updated_at = NOW()
                    WHERE id = $1::uuid
                      AND user_id = $2::uuid
                    RETURNING *
                    """,
                    social_account_id,
                    user_id,
                    platform,
                    account_name,
                    account_handle,
                    is_primary,
                    is_active,
                    connection_status,
                    provider_account_id,
                    display_name,
                    connection_method,
                    token_ref,
                    encrypted_bundle,
                    token_expires_at,
                    last_error,
                    publish_capabilities_json,
                    proxy_config_json,
                    last_api_response_json,
                )
            else:
                row = await conn.fetchrow(
                    """
                    INSERT INTO public.social_accounts (
                        user_id,
                        platform,
                        account_name,
                        account_handle,
                        is_primary,
                        is_active,
                        connection_status,
                        provider_account_id,
                        display_name,
                        connection_method,
                        token_ref,
                        encrypted_token_bundle,
                        token_expires_at,
                        last_sync_at,
                        last_error,
                        publish_capabilities,
                        proxy_config,
                        last_api_response
                    )
                    VALUES (
                        $1::uuid,
                        $2,
                        $3,
                        $4,
                        $5,
                        $6,
                        $7,
                        $8,
                        $9,
                        $10,
                        $11,
                        $12,
                        $13,
                        CASE
                            WHEN $7 = 'connected' THEN NOW()
                            ELSE NULL
                        END,
                        $14,
                        $15::jsonb,
                        $16::jsonb,
                        $17::jsonb
                    )
                    ON CONFLICT (user_id, platform, account_handle, is_primary) DO UPDATE
                    SET account_name = EXCLUDED.account_name,
                        is_active = EXCLUDED.is_active,
                        connection_status = EXCLUDED.connection_status,
                        provider_account_id = COALESCE(EXCLUDED.provider_account_id, public.social_accounts.provider_account_id),
                        display_name = COALESCE(EXCLUDED.display_name, public.social_accounts.display_name),
                        connection_method = EXCLUDED.connection_method,
                        token_ref = COALESCE(EXCLUDED.token_ref, public.social_accounts.token_ref),
                        encrypted_token_bundle = COALESCE(EXCLUDED.encrypted_token_bundle, public.social_accounts.encrypted_token_bundle),
                        token_expires_at = COALESCE(EXCLUDED.token_expires_at, public.social_accounts.token_expires_at),
                        last_sync_at = CASE
                            WHEN EXCLUDED.connection_status = 'connected' THEN NOW()
                            ELSE public.social_accounts.last_sync_at
                        END,
                        last_error = EXCLUDED.last_error,
                        publish_capabilities = COALESCE(public.social_accounts.publish_capabilities, '{}'::jsonb) || EXCLUDED.publish_capabilities,
                        proxy_config = COALESCE(public.social_accounts.proxy_config, '{}'::jsonb) || EXCLUDED.proxy_config,
                        last_api_response = COALESCE(public.social_accounts.last_api_response, '{}'::jsonb) || EXCLUDED.last_api_response,
                        updated_at = NOW()
                    RETURNING *
                    """,
                    user_id,
                    platform,
                    account_name,
                    account_handle,
                    is_primary,
                    is_active,
                    connection_status,
                    provider_account_id,
                    display_name,
                    connection_method,
                    token_ref,
                    encrypted_bundle,
                    token_expires_at,
                    last_error,
                    publish_capabilities_json,
                    proxy_config_json,
                    last_api_response_json,
                )

        if row is None:
            raise RuntimeError("Failed to upsert browser session account")
        return dict(row)
