from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_generation.contracts import FirmwareArtifact
from embedded_copilot.workspace_projection import (
    WorkspaceProjectionRejected,
    WorkspaceProjectionService,
)


def _artifact() -> FirmwareArtifact:
    return FirmwareArtifact.create(
        artifact_id="artifact-1",
        project_id="demo",
        files=("main.c", "CMakeLists.txt"),
        configuration=("proposal_only=true",),
        dependencies=("ESP-IDF",),
        summary="Firmware proposal.",
    )


def test_projection_is_approval_bound_and_contains_no_source() -> None:
    proposal = WorkspaceProjectionService().project(_artifact())
    assert proposal.requires_approval is True
    assert proposal.filenames == ("main.c", "CMakeLists.txt")
    assert "source" not in proposal.model_dump()
    with pytest.raises(ValidationError):
        proposal.filenames += ("changed.c",)  # type: ignore[misc]


def test_projection_revalidates_tampered_artifact() -> None:
    artifact = _artifact()
    tampered = artifact.model_copy(update={"summary": "changed"})
    with pytest.raises(WorkspaceProjectionRejected):
        WorkspaceProjectionService().project(tampered)
