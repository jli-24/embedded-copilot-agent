from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import embedded_copilot.engineering_interface as public
from embedded_copilot.engineering_interface import (
    EngineeringProjectProjection,
    EngineeringSessionCreateRequest,
    engineering_project_fingerprint,
)

NOW = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def _project() -> EngineeringProjectProjection:
    references = ("board-esp32-s3",)
    return EngineeringProjectProjection(
        project_id="project-1",
        name="ESP32-S3 Smart Camera",
        summary="A reviewable embedded camera engineering project.",
        reference_ids=references,
        fingerprint=engineering_project_fingerprint(
            project_id="project-1",
            name="ESP32-S3 Smart Camera",
            summary="A reviewable embedded camera engineering project.",
            reference_ids=references,
        ),
    )


def test_public_contracts_are_frozen_strict_and_deterministic() -> None:
    project = _project()
    request = EngineeringSessionCreateRequest(
        session_id="session-1",
        title="Design discussion 1",
        project=project,
        created_at=NOW,
    )

    assert request.project is not project
    assert request.project == project
    assert project.model_dump(mode="json") == _project().model_dump(mode="json")
    with pytest.raises(ValidationError):
        project.name = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineeringProjectProjection.model_validate(
            {**project.model_dump(), "unexpected": "value"}
        )
    with pytest.raises(ValidationError):
        EngineeringProjectProjection(
            project_id="project-1",
            name="ESP32-S3 Smart Camera",
            summary="A reviewable embedded camera engineering project.",
            reference_ids=["board-esp32-s3"],  # type: ignore[arg-type]
            fingerprint=project.fingerprint,
        )


def test_project_projection_rejects_fingerprint_tampering() -> None:
    project = _project()
    with pytest.raises(ValidationError):
        EngineeringProjectProjection.model_validate(
            {**project.model_dump(), "summary": "tampered"}
        )


def test_root_exports_are_strict() -> None:
    expected = {
        "AttachmentProjectionRequest",
        "AttachmentProjectionType",
        "EngineeringAttachmentProjection",
        "EngineeringChatRequest",
        "EngineeringChatRole",
        "EngineeringInterfaceError",
        "EngineeringInterfacePort",
        "EngineeringInterfaceRejected",
        "EngineeringInterfaceRuntime",
        "EngineeringMessageProjection",
        "EngineeringProgressEvent",
        "EngineeringProgressSource",
        "EngineeringProjectProjection",
        "EngineeringSessionCreateRequest",
        "EngineeringSessionSnapshot",
        "EngineeringWorkflowPreparationRequest",
        "EngineeringWorkflowUIProjection",
        "EngineeringWorkflowUnavailable",
        "HumanReviewUIProjection",
        "create_engineering_interface_runtime",
        "engineering_project_fingerprint",
    }
    assert set(public.__all__) == expected
    for forbidden in (
        "_EngineeringInterfaceService",
        "WorkflowAdapter",
        "SessionManager",
    ):
        assert not hasattr(public, forbidden)
