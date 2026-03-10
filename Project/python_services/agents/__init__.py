"""
Agents Package
OpenClaw agent configurations and factory
"""

from .agent_configs import (
    AGENT_REGISTRY,
    get_agent_config,
    list_available_agents,
    STRATEGY_AGENT_CONFIG,
    MEDIA_DIRECTOR_CONFIG,
    COPYWRITER_CONFIG,
    AUDIO_SCRIPTWRITER_CONFIG,
    BROWSER_AGENT_CONFIG,
    ENGAGEMENT_PERSONA_CONFIG,
    ANALYTICS_AGENT_CONFIG,
)
from .agent_factory import AgentFactory, agent_factory

__all__ = [
    "AGENT_REGISTRY",
    "get_agent_config",
    "list_available_agents",
    "AgentFactory",
    "agent_factory",
    "STRATEGY_AGENT_CONFIG",
    "MEDIA_DIRECTOR_CONFIG",
    "COPYWRITER_CONFIG",
    "AUDIO_SCRIPTWRITER_CONFIG",
    "BROWSER_AGENT_CONFIG",
    "ENGAGEMENT_PERSONA_CONFIG",
    "ANALYTICS_AGENT_CONFIG",
]
