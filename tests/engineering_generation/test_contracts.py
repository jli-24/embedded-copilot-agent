from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_generation.contracts import (
    FirmwareArtifact,
    GenerationSnapshot,
    GenerationStatus,
)


def _firmware() -> FirmwareArtifact:
    return FirmwareArtifact.create(
        artifact_id="artifact-fw-1",
        project_id="project-1",
        files=("main.c", "CMakeLists.txt", "component.yaml", "README.md"),
        configuration=("ESP-IDF project proposal",),
        dependencies=("ESP-IDF",),
        summary="Firmware project proposal for review.",
    )


def test_contracts_are_frozen_strict_and_fingerprinted() -> None:
    artifact = _firmware()
    assert artifact.fingerprint.startswith("sha256:")
    with pytest.raises(ValidationError):
        artifact.summary = "changed"
    with pytest.raises(ValidationError):
        FirmwareArtifact.model_validate(
            {**artifact.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        FirmwareArtifact.model_validate(
            {**artifact.model_dump(mode="python"), "fingerprint": "sha256:" + "0" * 64}
        )
    with pytest.raises(ValidationError):
        FirmwareArtifact.model_validate(
            {**artifact.model_dump(mode="python"), "files": ["main.c"]}
        )


def test_snapshot_preserves_artifact_order_and_rejects_duplicates() -> None:
    artifact = _firmware()
    snapshot = GenerationSnapshot.create(
        project_id="project-1",
        status=GenerationStatus.REVIEW_REQUIRED,
        artifacts=(artifact,),
    )
    assert snapshot.artifacts == (artifact,)
    with pytest.raises(ValidationError):
        GenerationSnapshot.create(
            project_id="project-1",
            status=GenerationStatus.REVIEW_REQUIRED,
            artifacts=(artifact, artifact),
        )


def test_sensitive_names_and_paths_are_rejected() -> None:
    with pytest.raises(ValidationError):
        FirmwareArtifact.create(
            artifact_id="artifact-fw-1",
            project_id="project-1",
            files=("../main.c",),
            configuration=(),
            dependencies=(),
            summary="proposal",
        )
    with pytest.raises(ValidationError):
        FirmwareArtifact.create(
            artifact_id="artifact-fw-1",
            project_id="project-1",
            files=("main.c",),
            configuration=("api_key=secret",),
            dependencies=(),
            summary="proposal",
        )
