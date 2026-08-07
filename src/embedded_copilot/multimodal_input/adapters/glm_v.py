from __future__ import annotations

from typing import Protocol

from ..contracts import VisionModelPort, VisionObservation, VisionRequest
from ..exceptions import MultimodalUnavailable


class GLMVisionExecutor(Protocol):
    def analyze_projection(self, request: VisionRequest) -> VisionObservation: ...


class GLMVisionAdapter(VisionModelPort):
    def __init__(self, executor: GLMVisionExecutor | None = None) -> None:
        self._executor = executor

    def analyze(self, request: VisionRequest) -> VisionObservation:
        if self._executor is None:
            raise MultimodalUnavailable()
        try:
            return self._executor.analyze_projection(request)
        except MultimodalUnavailable:
            raise
        except Exception as error:
            raise MultimodalUnavailable() from error


__all__ = ["GLMVisionAdapter", "GLMVisionExecutor"]
