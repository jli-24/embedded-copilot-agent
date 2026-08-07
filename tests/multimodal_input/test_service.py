from __future__ import annotations

import pytest

from embedded_copilot.multimodal_input.adapters.fake import (
    FakeReasoningAdapter,
    FakeVisionAdapter,
)
from embedded_copilot.multimodal_input.contracts import InputType, VisionRequest
from embedded_copilot.multimodal_input.service import MultimodalInputService


def _request() -> VisionRequest:
    return VisionRequest.create(
        project_id="demo",
        source_reference="source:demo",
        input_type=InputType.DOCUMENT,
        context_fingerprint="sha256:" + "a" * 64,
    )


def test_service_binds_observation_and_optional_interpretation() -> None:
    request = _request()
    projection = MultimodalInputService(
        FakeVisionAdapter(), FakeReasoningAdapter()
    ).analyze(request)
    assert projection.observation.project_id == request.project_id
    assert projection.interpretation is not None
    assert (
        projection.interpretation.observation_reference
        == projection.observation.observation_id
    )


def test_service_keeps_observation_when_reasoning_is_missing() -> None:
    projection = MultimodalInputService(FakeVisionAdapter()).analyze(_request())
    assert projection.observation.content
    assert projection.interpretation is None


class _CountingVision(FakeVisionAdapter):
    def __init__(self) -> None:
        self.calls = 0
        self.requests = []

    def analyze(self, request):
        self.calls += 1
        self.requests.append(request)
        return super().analyze(request)


class _FailingVision:
    def analyze(self, request):
        raise RuntimeError("provider details must not escape")


def test_service_deep_copies_request_and_invokes_vision_once() -> None:
    vision = _CountingVision()
    request = _request()
    projection = MultimodalInputService(vision).analyze(request)

    assert vision.calls == 1
    assert vision.requests[0] == request
    assert vision.requests[0] is not request
    assert projection.observation.project_id == request.project_id


def test_service_maps_vision_execution_failure_to_unavailable() -> None:
    from embedded_copilot.multimodal_input.exceptions import MultimodalUnavailable

    with pytest.raises(MultimodalUnavailable):
        MultimodalInputService(_FailingVision()).analyze(_request())
