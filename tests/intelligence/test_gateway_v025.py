from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.gateway import ModelGateway
from embedded_copilot.intelligence.models import (
    ModelCapability,
    ModelInput,
    ModelResponse,
)
from embedded_copilot.intelligence.providers.deepseek import DeepSeekModelProvider
from embedded_copilot.intelligence.providers.ollama import OllamaModelProvider
from embedded_copilot.intelligence.providers.openai import OpenAIModelProvider
from embedded_copilot.schemas.model import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)


def _request(task: ModelTaskType) -> ModelRequest:
    return ModelRequest(
        task_type=task,
        input_type=ModelInputType.TEXT,
        context_ids=("context:1",),
    )


def _input() -> ModelInput:
    return ModelInput(
        message_summary="Review the referenced context.",
        context_summaries=("Reference metadata is available.",),
    )


def test_model_capability_matches_provider_neutral_task_values() -> None:
    assert tuple(ModelCapability) == (
        ModelCapability.CHAT,
        ModelCapability.VISION,
        ModelCapability.CODE,
        ModelCapability.REASONING,
    )
    assert {item.value for item in ModelCapability} == {
        item.value for item in ModelTaskType
    }


def test_model_response_metadata_uses_an_explicit_runtime_allowlist() -> None:
    response = ModelResponse(
        text="This suggestion requires Engineer Review.",
        metadata={
            "cached": False,
            "latency_ms": 12.5,
            "finish_reason": "deterministic",
        },
        source="test-provider",
    )

    assert dict(response.metadata) == {
        "cached": False,
        "finish_reason": "deterministic",
        "latency_ms": 12.5,
    }
    with pytest.raises(ValidationError):
        ModelResponse(
            text="This suggestion requires Engineer Review.",
            metadata={"runtime_region": "private-zone"},
            source="test-provider",
        )


@pytest.mark.parametrize(
    "provider",
    (
        OpenAIModelProvider(),
        DeepSeekModelProvider(),
        OllamaModelProvider(),
    ),
)
def test_production_provider_placeholders_are_explicitly_unavailable(
    provider: object,
) -> None:
    with pytest.raises(ModelProviderUnavailable, match="provider is unavailable"):
        asyncio.run(
            ModelGateway((provider,)).generate(
                _request(ModelTaskType.CHAT),
                _input(),
            )
        )
