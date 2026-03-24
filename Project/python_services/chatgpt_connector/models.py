"""
Pydantic models for the ChatGPT/OpenClaw connector surface.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class OAuthStartRequest(BaseModel):
    chatgpt_subject: str
    user_id: Optional[str] = None
    display_name: Optional[str] = None


class OAuthStartResponse(BaseModel):
    state: str
    authorization_url: str
    callback_url: str
    chatgpt_subject: str
    user_id: Optional[str] = None
    expires_at: datetime


class OAuthCallbackRequest(BaseModel):
    state: str
    chatgpt_subject: str
    user_id: str
    display_name: Optional[str] = None


class ConnectorSessionView(BaseModel):
    session_id: str
    user_id: str
    chatgpt_subject: str
    display_name: Optional[str] = None
    linked_at: datetime
    expires_at: datetime
    active: bool = True


class ConnectorSessionIssuedView(ConnectorSessionView):
    session_token: str


class ToolCallRequest(BaseModel):
    tool: Literal[
        "openclaw_execute_task",
        "openclaw_get_task_status",
        "openclaw_cancel_task",
    ]
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_token: Optional[str] = None


class ToolCallResponse(BaseModel):
    ok: bool
    tool: str
    session_id: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class ConnectorManifest(BaseModel):
    service_name: str
    transport: str = "mcp"
    auth_mode: str = "oauth"
    session_header: str = "Authorization"
    oauth_start_path: str = "/oauth/start"
    oauth_callback_path: str = "/oauth/callback"
    tools: List[ToolDefinition] = Field(default_factory=list)
