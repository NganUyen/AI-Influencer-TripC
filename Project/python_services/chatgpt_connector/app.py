"""
FastAPI surface for the ChatGPT-facing OpenClaw connector.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import logging
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .auth import ConnectorAuthService
from .models import (
    ConnectorManifest,
    ConnectorSessionIssuedView,
    ConnectorSessionView,
    OAuthCallbackRequest,
    OAuthStartRequest,
    ToolDefinition,
    ToolCallRequest,
    ToolCallResponse,
)
from .tools import OpenClawToolRunner

logger = logging.getLogger(__name__)


def _root_path_from_public_url(value: str | None) -> str:
    if not value:
        return ""
    path = (urlparse(value).path or "").rstrip("/")
    return "" if path in {"", "/"} else path


def create_app(
    auth_service: ConnectorAuthService | None = None,
    tool_runner: OpenClawToolRunner | None = None,
) -> FastAPI:
    auth_service = auth_service or ConnectorAuthService(persist_links=True)
    tool_runner = tool_runner or OpenClawToolRunner()
    connector_root_path = _root_path_from_public_url(auth_service.public_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await auth_service.close()

    app_kwargs = {}
    if connector_root_path:
        app_kwargs["root_path"] = connector_root_path
        app_kwargs["servers"] = [{"url": connector_root_path}]

    app = FastAPI(
        title="ChatGPT OpenClaw Connector",
        description="Separate ChatGPT-facing connector surface for OpenClaw",
        version="0.1.0",
        lifespan=lifespan,
        **app_kwargs,
    )
    app.state.connector_auth = auth_service
    app.state.connector_tools = tool_runner

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/oauth/") or request.url.path.startswith("/sessions/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def sanitize_http_exception(_request: Request, exc: HTTPException):
        if exc.status_code >= 500:
            logger.warning("Sanitizing connector %s response: %s", exc.status_code, exc.detail)
            detail = "Service unavailable" if exc.status_code == 503 else "Internal server error"
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": detail},
                headers=exc.headers,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        logger.exception(
            "Unhandled connector error on %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    async def resolve_authenticated_session(
        authorization: str | None,
        x_session_token: str | None,
    ) -> ConnectorSessionView:
        try:
            return await auth_service.resolve_request_session(
                session_token=x_session_token,
                authorization_header=authorization,
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "chatgpt-connector"}

    @app.get("/mcp", response_model=ConnectorManifest)
    async def manifest() -> ConnectorManifest:
        oauth_start_path = "/oauth/start"
        oauth_callback_path = "/oauth/callback"
        if connector_root_path:
            oauth_start_path = f"{connector_root_path}{oauth_start_path}"
            oauth_callback_path = f"{connector_root_path}{oauth_callback_path}"
        return ConnectorManifest(
            service_name="chatgpt-openclaw-connector",
            oauth_start_path=oauth_start_path,
            oauth_callback_path=oauth_callback_path,
            tools=[
                ToolDefinition(
                    name=entry["name"],
                    description=entry["description"],
                    input_schema=entry["input_schema"],
                )
                for entry in tool_runner.manifest()
            ],
        )

    @app.post("/oauth/start")
    async def oauth_start(payload: OAuthStartRequest) -> dict:
        try:
            return (await auth_service.begin_oauth(
                chatgpt_subject=payload.chatgpt_subject,
                user_id=payload.user_id,
                display_name=payload.display_name,
            )).model_dump()
        except PermissionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/oauth/callback", response_model=ConnectorSessionIssuedView)
    async def oauth_callback(payload: OAuthCallbackRequest) -> ConnectorSessionIssuedView:
        try:
            return await auth_service.complete_oauth(
                state=payload.state,
                chatgpt_subject=payload.chatgpt_subject,
                user_id=payload.user_id,
                display_name=payload.display_name,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/sessions/{session_id}", response_model=ConnectorSessionView)
    async def get_session(
        session_id: str,
        authorization: str | None = Header(default=None),
        x_session_token: str | None = Header(default=None),
    ) -> ConnectorSessionView:
        caller_session = await resolve_authenticated_session(
            authorization=authorization,
            x_session_token=x_session_token,
        )
        if caller_session.session_id != session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        session = await auth_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.post("/mcp", response_model=ToolCallResponse)
    async def call_tool(
        payload: ToolCallRequest,
        authorization: str | None = Header(default=None),
        x_session_token: str | None = Header(default=None),
    ) -> ToolCallResponse:
        session = await resolve_authenticated_session(
            authorization=authorization,
            x_session_token=payload.session_token or x_session_token,
        )

        try:
            result = await tool_runner.run(payload.tool, payload.arguments, session)
            return ToolCallResponse(
                ok=True,
                tool=payload.tool,
                session_id=session.session_id,
                result=result,
            )
        except ValueError as exc:
            return ToolCallResponse(
                ok=False,
                tool=payload.tool,
                session_id=session.session_id,
                error=str(exc),
            )
        except Exception as exc:
            logger.exception("Connector tool execution failed for %s", payload.tool)
            return ToolCallResponse(
                ok=False,
                tool=payload.tool,
                session_id=session.session_id,
                error="Tool execution failed",
            )

    return app


# Deliberately export a module-level app for local Uvicorn smoke tests.
app = create_app()
