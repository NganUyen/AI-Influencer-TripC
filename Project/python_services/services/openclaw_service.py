"""
OpenClaw Service Integration
Serves as the cognitive engine for AI agent orchestration
"""

import httpx
import logging
from typing import Dict, Any, Optional
from config.settings import settings

logger = logging.getLogger(__name__)


class OpenClawService:
    """
    Integration with OpenClaw for multi-agent AI operations
    Handles content strategy, browser automation, and shell commands
    """

    def __init__(self):
        self.base_url = settings.OPENCLAW_API_URL
        self.api_key = settings.OPENCLAW_API_KEY
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300.0,  # 5 minutes for long-running tasks
        )

    async def execute_task(
        self,
        task_type: str,
        prompt: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute an OpenClaw task

        Args:
            task_type: Type of task (content_strategy, browser_action, shell_command)
            prompt: Task description/prompt
            user_id: User identifier
            context: Additional context for the task
        """
        logger.info(f"Executing OpenClaw task: {task_type}")

        try:
            response = await self.client.post(
                "/api/tasks/execute",
                json={
                    "task_type": task_type,
                    "prompt": prompt,
                    "user_id": user_id,
                    "context": context or {},
                    "stream": False,
                },
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"OpenClaw task completed: {task_type}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"OpenClaw task failed: {str(e)}")
            raise

    async def browser_action(
        self,
        action: str,
        url: str,
        selectors: Optional[Dict[str, str]] = None,
        proxy_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute browser automation via OpenClaw
        Uses Camoufox for stealth browsing

        Args:
            action: Browser action (navigate, click, fill, screenshot, etc.)
            url: Target URL
            selectors: CSS selectors for elements
            proxy_config: Proxy configuration for the session
        """
        logger.info(f"Executing browser action: {action} on {url}")

        try:
            response = await self.client.post(
                "/api/browser/action",
                json={
                    "action": action,
                    "url": url,
                    "selectors": selectors or {},
                    "proxy": proxy_config,
                    "stealth_mode": True,
                    "browser_engine": "camoufox",
                },
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Browser action failed: {str(e)}")
            raise

    async def shell_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute shell command via OpenClaw

        Args:
            command: Shell command to execute
            working_dir: Working directory
            env_vars: Environment variables
        """
        logger.info(f"Executing shell command: {command}")

        try:
            response = await self.client.post(
                "/api/shell/execute",
                json={"command": command, "cwd": working_dir, "env": env_vars or {}},
            )
            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Shell command failed: {str(e)}")
            raise

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a running task"""
        response = await self.client.get(f"/api/tasks/{task_id}/status")
        response.raise_for_status()
        return response.json()

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a running task"""
        response = await self.client.post(f"/api/tasks/{task_id}/cancel")
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
