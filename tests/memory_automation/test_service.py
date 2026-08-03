from datetime import UTC, datetime

from embedded_copilot.memory_automation import (
    MemoryApprovalProjection,
    MemoryReviewStatus,
    MemorySourceKind,
    MemorySourceProjection,
    VersionMemoryInput,
    create_memory_automation,
)


def test_approval_binds_candidate_fingerprint_without_persistence() -> None:
    source = MemorySourceProjection(
        source_type=MemorySourceKind.ENGINEERING_EVENT,
        source_id="event-1",
        source_reference="event:1",
        source_fingerprint="sha256:" + "b" * 64,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    service = create_memory_automation()
    candidate = service.project(VersionMemoryInput(source=source, summary="safe"))
    approval = MemoryApprovalProjection(
        memory_id=candidate.memory_id,
        candidate_fingerprint=candidate.fingerprint,
        reviewer="reviewer-1",
        decision="APPROVED",
        reviewed_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    approved = service.approve(candidate, approval)
    assert approved.review_status is MemoryReviewStatus.APPROVED
    assert approved.fingerprint != candidate.fingerprint
