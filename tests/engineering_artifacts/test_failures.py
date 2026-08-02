from __future__ import annotations

import pytest

from embedded_copilot.engineering_artifacts import (
    EngineeringArtifactRejected,
    create_engineering_artifact_runtime,
)


def test_tampered_nested_input_is_rejected(generation_request) -> None:
    forged = generation_request.context.model_copy(
        update={"fingerprint": "sha256:" + "0" * 64}, deep=True
    )
    request = generation_request.model_copy(update={"context": forged}, deep=True)
    with pytest.raises(EngineeringArtifactRejected, match="request rejected"):
        create_engineering_artifact_runtime().engineering_artifact_port().generate(
            request
        )


def test_cross_project_validation_binding_is_rejected(generation_request) -> None:
    validation = generation_request.validation_report.model_copy(
        update={"project_id": "other-project"}, deep=True
    )
    request = generation_request.model_copy(
        update={"validation_report": validation}, deep=True
    )
    with pytest.raises(EngineeringArtifactRejected, match="request rejected"):
        create_engineering_artifact_runtime().engineering_artifact_port().generate(
            request
        )


def test_untyped_request_is_rejected() -> None:
    with pytest.raises(EngineeringArtifactRejected, match="request rejected"):
        create_engineering_artifact_runtime().engineering_artifact_port().generate({})
