from __future__ import annotations

import asyncio

import pytest

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import (
    ModelCapability,
    ModelInput,
    ModelResponse,
)
from embedded_copilot.model_runtime.registry import ProviderRegistry
from embedded_copilot.model_runtime.routing import ModelRouter
from embedded_copilot.schemas.model import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)


class _Provider:
    def __init__(
        self,
        provider_id: str,
        capabilities: tuple[ModelCapability, ...],
        *,
        unavailable: bool = False,
    ) -> None:
        self.provider_id = provider_id
        self.supported_tasks = capabilities
        self.unavailable = unavailable
        self.calls = 0

    async def generate(
        self,
        request: ModelRequest,
        model_input: ModelInput,
    ) -> ModelResponse:
        self.calls += 1
        if self.unavailable:
            raise ModelProviderUnavailable("model provider is unavailable")
        return ModelResponse(
            text=f"Suggestion from {self.provider_id}.",
            source=self.provider_id,
        )


def _request(task_type: ModelTaskType) -> ModelRequest:
    return ModelRequest(
        task_type=task_type,
        input_type=ModelInputType.TEXT,
        context_ids=("session:1",),
    )


def _input() -> ModelInput:
    return ModelInput(message_summary="Review the embedded context.")


def test_router_selects_first_registered_capability_match() -> None:
    first = _Provider("first-provider", (ModelCapability.CHAT,))
    second = _Provider("second-provider", (ModelCapability.CHAT,))
    router = ModelRouter(ProviderRegistry((first, second)))

    response = asyncio.run(
        router.generate(_request(ModelTaskType.CHAT), _input())
    )

    assert response.source == "first-provider"
    assert first.calls == 1
    assert second.calls == 0


def test_router_does_not_fallback_after_selected_provider_failure() -> None:
    first = _Provider(
        "first-provider",
        (ModelCapability.REASONING,),
        unavailable=True,
    )
    second = _Provider("second-provider", (ModelCapability.REASONING,))
    router = ModelRouter(ProviderRegistry((first, second)))

    with pytest.raises(ModelProviderUnavailable):
        asyncio.run(router.generate(_request(ModelTaskType.REASONING), _input()))

    assert first.calls == 1
    assert second.calls == 0


def test_router_reports_unsupported_vision_without_provider_call() -> None:
    provider = _Provider(
        "text-provider",
        (
            ModelCapability.CHAT,
            ModelCapability.CODE,
            ModelCapability.REASONING,
        ),
    )
    router = ModelRouter(ProviderRegistry((provider,)))

    with pytest.raises(
        ModelProviderUnavailable,
        match="^model provider is unavailable$",
    ):
        asyncio.run(router.generate(_request(ModelTaskType.VISION), _input()))

    assert provider.calls == 0


def test_multi_model_registration_does_not_change_model_request_contract() -> None:
    fields_before = tuple(ModelRequest.model_fields)
    router = ModelRouter(
        ProviderRegistry(
            (
                _Provider("chat-model", (ModelCapability.CHAT,)),
                _Provider("code-model", (ModelCapability.CODE,)),
            )
        )
    )

    response = asyncio.run(
        router.generate(_request(ModelTaskType.CODE), _input())
    )

    assert response.source == "code-model"
    assert tuple(ModelRequest.model_fields) == fields_before == (
        "task_type",
        "input_type",
        "context_ids",
    )
