from datetime import UTC, datetime

from embedded_copilot.engineering_memory import (
    ApprovalAudit,
    ApprovedEngineeringMemory,
    EngineeringMemoryType,
)
from embedded_copilot.knowledge_writer import (
    artifact_from_approved_memory,
    create_knowledge_writer,
)


def _fact() -> ApprovedEngineeringMemory:
    return ApprovedEngineeringMemory.create(
        memory_id="memory-v30",
        project_id="project-1",
        source_reference="conversation:session-1",
        memory_type=EngineeringMemoryType.DECISION,
        summary="Use ESP32 for the camera node.",
        decision="Choose ESP32.",
        reason="The camera interface is available.",
        confidence=0.9,
        evidence=("conversation:session-1",),
        approval_audit=ApprovalAudit(
            approval_id="approval-v30",
            candidate_fingerprint="sha256:" + "a" * 64,
            reviewer="reviewer-1",
            decision="APPROVED",
            approved_at=datetime(2026, 8, 6, tzinfo=UTC),
        ),
    )


def test_approved_memory_writes_only_the_v30_projection_path(tmp_path) -> None:
    artifact = artifact_from_approved_memory(_fact())
    assert artifact.relative_path == (
        "docs/knowledge/99_Memory/memory-v30-decision.md"
    )
    result = create_knowledge_writer(tmp_path).write_approved_memory(_fact())
    assert result.status.value == "CREATED"
    content = (tmp_path / artifact.relative_path).read_text(encoding="utf-8")
    assert "## Summary" in content
    assert "## Decision" in content
    assert "## Reason" in content
    assert "## Evidence References" in content
    assert "## Related Links" in content
