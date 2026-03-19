"""
Safe tool wrappers around the internal OpenClaw service.

The connector only exposes a constrained subset of OpenClaw operations to
avoid surfacing shell execution through the ChatGPT-facing layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .models import ConnectorSessionView


def _default_openclaw_service_factory():
    from services.openclaw_service import OpenClawService

    return OpenClawService()


@dataclass
class ToolExecutionContext:
    session_id: str
    user_id: str
    chatgpt_subject: str
    display_name: Optional[str]


class OpenClawToolRunner:
    def __init__(self, service_factory: Optional[Callable[[], Any]] = None) -> None:
        self.service_factory = service_factory or _default_openclaw_service_factory

    @staticmethod
    def manifest() -> list[dict[str, Any]]:
        return [
            {
                "name": "openclaw_execute_task",
                "description": "Run a safe OpenClaw task such as strategy, analysis, or browser workflows. Shell execution is intentionally not exposed.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "task_type": {"type": "string"},
                        "prompt": {"type": "string"},
                        "context": {"type": "object"},
                    },
                    "required": ["task_type", "prompt"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "openclaw_get_task_status",
                "description": "Fetch the status of an existing OpenClaw task.",
                "input_schema": {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "openclaw_cancel_task",
                "description": "Cancel an existing OpenClaw task.",
                "input_schema": {
                    "type": "object",
                    "properties": {"task_id": {"type": "string"}},
                    "required": ["task_id"],
                    "additionalProperties": False,
                },
            },
        ]

    @staticmethod
    def _build_context(session: ConnectorSessionView, payload: Dict[str, Any]) -> ToolExecutionContext:
        return ToolExecutionContext(
            session_id=session.session_id,
            user_id=session.user_id,
            chatgpt_subject=session.chatgpt_subject,
            display_name=session.display_name,
        )

    @staticmethod
    async def _close_service(service: Any) -> None:
        close = getattr(service, "close", None)
        if callable(close):
            result = close()
            if hasattr(result, "__await__"):
                await result

    async def run(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        session: ConnectorSessionView,
    ) -> Dict[str, Any]:
        if tool_name == "openclaw_execute_task":
            return await self.execute_task(arguments, session)
        if tool_name == "openclaw_get_task_status":
            return await self.get_task_status(arguments, session)
        if tool_name == "openclaw_cancel_task":
            return await self.cancel_task(arguments, session)
        raise ValueError(f"Unsupported connector tool: {tool_name}")

    async def execute_task(
        self,
        arguments: Dict[str, Any],
        session: ConnectorSessionView,
    ) -> Dict[str, Any]:
        task_type = str(arguments.get("task_type") or "").strip()
        prompt = str(arguments.get("prompt") or "").strip()
        if not task_type:
            raise ValueError("task_type is required")
        if task_type == "shell_command":
            raise ValueError("Shell execution is not exposed through the ChatGPT connector")
        if not prompt:
            raise ValueError("prompt is required")

        service = self.service_factory()
        try:
            context_payload = dict(arguments.get("context") or {})
            context_payload["connector_session"] = self._build_context(session, arguments).__dict__
            return await service.execute_task(
                task_type=task_type,
                prompt=prompt,
                user_id=session.user_id,
                context=context_payload,
            )
        finally:
            await self._close_service(service)

    async def get_task_status(
        self,
        arguments: Dict[str, Any],
        session: ConnectorSessionView,
    ) -> Dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id is required")

        service = self.service_factory()
        try:
            return await service.get_task_status(task_id)
        finally:
            await self._close_service(service)

    async def cancel_task(
        self,
        arguments: Dict[str, Any],
        session: ConnectorSessionView,
    ) -> Dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id is required")

        service = self.service_factory()
        try:
            return await service.cancel_task(task_id)
        finally:
            await self._close_service(service)
