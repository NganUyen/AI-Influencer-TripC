"""
ChatGPT-facing OpenClaw connector scaffold.

This package is intentionally separate from the main FastAPI app so the
OpenClaw internal API-key integration can stay untouched while we add a
public MCP/OAuth-facing surface later.
"""

from .app import app, create_app
from .auth import ConnectorAuthService
from .models import (
    ConnectorManifest,
    ConnectorSessionView,
    OAuthCallbackRequest,
    OAuthStartRequest,
    OAuthStartResponse,
    ToolCallRequest,
    ToolCallResponse,
)
from .store import ConnectorLinkRecord, ConnectorLinkStore
from .tools import OpenClawToolRunner

__all__ = [
    "app",
    "create_app",
    "ConnectorAuthService",
    "ConnectorManifest",
    "ConnectorSessionView",
    "OAuthCallbackRequest",
    "OAuthStartRequest",
    "OAuthStartResponse",
    "ToolCallRequest",
    "ToolCallResponse",
    "ConnectorLinkRecord",
    "ConnectorLinkStore",
    "OpenClawToolRunner",
]
