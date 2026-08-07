from __future__ import annotations

from ..contracts import (
    EngineeringInterpretation,
    EngineeringReasoningPort,
    VisionModelPort,
    VisionObservation,
    VisionRequest,
)


class FakeVisionAdapter(VisionModelPort):
    def analyze(self, request: VisionRequest) -> VisionObservation:
        return VisionObservation.create(
            observation_id=f"observation:{request.project_id}:1",
            project_id=request.project_id,
            source_reference=request.source_reference,
            observation_type=request.input_type,
            content=("ESP32-S3 component observed", "SPI interface observed"),
            confidence=0.82,
        )


class FakeReasoningAdapter(EngineeringReasoningPort):
    def analyze_observation(
        self, observation: VisionObservation
    ) -> EngineeringInterpretation:
        return EngineeringInterpretation.create(
            interpretation_id=f"interpretation:{observation.project_id}:1",
            observation_reference=observation.observation_id,
            summary="The projected observation indicates an embedded controller and SPI interface.",
            risk="Electrical connectivity still requires engineering verification.",
            confidence=0.70,
        )


__all__ = ["FakeReasoningAdapter", "FakeVisionAdapter"]
