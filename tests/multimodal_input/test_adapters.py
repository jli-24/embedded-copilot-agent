from __future__ import annotations

import pytest

from embedded_copilot.multimodal_input.adapters.deepseek import DeepSeekReasoningAdapter
from embedded_copilot.multimodal_input.adapters.glm_v import GLMVisionAdapter
from embedded_copilot.multimodal_input.contracts import (
    InputType,
    VisionObservation,
    VisionRequest,
)
from embedded_copilot.multimodal_input.exceptions import MultimodalUnavailable


def _request() -> VisionRequest:
    return VisionRequest.create(
        project_id="demo",
        source_reference="source:demo",
        input_type=InputType.IMAGE,
        context_fingerprint="sha256:" + "a" * 64,
    )


def _observation() -> VisionObservation:
    return VisionObservation.create(
        observation_id="observation:demo:1",
        project_id="demo",
        source_reference="source:demo",
        observation_type=InputType.IMAGE,
        content=("component observed",),
        confidence=0.8,
    )


def test_glm_v_without_executor_is_unavailable() -> None:
    with pytest.raises(MultimodalUnavailable):
        GLMVisionAdapter().analyze(_request())


def test_deepseek_without_executor_is_unavailable() -> None:
    with pytest.raises(MultimodalUnavailable):
        DeepSeekReasoningAdapter().analyze_observation(_observation())
