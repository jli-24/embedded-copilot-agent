from __future__ import annotations

from dataclasses import dataclass

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import (
    ModelCapability,
    ModelInput,
    ModelResponse,
)
from embedded_copilot.model_runtime.registry import ProviderRegistry
from embedded_copilot.schemas.model import ModelRequest


@dataclass(frozen=True, slots=True)
class ModelRouter:
    _registry: ProviderRegistry

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        capability = ModelCapability(request.task_type.value)
        providers = self._registry.for_capability(capability)
        if not providers:
            raise ModelProviderUnavailable("model provider is unavailable")
        return await providers[0].generate(request, model_input)
