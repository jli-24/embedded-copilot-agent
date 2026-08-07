from __future__ import annotations

import copy

from .contracts import (
    EngineeringInterpretation,
    EngineeringReasoningPort,
    MultimodalAnalysisProjection,
    VisionModelPort,
    VisionRequest,
    validate_interpretation,
    validate_observation,
    validate_projection,
    validate_request,
)
from .exceptions import MultimodalRejected, MultimodalUnavailable


class MultimodalInputService:
    __slots__ = ("_reasoning", "_vision")

    def __init__(
        self,
        vision: VisionModelPort,
        reasoning: EngineeringReasoningPort | None = None,
    ) -> None:
        if not callable(getattr(vision, "analyze", None)):
            raise TypeError("vision port is invalid")
        if reasoning is not None and not callable(
            getattr(reasoning, "analyze_observation", None)
        ):
            raise TypeError("reasoning port is invalid")
        self._vision = vision
        self._reasoning = reasoning

    def analyze(self, request: VisionRequest) -> MultimodalAnalysisProjection:
        checked_request = validate_request(request)
        try:
            raw_observation = self._vision.analyze(copy.deepcopy(checked_request))
        except (MultimodalUnavailable, MultimodalRejected):
            raise
        except Exception as error:
            raise MultimodalUnavailable() from error
        try:
            observation = validate_observation(raw_observation)
        except (TypeError, ValueError) as error:
            raise MultimodalRejected() from error
        if (
            observation.project_id != checked_request.project_id
            or observation.source_reference != checked_request.source_reference
        ):
            raise MultimodalRejected() from None
        interpretation: EngineeringInterpretation | None = None
        if self._reasoning is not None:
            try:
                interpretation = validate_interpretation(
                    self._reasoning.analyze_observation(copy.deepcopy(observation))
                )
                if interpretation.observation_reference != observation.observation_id:
                    interpretation = None
            except Exception:  # noqa: BLE001 - reasoning output is optional and sanitized
                interpretation = None
        return validate_projection(
            MultimodalAnalysisProjection.create(
                observation=observation,
                interpretation=interpretation,
            )
        )


__all__ = ["MultimodalInputService"]
