from __future__ import annotations

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import ModelInput, ModelResponse
from embedded_copilot.schemas.model import ModelRequest, ModelTaskType


class DeterministicMockProvider:
    """Deterministic test provider that never retains request content."""

    def __init__(
        self,
        *,
        provider_id: str = "mock-provider",
        supported_tasks: tuple[ModelTaskType, ...] = tuple(ModelTaskType),
        response_text: str = (
            "This is a reasoning suggestion requiring Engineering Agent validation."
        ),
    ) -> None:
        self.provider_id = provider_id
        self.supported_tasks = supported_tasks
        self._response_text = response_text
        self._call_count = 0

    @property
    def calls(self) -> tuple[int, ...]:
        return tuple(range(self._call_count))

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        self._call_count += 1
        return ModelResponse(
            text=self._response_text,
            metadata={"cached": False, "finish_reason": "deterministic"},
            source=self.provider_id,
        )


class UnavailableLocalModelProvider:
    """Explicit placeholder; it never pretends a local model is configured."""

    provider_id = "local-model"
    supported_tasks = tuple(ModelTaskType)

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        raise ModelProviderUnavailable("local model is unavailable")
