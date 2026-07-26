from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.intelligence.models import ModelCapability, ModelInput
from embedded_copilot.model_runtime.providers.ollama import OllamaProvider
from embedded_copilot.schemas.model import (
    ModelInputType,
    ModelRequest,
    ModelTaskType,
)


def _request(task_type: ModelTaskType = ModelTaskType.CHAT) -> ModelRequest:
    return ModelRequest(
        task_type=task_type,
        input_type=ModelInputType.TEXT,
        context_ids=("session:1",),
    )


def _input() -> ModelInput:
    return ModelInput(
        message_summary="Explain the referenced embedded context.",
        context_summaries=("Reference metadata is available.",),
    )


def test_ollama_provider_sends_request_scoped_non_streaming_generation() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "edge-model:latest",
                "created_at": "2026-07-26T08:00:00Z",
                "response": "Candidate reasoning suggestion.",
                "thinking": "PRIVATE_REASONING_TRACE",
                "done": True,
                "done_reason": "stop",
                "context": [1, 2, 3],
                "total_duration": 10,
                "prompt_eval_count": 4,
                "eval_count": 5,
            },
        )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="edge-model:latest",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(respond),
    )

    response = asyncio.run(provider.generate(_request(), _input()))

    assert provider.provider_id == "ollama"
    assert provider.supported_tasks == (
        ModelCapability.CHAT,
        ModelCapability.CODE,
        ModelCapability.REASONING,
    )
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/generate"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "edge-model:latest"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert response.output_type == "reasoning_suggestion"
    assert response.text == "Candidate reasoning suggestion."
    assert response.source == "ollama"
    assert set(response.metadata) == {"cached", "finish_reason", "latency_ms"}
    assert response.metadata["cached"] is False
    assert response.metadata["finish_reason"] == "stop"
    assert isinstance(response.metadata["latency_ms"], float)
    serialized = response.model_dump_json()
    assert "PRIVATE_REASONING_TRACE" not in serialized
    assert "context" not in serialized
    assert "prompt_eval_count" not in serialized


def test_ollama_provider_does_not_retain_generation_payloads() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"response": "Request-scoped answer.", "done_reason": "stop"},
        )

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="arbitrary-model",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(respond),
    )

    asyncio.run(provider.generate(_request(), _input()))

    for forbidden in (
        "client",
        "_client",
        "prompt",
        "_prompt",
        "response",
        "_response",
        "history",
        "_history",
    ):
        assert not hasattr(provider, forbidden)


@pytest.mark.parametrize(
    "response",
    (
        httpx.Response(503, text="PRIVATE_ENDPOINT_DIAGNOSTIC"),
        httpx.Response(200, content=b"not-json"),
        httpx.Response(200, json={"response": 123, "done_reason": "stop"}),
        httpx.Response(
            200,
            json={
                "response": "Suggestion.",
                "done_reason": "x" * 65,
            },
        ),
    ),
)
def test_ollama_provider_maps_untrusted_failures_to_safe_unavailable(
    response: httpx.Response,
) -> None:
    secret_url = "http://127.0.0.1:11434"

    provider = OllamaProvider(
        base_url=secret_url,
        model="private-model-name",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(lambda request: response),
    )

    with pytest.raises(ModelProviderUnavailable) as captured:
        asyncio.run(provider.generate(_request(), _input()))

    message = str(captured.value)
    assert message == "model provider is unavailable"
    assert secret_url not in message
    assert "private-model-name" not in message
    assert "PRIVATE_" not in message


def test_ollama_provider_maps_transport_errors_to_safe_unavailable() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("PRIVATE_URL_TOKEN", request=request)

    provider = OllamaProvider(
        base_url="http://127.0.0.1:11434",
        model="private-model-name",
        timeout_seconds=2.0,
        transport=httpx.MockTransport(fail),
    )

    with pytest.raises(
        ModelProviderUnavailable,
        match="^model provider is unavailable$",
    ):
        asyncio.run(provider.generate(_request(), _input()))
