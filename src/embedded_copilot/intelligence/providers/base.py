from __future__ import annotations

from typing import Protocol

from embedded_copilot.intelligence.models import ModelInput, ModelResponse
from embedded_copilot.schemas.model import ModelRequest, ModelTaskType


class ModelProvider(Protocol):
    provider_id: str
    supported_tasks: tuple[ModelTaskType, ...]

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse: ...
