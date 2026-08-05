from __future__ import annotations

import copy

from .contracts import (
    DebugAnalysisPort,
    DebugAnalysisSnapshot,
    DebugAnalyzerPort,
    DebugInputSnapshot,
    validate_analysis_snapshot,
)
from .exceptions import DebugAnalysisRejected


class DebugAnalysisService:
    __slots__ = ("_analyzer",)

    def __init__(self, analyzer: DebugAnalyzerPort) -> None:
        if not isinstance(analyzer, DebugAnalyzerPort):
            raise TypeError("debug analyzer port is invalid")
        self._analyzer = analyzer

    def analyze(self, value: DebugInputSnapshot) -> DebugAnalysisSnapshot:
        try:
            checked = DebugInputSnapshot.model_validate(copy.deepcopy(value))
            result = self._analyzer.analyze(copy.deepcopy(checked))
            snapshot = validate_analysis_snapshot(result)
            if (
                snapshot.project_id != checked.project_id
                or snapshot.failure_reference != checked.failure_reference
            ):
                raise ValueError("debug analysis identity mismatch")
            return snapshot
        except Exception as error:
            if isinstance(error, DebugAnalysisRejected):
                raise
            raise DebugAnalysisRejected() from error


__all__ = ["DebugAnalysisService"]
