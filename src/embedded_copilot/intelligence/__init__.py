"""Provider-neutral, suggestion-only Intelligence Layer contracts."""

from embedded_copilot.intelligence.gateway import ModelGateway
from embedded_copilot.intelligence.models import ModelInput, ModelResponse, ModelUsage
from embedded_copilot.intelligence.providers.base import ModelProvider

__all__ = [
    "ModelGateway",
    "ModelInput",
    "ModelProvider",
    "ModelResponse",
    "ModelUsage",
]
