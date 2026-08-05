from __future__ import annotations

from ..contracts import (
    HardwareReviewCategory,
    HardwareReviewPort,
    HardwareReviewProposal,
    HardwareReviewSeverity,
    HardwareReviewStatus,
)


class FakeHardwareReviewPort(HardwareReviewPort):
    def get_snapshot(self, project_id: str) -> tuple[HardwareReviewProposal, ...]:
        return (
            HardwareReviewProposal.create(
                review_id=f"review:{project_id}:component:1",
                project_id=project_id,
                category=HardwareReviewCategory.COMPONENT,
                severity=HardwareReviewSeverity.MEDIUM,
                summary="Component identity requires human review.",
                evidence_reference=f"design:{project_id}",
                status=HardwareReviewStatus.PROJECTED,
            ),
        )


__all__ = ["FakeHardwareReviewPort"]
