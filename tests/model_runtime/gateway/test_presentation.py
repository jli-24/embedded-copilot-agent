from __future__ import annotations

import asyncio
import json

import httpx

from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    DatasheetContext,
    FileContext,
    InterfaceContextCandidate,
)
from embedded_copilot.core.config import Settings
from embedded_copilot.model_runtime import create_model_runtime
from embedded_copilot.reasoning_runtime import (
    ReasoningContextSnapshot,
    ReasoningRequest,
    SourceType,
    create_reasoning_runtime,
)
from embedded_copilot.reasoning_runtime.snapshot import snapshot_fingerprint


def _request() -> ReasoningRequest:
    datasheet = DatasheetContext(
        file_id="file:1",
        component_candidate=ComponentContextCandidate(
            family="ESP32",
            model="ESP32-S3",
        ),
        interfaces=(InterfaceContextCandidate(name="SPI"),),
    )
    file_summary = FileContext(
        file_id="file:1",
        document_type=ContextDocumentType.PDF,
        page_count=10,
    )
    fields = {
        "schema_version": "1.0",
        "context_id": "context:0123456789abcdef01234567",
        "task_intent": "PRIVATE TASK ESP32 WiFi review.",
        "reference_ids": ("file:1",),
        "source_types": (SourceType.DATASHEET,),
        "datasheet_candidates": (datasheet,),
        "file_summaries": (file_summary,),
        "vision_refs": (),
    }
    snapshot = ReasoningContextSnapshot(
        snapshot_fingerprint=snapshot_fingerprint(**fields),
        **fields,
    )
    return ReasoningRequest(
        session_id="session:1",
        trace_id="trace:1",
        context_snapshot=snapshot,
    )


def test_model_adds_only_validated_presentation_patch() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "response": "Additional verification may be required.",
                "done_reason": "stop",
            },
        )

    model_runtime = create_model_runtime(
        Settings(
            model_provider="ollama",
            ollama_model="presentation-model",
            _env_file=None,
        ),
        transport=httpx.MockTransport(respond),
    )
    base = create_reasoning_runtime().reasoning_port()
    request = _request()
    canonical = asyncio.run(base.analyze(request))

    enhanced = asyncio.run(model_runtime.enhance_reasoning_port(base).analyze(request))

    assert enhanced.reasoning_summary.presentation_summary == (
        "Additional verification may be required."
    )
    enhanced_payload = enhanced.model_dump(mode="python")
    canonical_payload = canonical.model_dump(mode="python")
    enhanced_payload["reasoning_summary"]["presentation_summary"] = None
    assert enhanced_payload == canonical_payload
    payload = json.loads(requests[0].content)
    assert "PRIVATE TASK" not in payload["prompt"]
    assert "WiFi" not in payload["prompt"]


def test_model_fact_promotion_is_rejected_without_canonical_change() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"response": "The SPI connection is wrong.", "done_reason": "stop"},
        )

    model_runtime = create_model_runtime(
        Settings(
            model_provider="ollama",
            ollama_model="unsafe-model",
            _env_file=None,
        ),
        transport=httpx.MockTransport(respond),
    )
    base = create_reasoning_runtime().reasoning_port()
    request = _request()

    canonical = asyncio.run(base.analyze(request))
    enhanced = asyncio.run(model_runtime.enhance_reasoning_port(base).analyze(request))

    assert enhanced == canonical
    assert enhanced.reasoning_summary.presentation_summary is None


def test_unavailable_model_falls_back_without_network_or_semantic_change() -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"response": "Unexpected."})

    model_runtime = create_model_runtime(
        Settings(_env_file=None),
        transport=httpx.MockTransport(respond),
    )
    base = create_reasoning_runtime().reasoning_port()
    request = _request()

    canonical = asyncio.run(base.analyze(request))
    enhanced = asyncio.run(model_runtime.enhance_reasoning_port(base).analyze(request))

    assert enhanced == canonical
    assert calls == 0
