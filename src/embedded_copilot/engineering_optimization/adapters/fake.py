from __future__ import annotations

from ..contracts import (
    OptimizationAnalysis,
    OptimizationAnalysisPort,
    OptimizationApprovalPort,
    OptimizationApprovalRequest,
    OptimizationCategory,
    OptimizationConfidence,
    OptimizationFinding,
    OptimizationStatus,
    OptimizationTarget,
)


def _finding(project_id: str) -> OptimizationFinding:
    return OptimizationFinding.create(
        finding_id=f"finding:{project_id}:1",
        category=OptimizationCategory.PERFORMANCE,
        target=OptimizationTarget.TEST,
        current_state="Projected metrics are available.",
        suggested_direction="Review measured latency before proposing a bounded change.",
        risk="A change requires explicit human review.",
        confidence=OptimizationConfidence.PROJECTED,
        evidence_reference=f"evidence:{project_id}",
        status=OptimizationStatus.REVIEW_REQUIRED,
    )


class FakeOptimizationAnalysisPort(OptimizationAnalysisPort):
    def get_snapshot(self, project_id: str) -> OptimizationAnalysis:
        return OptimizationAnalysis.create(
            project_id=project_id, findings=(_finding(project_id),)
        )


class FakeOptimizationApprovalPort(OptimizationApprovalPort):
    def _decide(
        self, request: OptimizationApprovalRequest, status: OptimizationStatus
    ) -> OptimizationFinding:
        project_id = (
            request.finding_id.split(":", 2)[1]
            if request.finding_id.startswith("finding:")
            else request.finding_id
        )
        finding = _finding(project_id)
        if (
            finding.finding_id != request.finding_id
            or finding.fingerprint != request.finding_fingerprint
        ):
            raise ValueError("finding identity mismatch")
        return OptimizationFinding.create(
            **{**finding.model_dump(mode="python"), "status": status}
        )

    def approve(self, request: OptimizationApprovalRequest) -> OptimizationFinding:
        return self._decide(request, OptimizationStatus.APPROVED)

    def reject(self, request: OptimizationApprovalRequest) -> OptimizationFinding:
        return self._decide(request, OptimizationStatus.REJECTED)


__all__ = ["FakeOptimizationAnalysisPort", "FakeOptimizationApprovalPort"]
