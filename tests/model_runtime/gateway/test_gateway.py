from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from embedded_copilot.core.config import Settings
from embedded_copilot.intelligence.exceptions import ModelProviderUnavailable
from embedded_copilot.model_runtime import create_model_runtime


def test_runtime_reasoning_port_is_model_agnostic() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "response": "Candidate reasoning suggestion.",
                "done_reason": "stop",
            },
        )

    runtime = create_model_runtime(
        Settings(
            model_provider="ollama",
            ollama_model="arbitrary-edge-model",
            _env_file=None,
        ),
        transport=httpx.MockTransport(respond),
    )

    output = asyncio.run(
        runtime.reasoning_port().reason(
            user_message_summary="Explain the embedded context.",
            context_summaries=("Reference metadata is available.",),
            task_intent="GENERAL",
        )
    )

    assert output.response.text == "Candidate reasoning suggestion."
    assert output.reasoning_chain == ()
    assert output.temporary_context == ()
    assert len(requests) == 1
    payload = json.loads(requests[0].content)
    assert payload["model"] == "arbitrary-edge-model"
    assert set(payload) == {"model", "prompt", "stream", "think"}


def test_unavailable_runtime_does_not_make_network_request() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"response": "unexpected"})

    runtime = create_model_runtime(
        Settings(_env_file=None),
        transport=httpx.MockTransport(respond),
    )

    with pytest.raises(ModelProviderUnavailable):
        asyncio.run(
            runtime.reasoning_port().reason(
                user_message_summary="Explain the embedded context.",
                context_summaries=(),
                task_intent="GENERAL",
            )
        )

    assert calls == 0


def test_runtime_rejects_vision_without_calling_ollama() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"response": "unexpected"})

    runtime = create_model_runtime(
        Settings(
            model_provider="ollama",
            ollama_model="text-only-model",
            _env_file=None,
        ),
        transport=httpx.MockTransport(respond),
    )

    with pytest.raises(ModelProviderUnavailable):
        asyncio.run(
            runtime.reasoning_port().reason(
                user_message_summary="Inspect the referenced image.",
                context_summaries=("Image reference metadata.",),
                task_intent="VISION_ANALYSIS",
            )
        )

    assert calls == 0
