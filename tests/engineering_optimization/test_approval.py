from __future__ import annotations

from datetime import UTC, datetime

from embedded_copilot.engineering_optimization.adapters.fake import (
    FakeOptimizationApprovalPort,
    FakeOptimizationAnalysisPort,
)
from embedded_copilot.engineering_optimization.contracts import (
    OptimizationApprovalRequest,
    OptimizationStatus,
)


def test_approval_binds_finding_identity() -> None:
    finding = FakeOptimizationAnalysisPort().get_snapshot("demo").findings[0]
    request = OptimizationApprovalRequest(
        finding_id=finding.finding_id,
        finding_fingerprint=finding.fingerprint,
        reviewer="reviewer:demo",
        decided_at=datetime.now(UTC),
    )
    approved = FakeOptimizationApprovalPort().approve(request)
    assert approved.status is OptimizationStatus.APPROVED
    assert approved.fingerprint == finding.fingerprint
