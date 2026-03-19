"""
FastAPI surface for the ChatGPT-facing OpenClaw connector.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException

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


def create_app(
    auth_service: ConnectorAuthService | None = None,
    tool_runner: OpenClawToolRunner | None = None,
) -> FastAPI:
    auth_service = auth_service or ConnectorAuthService(persist_links=True)
    tool_runner = tool_runner or OpenClawToolRunner()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        await auth_service.close()

    app = FastAPI(
        title="ChatGPT OpenClaw Connector",
        description="Separate ChatGPT-facing connector surface for OpenClaw",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.connector_auth = auth_service
    app.state.connector_tools = tool_runner

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "chatgpt-connector"}

    @app.get("/mcp", response_model=ConnectorManifest)
    async def manifest() -> ConnectorManifest:
        return ConnectorManifest(
            service_name="chatgpt-openclaw-connector",
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/sessions/{session_id}", response_model=ConnectorSessionView)
    async def get_session(session_id: str) -> ConnectorSessionView:
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
        try:
            session = await auth_service.resolve_request_session(
                session_token=payload.session_token or x_session_token,
                authorization_header=authorization,
            )
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

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
            return ToolCallResponse(
                ok=False,
                tool=payload.tool,
                session_id=session.session_id,
                error=str(exc),
            )

    return app


# Deliberately export a module-level app for local Uvicorn smoke tests.
app = create_app()
