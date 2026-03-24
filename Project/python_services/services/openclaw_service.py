"""
OpenClaw service adapter for the current public gateway APIs.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


def _strip_markdown_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return text


def _maybe_parse_json(value: str) -> Any:
    cleaned = _strip_markdown_fence(value)
    if not cleaned:
        return {}

    candidates = [cleaned]
    if "{" in cleaned and "}" in cleaned:
        candidates.append(cleaned[cleaned.find("{") : cleaned.rfind("}") + 1])
    if "[" in cleaned and "]" in cleaned:
        candidates.append(cleaned[cleaned.find("[") : cleaned.rfind("]") + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return {"text": cleaned}


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

    def __init__(self):
        self.base_url = settings.OPENCLAW_API_URL.rstrip("/")
        self.api_key = settings.OPENCLAW_API_KEY
        self.agent_id = settings.OPENCLAW_AGENT_ID.strip() or "main"

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=300.0,
        )

    async def execute_task(
        self,
        task_type: str,
        prompt: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("Executing OpenClaw task via /v1/responses: %s", task_type)

        payload = {
            "model": f"openclaw:{self.agent_id}",
            "input": _build_prompt(task_type, prompt, user_id, context),
            "user": user_id,
        }

        response = await self.client.post("/v1/responses", json=payload)
        response.raise_for_status()

        raw = response.json()
        output_text = _extract_output_text(raw)
        result = _maybe_parse_json(output_text)

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

        response = await self.client.post("/tools/invoke", json=payload)
        response.raise_for_status()
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

    async def close(self):
        await self.client.aclose()
