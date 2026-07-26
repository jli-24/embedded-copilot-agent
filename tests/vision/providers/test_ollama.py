from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from embedded_copilot.vision_runtime import ImageType, VisionRequest
from embedded_copilot.vision_runtime.providers import (
    OllamaVisionProvider,
    VisionProviderTimeout,
    VisionProviderUnavailable,
)


def _request() -> VisionRequest:
    return VisionRequest(
        session_id="session:1",
        reference_id="image:1",
        image_type=ImageType.UNKNOWN,
        instruction_summary="Review the registered image reference.",
    )


def test_ollama_provider_sends_metadata_only_non_streaming_request() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "response": "The metadata suggests an engineer review is needed.",
                "done_reason": "stop",
                "thinking": "hidden trace",
                "context": [1, 2, 3],
                "diagnostics": {"host": "private"},
            },
        )

    provider = OllamaVisionProvider(
        base_url="http://127.0.0.1:11434",
        model="edge-vision:latest",
        timeout_seconds=5.0,
        transport=httpx.MockTransport(respond),
    )

    result = asyncio.run(
        provider.analyze(
            _request(),
            reference_summary="Registered schematic screenshot metadata.",
        )
    )

    assert result.summary == (
        "The metadata suggests an engineer review is needed."
    )
    assert set(result.metadata) == {"cached", "finish_reason", "latency_ms"}
    assert result.metadata["cached"] is False
    assert result.metadata["finish_reason"] == "stop"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/generate"
    payload = json.loads(requests[0].content)
    assert payload == {
        "model": "edge-vision:latest",
        "prompt": (
            "Instruction: Review the registered image reference.\n"
            "Image type: unknown\n"
            "Reference summary: Registered schematic screenshot metadata."
        ),
        "stream": False,
        "think": False,
    }
    assert "images" not in payload
    assert "image:1" not in requests[0].content.decode()
    assert "session:1" not in requests[0].content.decode()
    assert not hasattr(provider, "prompt")
    assert not hasattr(provider, "response")
    assert not hasattr(provider, "client")


def test_ollama_provider_maps_timeout_to_safe_timeout_error() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("PRIVATE_ENDPOINT", request=request)

    provider = OllamaVisionProvider(
        base_url="http://127.0.0.1:11434",
        model="vision-model",
        timeout_seconds=1.0,
        transport=httpx.MockTransport(timeout),
    )

    with pytest.raises(
        VisionProviderTimeout,
        match=r"^vision provider request timed out$",
    ):
        asyncio.run(
            provider.analyze(
                _request(),
                reference_summary="Registered image reference.",
            )
        )


@pytest.mark.parametrize(
    "response",
    (
        httpx.Response(503, text="PRIVATE_PROVIDER"),
        httpx.Response(200, json={"response": {"unsafe": True}}),
        httpx.Response(200, text="not-json"),
    ),
)
def test_ollama_provider_maps_untrusted_failures_to_safe_unavailable(
    response: httpx.Response,
) -> None:
    provider = OllamaVisionProvider(
        base_url="http://127.0.0.1:11434",
        model="vision-model",
        timeout_seconds=1.0,
        transport=httpx.MockTransport(lambda request: response),
    )

    with pytest.raises(
        VisionProviderUnavailable,
        match=r"^vision provider is unavailable$",
    ):
        asyncio.run(
            provider.analyze(
                _request(),
                reference_summary="Registered image reference.",
            )
        )
