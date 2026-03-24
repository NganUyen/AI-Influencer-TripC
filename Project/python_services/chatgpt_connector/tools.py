"""
Safe tool wrappers around the internal OpenClaw service.

The connector only exposes a constrained subset of OpenClaw operations to
avoid surfacing shell execution through the ChatGPT-facing layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

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


_TASK_REGISTRY: Dict[str, Dict[str, Any]] = {}


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
        task_id = f"task_{uuid4().hex}"
        _TASK_REGISTRY[task_id] = {
            "task_id": task_id,
            "status": "running",
            "tool": "openclaw_execute_task",
            "session_id": session.session_id,
            "user_id": session.user_id,
        }
        try:
            context_payload = dict(arguments.get("context") or {})
            context_payload["connector_session"] = self._build_context(session, arguments).__dict__
            result = await service.execute_task(
                task_type=task_type,
                prompt=prompt,
                user_id=session.user_id,
                context=context_payload,
            )
            _TASK_REGISTRY[task_id].update(
                {
                    "status": "completed",
                    "result": result,
                }
            )
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result,
            }
        except Exception as exc:
            _TASK_REGISTRY[task_id].update(
                {
                    "status": "failed",
                    "error": str(exc),
                }
            )
            raise
        finally:
            await self._close_service(service)

    @staticmethod
    def _get_task_for_session(
        task_id: str,
        session: ConnectorSessionView,
    ) -> Optional[Dict[str, Any]]:
        task = _TASK_REGISTRY.get(task_id)
        if task is None:
            return None
        if task.get("session_id") != session.session_id:
            return None
        return task

    async def get_task_status(
        self,
        arguments: Dict[str, Any],
        session: ConnectorSessionView,
    ) -> Dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id is required")

        task = self._get_task_for_session(task_id, session)
        if not task:
            return {
                "task_id": task_id,
                "status": "not_found",
            }
        return dict(task)

    async def cancel_task(
        self,
        arguments: Dict[str, Any],
        session: ConnectorSessionView,
    ) -> Dict[str, Any]:
        task_id = str(arguments.get("task_id") or "").strip()
        if not task_id:
            raise ValueError("task_id is required")

        task = self._get_task_for_session(task_id, session)
        if not task:
            return {
                "task_id": task_id,
                "status": "not_found",
            }
        if task.get("status") not in {"completed", "failed", "canceled"}:
            task["status"] = "canceled"
        return dict(task)
