from __future__ import annotations

from typing import Protocol

from ..contracts import (
    EngineeringInterpretation,
    EngineeringReasoningPort,
    VisionObservation,
)
from ..exceptions import MultimodalUnavailable


class DeepSeekReasoningExecutor(Protocol):
    def analyze_projection(
        self, observation: VisionObservation
    ) -> EngineeringInterpretation: ...


class DeepSeekReasoningAdapter(EngineeringReasoningPort):
    def __init__(self, executor: DeepSeekReasoningExecutor | None = None) -> None:
        self._executor = executor

    def analyze_observation(
        self, observation: VisionObservation
    ) -> EngineeringInterpretation:
        if self._executor is None:
            raise MultimodalUnavailable()
        try:
            return self._executor.analyze_projection(observation)
        except MultimodalUnavailable:
            raise
        except Exception as error:
            raise MultimodalUnavailable() from error


__all__ = ["DeepSeekReasoningAdapter", "DeepSeekReasoningExecutor"]
