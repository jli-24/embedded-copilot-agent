from __future__ import annotations

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import (
    ModelCapability,
    ModelInput,
    ModelResponse,
)
from embedded_copilot.schemas.model import ModelRequest


class UnavailableModelProvider:
    """Non-networked placeholder for an unconfigured production provider."""

    provider_id = "unavailable-provider"
    supported_tasks = tuple(ModelCapability)

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        raise ModelProviderUnavailable("model provider is unavailable")
