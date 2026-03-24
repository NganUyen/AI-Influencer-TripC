"""
OAuth-style session and identity-link helpers for the connector surface.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import quote, urlparse
from uuid import uuid4

from .models import ConnectorSessionIssuedView, ConnectorSessionView, OAuthStartResponse
from .store import ConnectorLinkStore


PLACEHOLDER_CONNECTOR_SECRETS = {
    "change-this-connector-secret",
    "dev-connector-secret",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _json_dumps(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _json_loads(raw: bytes) -> Dict[str, Any]:
    return json.loads(raw.decode("utf-8"))


def _is_local_public_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", ""}


def _env_flag(name: str) -> bool:
    value = os.getenv(name)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class IdentityLink:
    chatgpt_subject: str
    user_id: str
    display_name: Optional[str]
    linked_at: datetime
    last_used_at: datetime
    session_id: str


@dataclass
class OAuthStateRecord:
    state: str
    chatgpt_subject: str
    user_id: Optional[str]
    display_name: Optional[str]
    return_url: str
    expires_at: datetime


@dataclass
class ConnectorSession:
    session_id: str
    session_token: str
    user_id: str
    chatgpt_subject: str
    display_name: Optional[str]
    linked_at: datetime
    expires_at: datetime
    active: bool = True

    def to_view(self) -> ConnectorSessionView:
        return ConnectorSessionView(
            session_id=self.session_id,
            user_id=self.user_id,
            chatgpt_subject=self.chatgpt_subject,
            display_name=self.display_name,
            linked_at=self.linked_at,
            expires_at=self.expires_at,
            active=self.active,
        )

    def to_issued_view(self) -> ConnectorSessionIssuedView:
        return ConnectorSessionIssuedView(
            session_id=self.session_id,
            session_token=self.session_token,
            user_id=self.user_id,
            chatgpt_subject=self.chatgpt_subject,
            display_name=self.display_name,
            linked_at=self.linked_at,
            expires_at=self.expires_at,
            active=self.active,
        )


class ConnectorAuthService:
    def __init__(
        self,
        public_url: Optional[str] = None,
        secret: Optional[str] = None,
        session_ttl_minutes: int = 720,
        state_ttl_minutes: int = 30,
        persist_links: bool = True,
        db_url: Optional[str] = None,
    ) -> None:
        self.public_url = (public_url or os.getenv("CHATGPT_CONNECTOR_PUBLIC_URL") or "http://localhost:8010").rstrip("/")
        self.secret = secret or os.getenv("CHATGPT_CONNECTOR_SESSION_SECRET") or "dev-connector-secret"
        environment = (os.getenv("ENVIRONMENT") or "development").strip().lower()
        debug = (os.getenv("DEBUG") or "true").strip().lower()
        self.is_production_like = (
            environment in {"production", "staging"}
            or debug in {"false", "0", "no"}
            or not _is_local_public_url(self.public_url)
        )
        self.allow_insecure_self_issued_oauth = (
            not self.is_production_like
            or _env_flag("CHATGPT_CONNECTOR_ALLOW_INSECURE_SELF_ISSUED_OAUTH")
        )
        if self.is_production_like and self.secret in PLACEHOLDER_CONNECTOR_SECRETS:
            raise ValueError(
                "CHATGPT_CONNECTOR_SESSION_SECRET must be set to a non-default value"
            )
        self.session_ttl = timedelta(minutes=session_ttl_minutes)
        self.state_ttl = timedelta(minutes=state_ttl_minutes)
        self._lock = asyncio.Lock()
        self._states: Dict[str, OAuthStateRecord] = {}
        self._sessions_by_id: Dict[str, ConnectorSession] = {}
        self._sessions_by_token: Dict[str, str] = {}
        self._links_by_subject: Dict[str, IdentityLink] = {}
        self._persist_links = persist_links
        self._link_store = ConnectorLinkStore(db_url=db_url, enabled=persist_links)

    def _ensure_oauth_bootstrap_allowed(self) -> None:
        if self.allow_insecure_self_issued_oauth:
            return
        raise PermissionError(
            "Connector OAuth bootstrap is disabled until a real external identity flow is configured"
        )

    def _sign(self, payload: Dict[str, Any]) -> str:
        body = _json_dumps(payload)
        signature = hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).digest()
        return f"{_b64url_encode(body)}.{_b64url_encode(signature)}"

    def _unsign(self, token: str) -> Dict[str, Any]:
        body_part, signature_part = token.split(".", 1)
        body = _b64url_decode(body_part)
        expected = hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url_decode(signature_part)):
            raise ValueError("Invalid connector token signature")
        payload = _json_loads(body)
        expires_at = payload.get("expires_at")
        if expires_at and _utcnow() > datetime.fromisoformat(expires_at):
            raise ValueError("Connector token expired")
        return payload

    def _issue_state(self, chatgpt_subject: str, user_id: Optional[str], display_name: Optional[str], return_url: str) -> OAuthStateRecord:
        now = _utcnow()
        payload = {
            "kind": "oauth_state",
            "nonce": uuid4().hex,
            "chatgpt_subject": chatgpt_subject,
            "user_id": user_id,
            "display_name": display_name,
            "return_url": return_url,
            "issued_at": now.isoformat(),
            "expires_at": (now + self.state_ttl).isoformat(),
        }
        return OAuthStateRecord(
            state=self._sign(payload),
            chatgpt_subject=chatgpt_subject,
            user_id=user_id,
            display_name=display_name,
            return_url=return_url,
            expires_at=now + self.state_ttl,
        )

    def _issue_session(self, chatgpt_subject: str, user_id: str, display_name: Optional[str]) -> ConnectorSession:
        now = _utcnow()
        session_id = f"sess_{uuid4().hex}"
        expires_at = now + self.session_ttl
        token_payload = {
            "kind": "connector_session",
            "session_id": session_id,
            "chatgpt_subject": chatgpt_subject,
            "user_id": user_id,
            "display_name": display_name,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "nonce": uuid4().hex,
        }
        session_token = self._sign(token_payload)
        session = ConnectorSession(
            session_id=session_id,
            session_token=session_token,
            user_id=user_id,
            chatgpt_subject=chatgpt_subject,
            display_name=display_name,
            linked_at=now,
            expires_at=expires_at,
        )
        self._sessions_by_id[session_id] = session
        self._sessions_by_token[session_token] = session_id
        self._links_by_subject[chatgpt_subject] = IdentityLink(
            chatgpt_subject=chatgpt_subject,
            user_id=user_id,
            display_name=display_name,
            linked_at=now,
            last_used_at=now,
            session_id=session_id,
        )
        return session

    async def begin_oauth(
        self,
        chatgpt_subject: str,
        user_id: Optional[str] = None,
        display_name: Optional[str] = None,
        return_url: Optional[str] = None,
    ) -> OAuthStartResponse:
        self._ensure_oauth_bootstrap_allowed()
        async with self._lock:
            return_url = return_url or f"{self.public_url}/oauth/callback"
            state = self._issue_state(chatgpt_subject, user_id, display_name, return_url)
            self._states[state.state] = state
            callback_url = f"{self.public_url}/oauth/callback?state={quote(state.state)}"
            return OAuthStartResponse(
                state=state.state,
                authorization_url=callback_url,
                callback_url=callback_url,
                chatgpt_subject=chatgpt_subject,
                user_id=user_id,
                expires_at=state.expires_at,
            )

    async def complete_oauth(
        self,
        state: str,
        chatgpt_subject: str,
        user_id: str,
        display_name: Optional[str] = None,
    ) -> ConnectorSessionIssuedView:
        self._ensure_oauth_bootstrap_allowed()
        payload = self._unsign(state)
        if payload.get("kind") != "oauth_state":
            raise ValueError("Unexpected OAuth state payload")
        async with self._lock:
            state_record = self._states.pop(state, None)
            if state_record is None:
                raise ValueError("Unknown or already-used OAuth state")
            if state_record.expires_at < _utcnow():
                raise ValueError("OAuth state expired")
            if state_record.chatgpt_subject != chatgpt_subject:
                raise ValueError("OAuth state does not match the supplied ChatGPT subject")
            if state_record.user_id and state_record.user_id != user_id:
                raise ValueError("OAuth state does not match the supplied user")

            session = self._issue_session(chatgpt_subject, user_id, display_name or payload.get("display_name"))
            if self._persist_links:
                await self._link_store.upsert_link(
                    chatgpt_subject=chatgpt_subject,
                    user_id=user_id,
                    display_name=display_name or payload.get("display_name"),
                    session_id=session.session_id,
                )
            return session.to_issued_view()

    async def resolve_session(self, session_token: str) -> ConnectorSessionView:
        async with self._lock:
            payload = self._unsign(session_token)
            if payload.get("kind") != "connector_session":
                raise ValueError("Unexpected session token payload")

            session_id = payload.get("session_id")
            session = self._sessions_by_id.get(session_id)
            if session is None or session.session_token != session_token:
                link = self._links_by_subject.get(payload.get("chatgpt_subject"))
                if link is None and self._persist_links:
                    record = await self._link_store.get_link(payload.get("chatgpt_subject"))
                    if record is not None and record.active:
                        link = IdentityLink(
                            chatgpt_subject=record.chatgpt_subject,
                            user_id=record.user_id,
                            display_name=record.display_name,
                            linked_at=record.linked_at,
                            last_used_at=record.last_used_at,
                            session_id=record.session_id,
                        )
                        self._links_by_subject[record.chatgpt_subject] = link

                if (
                    link is None
                    or link.user_id != payload.get("user_id")
                    or link.session_id != session_id
                ):
                    raise ValueError("Unknown connector session")

                session = ConnectorSession(
                    session_id=session_id,
                    session_token=session_token,
                    user_id=payload.get("user_id"),
                    chatgpt_subject=payload.get("chatgpt_subject"),
                    display_name=payload.get("display_name") or link.display_name,
                    linked_at=link.linked_at,
                    expires_at=datetime.fromisoformat(payload.get("expires_at")),
                )
                self._sessions_by_id[session_id] = session
                self._sessions_by_token[session_token] = session_id

            if _utcnow() > session.expires_at:
                session.active = False
                raise ValueError("Connector session expired")

            link = self._links_by_subject.get(session.chatgpt_subject)
            if link:
                link.last_used_at = _utcnow()
            if self._persist_links:
                await self._link_store.touch_link(session.chatgpt_subject, session.session_id)
            return session.to_view()

    async def get_session(self, session_id: str) -> Optional[ConnectorSessionView]:
        session = self._sessions_by_id.get(session_id)
        return session.to_view() if session else None

    async def get_link(self, chatgpt_subject: str) -> Optional[IdentityLink]:
        async with self._lock:
            link = self._links_by_subject.get(chatgpt_subject)
            if link:
                return link

            if not self._persist_links:
                return None

            record = await self._link_store.get_link(chatgpt_subject)
            if record is None:
                return None

            link = IdentityLink(
                chatgpt_subject=record.chatgpt_subject,
                user_id=record.user_id,
                display_name=record.display_name,
                linked_at=record.linked_at,
                last_used_at=record.last_used_at,
                session_id=record.session_id,
            )
            self._links_by_subject[chatgpt_subject] = link
            return link

    async def resolve_request_session(
        self,
        session_token: Optional[str] = None,
        authorization_header: Optional[str] = None,
    ) -> ConnectorSessionView:
        token = session_token
        if not token and authorization_header:
            if authorization_header.lower().startswith("bearer "):
                token = authorization_header.split(" ", 1)[1].strip()
            else:
                token = authorization_header.strip()
        if not token:
            raise ValueError("Missing connector session token")
        return await self.resolve_session(token)

    async def close(self) -> None:
        await self._link_store.close()
