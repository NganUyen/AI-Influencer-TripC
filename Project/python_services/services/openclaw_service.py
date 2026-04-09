"""
OpenClaw service adapter for the current public gateway APIs.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx

from config.settings import settings
from utils.json_helpers import extract_json_from_llm_response

logger = logging.getLogger(__name__)

_shared_client: Optional[httpx.AsyncClient] = None


def _get_shared_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = httpx.AsyncClient(timeout=300.0)
    return _shared_client



def _extract_output_text(payload: Dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def _build_prompt(
    task_type: str,
    prompt: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [
        f"Task type: {task_type}",
        f"User ID: {user_id}",
        prompt.strip(),
    ]
    if context:
        parts.extend(
            [
                "Context JSON:",
                json.dumps(context, ensure_ascii=True, sort_keys=True, indent=2),
            ]
        )
    parts.append(
        "Return JSON when the task naturally produces structured data. "
        "If structured data is not appropriate, return concise plain text."
    )
    return "\n\n".join(part for part in parts if part)


class OpenClawService:
    """
    Adapter around the public OpenClaw gateway HTTP APIs.

    - execute_task -> POST /v1/responses
    - browser_action -> POST /tools/invoke
    - shell_command -> POST /tools/invoke
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        connector_session_token: Optional[str] = None,
    ):
        self.base_url = f"{(base_url or settings.OPENCLAW_API_URL).rstrip('/')}/"
        self.api_key = api_key if api_key is not None else settings.OPENCLAW_API_KEY
        self.agent_id = (agent_id or settings.OPENCLAW_AGENT_ID).strip() or "main"
        self.connector_session_token = connector_session_token
        self.transport = "connector" if connector_session_token else "responses"

        self.headers = {"Content-Type": "application/json"}
        if self.connector_session_token:
            self.headers["Authorization"] = f"Bearer {self.connector_session_token}"
        elif self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = _get_shared_client()

    @classmethod
    async def create_for_owner(
        cls,
        *,
        owner_key: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> "OpenClawService":
        resolved_user_id = str(user_id or "").strip() or None

        if not resolved_user_id and owner_key:
            from services.telegram_link_service import TelegramLinkService

            resolved_user_id = await TelegramLinkService.resolve_user_id_for_owner_key(
                owner_key
            )

        if not resolved_user_id:
            return cls()

        from services.customer_ai_backbone_service import CustomerAIBackboneService

        runtime_config = await CustomerAIBackboneService.resolve_runtime_config(
            resolved_user_id
        )
        return cls(
            base_url=runtime_config.get("base_url"),
            api_key=runtime_config.get("api_key"),
            connector_session_token=runtime_config.get("connector_session_token"),
        )

    async def _record_usage(
        self,
        operation: str,
        usage: Dict[str, Any],
        error: Exception | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        from services.quota_monitor_service import QuotaMonitorService
        quota_metadata = {
            "service": "openclaw_service",
            "operation": operation,
            "status": "error" if error else "success",
            "transport": self.transport,
            "agent_id": self.agent_id,
        }
        if metadata:
            quota_metadata.update(metadata)
        if error:
            quota_metadata["error_type"] = type(error).__name__
            quota_metadata["error_message"] = str(error)

        await QuotaMonitorService.record_runtime_usage(
            provider="openclaw",
            usage=usage,
            metadata=quota_metadata,
        )

    @staticmethod
    def _extract_error_message(exc: httpx.HTTPStatusError) -> str:
        try:
            payload = exc.response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()
            error = payload.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()
        body = exc.response.text.strip()
        if body:
            return body
        return str(exc)

    @staticmethod
    def _extract_failed_response_message(payload: Dict[str, Any]) -> Optional[str]:
        if not isinstance(payload, dict):
            return None

        error = payload.get("error")
        status = str(payload.get("status") or "").strip().lower()
        if status != "failed" and not isinstance(error, dict):
            return None

        parts: list[str] = []
        response_id = str(payload.get("id") or "").strip()
        model = str(payload.get("model") or "").strip()
        if response_id:
            parts.append(f"id={response_id}")
        if model:
            parts.append(f"model={model}")
        if status:
            parts.append(f"status={status}")

        if isinstance(error, dict):
            code = str(error.get("code") or "").strip()
            message = str(error.get("message") or "").strip()
            if code:
                parts.append(f"code={code}")
            if message:
                parts.append(f"message={message}")

        return ", ".join(parts) if parts else "request failed"

    @classmethod
    def _raise_provider_error(cls, exc: httpx.HTTPStatusError, transport: str) -> None:
        status_code = exc.response.status_code if exc.response is not None else None
        if transport == "connector":
            if status_code == 401:
                raise ValueError(
                    "GPT OAuth access was rejected. Reconnect your GPT Plus or Pro link and try again."
                ) from exc
            raise ValueError(
                f"Connector-backed GPT OAuth request failed: {cls._extract_error_message(exc)}"
            ) from exc

        if status_code in {401, 403}:
            raise ValueError(
                "The provided OpenClaw API key was rejected. Update it or switch back to workspace-managed access."
            ) from exc
        raise ValueError(
            f"OpenClaw request failed: {cls._extract_error_message(exc)}"
        ) from exc

    @staticmethod
    def _raise_network_error(exc: httpx.RequestError, transport: str) -> None:
        endpoint = str(exc.request.url) if exc.request is not None else "OpenClaw endpoint"
        if transport == "connector":
            raise ValueError(
                f"Connector-backed GPT OAuth request could not reach {endpoint}: {exc}"
            ) from exc

        raise ValueError(
            f"OpenClaw service is unreachable at {endpoint}: {exc}"
        ) from exc

    async def execute_task(
        self,
        task_type: str,
        prompt: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if self.transport == "connector":
            logger.info("Executing OpenClaw task via ChatGPT connector: %s", task_type)
            payload = {
                "tool": "openclaw_execute_task",
                "arguments": {
                    "task_type": task_type,
                    "prompt": prompt,
                    "context": context or {},
                },
            }
            try:
                response = await self.client.post(f"{self.base_url}mcp", json=payload, headers=self.headers)
                response.raise_for_status()
            except httpx.RequestError as exc:
                self._raise_network_error(exc, transport="connector")
            except httpx.HTTPStatusError as exc:
                self._raise_provider_error(exc, transport="connector")

            raw = response.json()
            if not raw.get("ok"):
                raise ValueError(
                    raw.get("error")
                    or "Connector-backed GPT OAuth request failed"
                )

            result = raw.get("result")
            if isinstance(result, dict):
                result.setdefault("task_type", task_type)
                result.setdefault("connector_session_id", raw.get("session_id"))
                return result
            return {
                "task_type": task_type,
                "connector_session_id": raw.get("session_id"),
                "result": result,
            }

        logger.info("Executing OpenClaw task via /v1/responses: %s", task_type)

        payload = {
            "model": f"openclaw:{self.agent_id}",
            "input": _build_prompt(task_type, prompt, user_id, context),
            "user": user_id,
        }

        try:
            response = await self.client.post(f"{self.base_url}v1/responses", json=payload, headers=self.headers)
            response.raise_for_status()
            await self._record_usage(
                operation="execute_task",
                usage={"requests": 1},
                metadata={"task_type": task_type},
            )
        except httpx.RequestError as exc:
            await self._record_usage(
                operation="execute_task",
                usage={"requests": 1},
                metadata={"task_type": task_type},
                error=exc,
            )
            self._raise_network_error(exc, transport="responses")
        except httpx.HTTPStatusError as exc:
            await self._record_usage(
                operation="execute_task",
                usage={"requests": 1},
                metadata={"task_type": task_type},
                error=exc,
            )
            self._raise_provider_error(exc, transport="responses")

        raw = response.json()
        failed_message = self._extract_failed_response_message(raw)
        if failed_message:
            raise ValueError(f"OpenClaw request failed: {failed_message}")

        output_text = _extract_output_text(raw)
        result = extract_json_from_llm_response(output_text)

        if isinstance(result, dict):
            result.setdefault("response_id", raw.get("id"))
            result.setdefault("task_type", task_type)
            return result

        return {
            "response_id": raw.get("id"),
            "task_type": task_type,
            "result": result,
        }

    async def _invoke_tool(
        self,
        tool: str,
        action: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        session_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tool": tool,
            "args": args or {},
        }
        if action:
            payload["action"] = action
        if session_key:
            payload["sessionKey"] = session_key

        try:
            response = await self.client.post(f"{self.base_url}tools/invoke", json=payload, headers=self.headers)
            response.raise_for_status()
        except httpx.RequestError as exc:
            self._raise_network_error(exc, transport="responses")
        except httpx.HTTPStatusError as exc:
            self._raise_provider_error(exc, transport="responses")
        return response.json()

    async def browser_action(
        self,
        action: str,
        url: str,
        selectors: Optional[Dict[str, str]] = None,
        proxy_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("Executing OpenClaw browser action via /tools/invoke: %s", action)
        return await self._invoke_tool(
            tool="browser",
            action=action,
            args={
                "url": url,
                "selectors": selectors or {},
                "proxy": proxy_config,
                "stealth_mode": True,
            },
        )

    async def shell_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        logger.info("Executing OpenClaw shell command via /tools/invoke")
        return await self._invoke_tool(
            tool="exec",
            args={
                "cmd": command,
                "cwd": working_dir,
                "env": env_vars or {},
            },
        )

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        logger.warning("OpenClaw task status is shimmed locally for connector tasks: %s", task_id)
        return {
            "task_id": task_id,
            "status": "unsupported",
            "message": "Current public OpenClaw HTTP APIs do not expose a native REST task status endpoint.",
        }

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        logger.warning("OpenClaw task cancel is shimmed locally for connector tasks: %s", task_id)
        return {
            "task_id": task_id,
            "status": "unsupported",
            "message": "Current public OpenClaw HTTP APIs do not expose a native REST task cancel endpoint.",
        }

    async def close(self) -> None:
        pass  # Shared client lifecycle is globally managed

    async def __aenter__(self) -> 'OpenClawService':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
