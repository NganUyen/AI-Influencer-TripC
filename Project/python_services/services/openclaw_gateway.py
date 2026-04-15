"""
Canonical OpenClaw gateway abstraction.
"""

from __future__ import annotations

from services.openclaw_service import OpenClawService


class OpenClawGateway(OpenClawService):
    """Compatibility alias for the transport-aware OpenClaw gateway."""

    pass
