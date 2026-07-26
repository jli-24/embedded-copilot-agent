from __future__ import annotations

import asyncio

import httpx
import pytest
from pydantic import ValidationError

from embedded_copilot.core.config import Settings
from embedded_copilot.model_runtime import create_model_runtime


def test_unavailable_status_is_request_triggered_without_network() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"models": []})

    runtime = create_model_runtime(
        Settings(_env_file=None),
        transport=httpx.MockTransport(respond),
    )

    result = asyncio.run(runtime.status_port().status())

    assert result.model_dump(mode="python") == {
        "provider": "unavailable",
        "status": "unavailable",
        "capabilities": (),
        "model": None,
    }
    assert calls == 0


def test_ollama_status_probes_each_request_without_cached_availability() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "edge-model:latest",
                            "model": "edge-model:latest",
                            "modified_at": "2026-07-26T08:00:00Z",
                            "size": 1,
                            "digest": "PRIVATE_DIGEST",
                            "details": {"family": "private-family"},
                        }
                    ]
                },
            )
        return httpx.Response(503, text="PRIVATE_SERVICE_DETAIL")

    runtime = create_model_runtime(
        Settings(
            model_provider="ollama",
            ollama_model="edge-model:latest",
            _env_file=None,
        ),
        transport=httpx.MockTransport(respond),
    )

    available = asyncio.run(runtime.status_port().status())
    unavailable = asyncio.run(runtime.status_port().status())

    assert available.status == "available"
    assert unavailable.status == "unavailable"
    assert calls == 2
    assert available.model_dump(mode="python") == {
        "provider": "ollama",
        "status": "available",
        "capabilities": ("CHAT", "CODE", "REASONING"),
        "model": "edge-model:latest",
    }
    serialized = available.model_dump_json()
    assert "base_url" not in serialized
    assert "digest" not in serialized
    assert "details" not in serialized
    assert "PRIVATE_" not in serialized


def test_model_status_response_is_immutable() -> None:
    runtime = create_model_runtime(Settings(_env_file=None))
    result = asyncio.run(runtime.status_port().status())

    with pytest.raises(ValidationError):
        result.status = "available"
