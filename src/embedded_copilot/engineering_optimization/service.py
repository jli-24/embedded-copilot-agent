from __future__ import annotations

import copy

from .contracts import OptimizationAnalysis, OptimizationAnalysisPort, validate_analysis
from .exceptions import OptimizationRejected
from .models import identifier


class EngineeringOptimizationService:
    __slots__ = ("_port",)

    def __init__(self, port: OptimizationAnalysisPort) -> None:
        if not isinstance(port, OptimizationAnalysisPort):
            raise TypeError("optimization analysis port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> OptimizationAnalysis | None:
        try:
            project = identifier(project_id, field="project_id")
            value = self._port.get_snapshot(copy.deepcopy(project))
            if value is None:
                return None
            checked = validate_analysis(value)
            if checked.project_id != project:
                raise ValueError("project binding mismatch")
            return checked
        except Exception as error:
            raise OptimizationRejected() from error


__all__ = ["EngineeringOptimizationService"]
