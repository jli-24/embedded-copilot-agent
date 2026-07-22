"""Shared foundation models, configuration, and capability infrastructure."""

from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.core.config import Settings
from embedded_copilot.core.models import AgentContext

__all__ = ["AgentContext", "CapabilityRegistry", "Settings"]
