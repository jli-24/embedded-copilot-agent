from datetime import UTC, datetime

import pytest

from embedded_copilot.knowledge_writer import artifact_from_candidate, create_knowledge_writer
from embedded_copilot.memory_automation import (
    MemoryApprovalProjection,
    MemorySourceKind,
    MemorySourceProjection,
    VersionMemoryInput,
    create_memory_automation,
)


def test_writer_only_writes_approved_projection(tmp_path) -> None:
    source = MemorySourceProjection(
        source_type=MemorySourceKind.BUILD_OBSERVATION,
        source_id="build-1",
        source_reference="build:1",
        source_fingerprint="sha256:" + "c" * 64,
        observed_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    service = create_memory_automation()
    candidate = service.project(
        VersionMemoryInput(source=source, summary="Build passed")
    )
    writer = create_knowledge_writer(tmp_path)
    with pytest.raises(ValueError):
        artifact_from_candidate(candidate)
    approved = service.approve(
        candidate,
        MemoryApprovalProjection(
            memory_id=candidate.memory_id,
            candidate_fingerprint=candidate.fingerprint,
            reviewer="reviewer-1",
            decision="APPROVED",
            reviewed_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
    )
    result = writer.write(artifact_from_candidate(approved))
    assert result.status.value == "CREATED"
    target = tmp_path / "docs" / "knowledge" / (
        f"{candidate.memory_id}-build_observation.md"
    )
    assert target.exists()
    assert "Build passed" in target.read_text(encoding="utf-8")
