from __future__ import annotations

from fastapi.testclient import TestClient

from embedded_copilot.api.main import create_app
from embedded_copilot.multimodal_input.adapters.fake import (
    FakeReasoningAdapter,
    FakeVisionAdapter,
)
from embedded_copilot.multimodal_input.contracts import (
    EngineeringInterpretation,
    VisionObservation,
)
from embedded_copilot.services.config import Settings


class _ChatService:
    async def chat(self, request):
        raise AssertionError("chat should not be called")


def _app(vision=None, reasoning=None):
    return create_app(
        service=_ChatService(),
        settings=Settings(_env_file=None),
        vision_port=vision,
        reasoning_port=reasoning,
    )


def _payload() -> dict[str, str]:
    return {
        "project_id": "demo",
        "source_reference": "source:demo",
        "input_type": "IMAGE",
        "context_fingerprint": "sha256:" + "a" * 64,
    }


class _InvalidObservationVision:
    def __init__(self, mode: str) -> None:
        self._mode = mode

    def analyze(self, request):
        observation = FakeVisionAdapter().analyze(request)
        if self._mode == "fingerprint":
            return observation.model_copy(update={"fingerprint": "sha256:" + "0" * 64})
        return observation.model_copy(update={"source_reference": "source:other"})


class _MismatchedReasoning:
    def analyze_observation(self, observation: VisionObservation):
        return EngineeringInterpretation.create(
            interpretation_id="interpretation:other:1",
            observation_reference="observation:other:1",
            summary="This interpretation is deliberately unbound.",
            risk="The binding must be rejected.",
            confidence=0.1,
        )


def test_v29_success_and_reasoning_optional() -> None:
    with TestClient(_app(FakeVisionAdapter(), FakeReasoningAdapter())) as client:
        result = client.post("/api/multimodal/v29/analyze", json=_payload())
    assert result.status_code == 200
    assert result.json()["observation"]["project_id"] == "demo"
    assert result.json()["interpretation"] is not None


def test_v29_missing_ports_and_invalid_request_are_safe() -> None:
    with TestClient(_app()) as client:
        unavailable = client.post("/api/multimodal/v29/analyze", json=_payload())
        invalid = client.post(
            "/api/multimodal/v29/analyze",
            json={**_payload(), "source_reference": "C:\\private\\image.png"},
        )
    assert unavailable.status_code == 503
    assert unavailable.json() == {"error": "MULTIMODAL_UNAVAILABLE"}
    assert invalid.status_code == 422
    assert invalid.json() == {"error": "QUERY_REJECTED"}


def test_v29_default_does_not_fallback_to_legacy_runtime(monkeypatch) -> None:
    import embedded_copilot.api.main as api_main

    def fail_if_composed(*args, **kwargs):
        raise AssertionError("legacy runtime was composed during startup")

    monkeypatch.setattr(api_main, "create_vision_runtime", fail_if_composed)
    monkeypatch.setattr(api_main, "create_reasoning_runtime", fail_if_composed)
    app = create_app(service=_ChatService(), settings=Settings(_env_file=None))

    with TestClient(app) as client:
        result = client.post("/api/multimodal/v29/analyze", json=_payload())

    assert result.status_code == 503
    assert result.json() == {"error": "MULTIMODAL_UNAVAILABLE"}
    assert app.state.multimodal_vision_port is None
    assert app.state.multimodal_reasoning_port is None


def test_v29_rejects_invalid_observation_projection() -> None:
    for mode in ("fingerprint", "context"):
        with TestClient(_app(_InvalidObservationVision(mode))) as client:
            result = client.post("/api/multimodal/v29/analyze", json=_payload())
        assert result.status_code == 422
        assert result.json() == {"error": "QUERY_REJECTED"}


def test_v29_reasoning_failure_does_not_leak_details() -> None:
    class FailingReasoning:
        def analyze_observation(self, observation):
            raise RuntimeError("private/path/provider output")

    with TestClient(_app(FakeVisionAdapter(), FailingReasoning())) as client:
        result = client.post("/api/multimodal/v29/analyze", json=_payload())
    assert result.status_code == 200
    assert result.json()["interpretation"] is None
    assert "private" not in result.text


def test_v29_reasoning_binding_failure_preserves_observation() -> None:
    with TestClient(_app(FakeVisionAdapter(), _MismatchedReasoning())) as client:
        result = client.post("/api/multimodal/v29/analyze", json=_payload())

    assert result.status_code == 200
    assert result.json()["observation"]["observation_id"] == "observation:demo:1"
    assert result.json()["interpretation"] is None
