from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from embedded_copilot.copilot.models import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)
from embedded_copilot.intelligence.exceptions import (
    ModelGatewayError,
    ModelProviderUnavailable,
)
from embedded_copilot.intelligence.gateway import ModelGateway
from embedded_copilot.intelligence.models import (
    ModelInput,
    ModelResponse,
    ModelUsage,
)
from embedded_copilot.intelligence.providers.mock import (
    DeterministicMockProvider,
    UnavailableLocalModelProvider,
)


def _request(task: ModelTaskType = ModelTaskType.REASONING) -> ModelRequest:
    return ModelRequest(
        task_type=task,
        input_type=ModelInputType.TEXT,
        context_ids=("message:1",),
    )


def _input() -> ModelInput:
    return ModelInput(
        message_summary="Review the referenced engineering context.",
        context_summaries=("Existing evidence is available for review.",),
    )


def test_v022_model_request_contract_remains_unchanged() -> None:
    assert set(ModelRequest.model_fields) == {
        "task_type",
        "input_type",
        "context_ids",
    }


def test_model_contracts_are_frozen_and_usage_is_consistent() -> None:
    usage = ModelUsage(input_tokens=4, output_tokens=3, total_tokens=7)
    response = ModelResponse(
        text="Review GPIO4 as an unverified reasoning suggestion.",
        metadata={"finish_reason": "stop", "cached": False},
        usage=usage,
        source="mock-provider",
    )

    assert response.output_type == "reasoning_suggestion"
    assert dict(response.metadata) == {"cached": False, "finish_reason": "stop"}
    with pytest.raises(TypeError):
        response.metadata["cached"] = True  # type: ignore[index]
    with pytest.raises(ValidationError):
        response.text = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ModelUsage(input_tokens=4, output_tokens=3, total_tokens=8)


@pytest.mark.parametrize(
    "metadata",
    (
        {"gpio": 4},
        {"components": "MQ-2"},
        {"connection": "sensor-to-mcu"},
        {"voltage": 3.3},
        {"current": 0.1},
        {"artifact_decision": "GPIO4"},
        {"api_key": "SECRET_SENTINEL"},
        {"path": "C:/private/context.txt"},
    ),
)
def test_model_response_rejects_engineering_fact_or_sensitive_metadata(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ModelResponse(
            text="Treat this output only as a reasoning suggestion.",
            metadata=metadata,
            source="mock-provider",
        )


def test_gateway_routes_by_capability_and_revalidates_response() -> None:
    code = DeterministicMockProvider(
        provider_id="code-provider",
        supported_tasks=(ModelTaskType.CODE,),
        response_text="Review code assumptions before engineering validation.",
    )
    reasoning = DeterministicMockProvider(
        provider_id="reasoning-provider",
        supported_tasks=(ModelTaskType.REASONING,),
        response_text="Candidate reasoning requires Engineering Agent validation.",
    )
    gateway = ModelGateway((code, reasoning))

    first = asyncio.run(gateway.generate(_request(), _input()))
    second = asyncio.run(gateway.generate(_request(), _input()))

    assert first == second
    assert first.source == "reasoning-provider"
    assert first.output_type == "reasoning_suggestion"
    assert code.calls == ()
    assert len(reasoning.calls) == 2


def test_gateway_isolates_provider_failures_without_secret_leakage() -> None:
    class FailingProvider:
        provider_id = "failing-provider"
        supported_tasks = (ModelTaskType.REASONING,)

        async def generate(
            self,
            request: ModelRequest,
            model_input: ModelInput,
        ) -> ModelResponse:
            raise RuntimeError("token=SECRET_SENTINEL C:/private/model")

    with pytest.raises(ModelGatewayError, match="model provider failed") as captured:
        asyncio.run(ModelGateway((FailingProvider(),)).generate(_request(), _input()))

    assert "SECRET_SENTINEL" not in str(captured.value)
    assert "private" not in str(captured.value)


def test_unavailable_local_placeholder_and_missing_route_fail_explicitly() -> None:
    with pytest.raises(ModelProviderUnavailable, match="local model is unavailable"):
        asyncio.run(
            ModelGateway((UnavailableLocalModelProvider(),)).generate(
                _request(),
                _input(),
            )
        )

    with pytest.raises(ModelProviderUnavailable, match="model provider is unavailable"):
        asyncio.run(ModelGateway(()).generate(_request(), _input()))
