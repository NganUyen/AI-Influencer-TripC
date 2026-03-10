"""
Agent Factory
Creates and manages OpenClaw agent instances
"""

import logging
from typing import Dict, Any, Optional
from services.openclaw_service import OpenClawService
from .agent_configs import get_agent_config

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating and managing OpenClaw agents
    """

    def __init__(self):
        self.openclaw = OpenClawService()
        self.active_agents: Dict[str, Any] = {}

    async def create_agent(
        self,
        agent_type: str,
        user_id: str,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create an agent instance

        Args:
            agent_type: Type of agent (strategist, media_director, etc.)
            user_id: User identifier
            custom_config: Optional custom configuration overrides
        """
        logger.info(f"Creating {agent_type} agent for user {user_id}")

        # Get base configuration
        base_config = get_agent_config(agent_type)

        if not base_config:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Merge with custom config
        config = {**base_config, **(custom_config or {})}

        # Create agent via OpenClaw
        agent = await self.openclaw.execute_task(
            task_type="create_agent",
            prompt=config.get("system_prompt", ""),
            user_id=user_id,
            context={
                "agent_name": config.get("name"),
                "role": config.get("role"),
                "capabilities": config.get("capabilities"),
                "model": config.get("model"),
                "temperature": config.get("temperature"),
            },
        )

        # Store agent instance
        agent_id = f"{agent_type}_{user_id}"
        self.active_agents[agent_id] = {
            "agent": agent,
            "config": config,
            "user_id": user_id,
        }

        logger.info(f"Agent {agent_id} created successfully")
        return agent

    async def execute_agent_task(
        self, agent_id: str, task: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a task using an existing agent

        Args:
            agent_id: Agent identifier
            task: Task description
            context: Additional context for the task
        """
        if agent_id not in self.active_agents:
            raise ValueError(f"Agent {agent_id} not found")

        agent_data = self.active_agents[agent_id]

        result = await self.openclaw.execute_task(
            task_type="agent_task",
            prompt=task,
            user_id=agent_data["user_id"],
            context={"agent_config": agent_data["config"], **(context or {})},
        )

        return result

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get an active agent by ID"""
        return self.active_agents.get(agent_id)

    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from active agents"""
        if agent_id in self.active_agents:
            del self.active_agents[agent_id]
            logger.info(f"Agent {agent_id} removed")
            return True
        return False

    async def list_active_agents(self) -> list:
        """List all active agents"""
        return list(self.active_agents.keys())

    async def close(self):
        """Cleanup all agents"""
        self.active_agents.clear()
        await self.openclaw.close()


# Global agent factory instance
agent_factory = AgentFactory()
