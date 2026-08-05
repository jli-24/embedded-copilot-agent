from __future__ import annotations

from embedded_copilot.debug_analysis.adapters.fake import FakeDebugAnalysisPort

from ..contracts import OptimizationPort
from ..service import OptimizationService


class FakeOptimizationPort(OptimizationPort):
    def get_snapshot(self, project_id: str):
        debug_snapshot = FakeDebugAnalysisPort().get_snapshot(project_id)
        return OptimizationService().propose(debug_snapshot.findings[0])


__all__ = ["FakeOptimizationPort"]
