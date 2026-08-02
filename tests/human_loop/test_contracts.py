from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_generation import (
    ArtifactProposal,
    ArtifactType,
    GenerationContextReference,
    GenerationReferenceType,
    HardwareDesignStructuredOutput,
    artifact_proposal_fingerprint,
)
from embedded_copilot.human_loop import (
    HumanReviewDecision,
    HumanReviewRequest,
    ProposalProjection,
    project_proposal_projection,
)

from .conftest import NOW, proposal_projection


def test_proposal_projection_is_frozen_strict_and_fingerprinted() -> None:
    proposal = proposal_projection()

    with pytest.raises(ValidationError):
        proposal.summary = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ProposalProjection.model_validate(
            {**proposal.model_dump(mode="python"), "artifact_body": "unsafe"}
        )
    with pytest.raises(ValidationError):
        ProposalProjection(
            **{**proposal.model_dump(mode="python"), "reference_ids": []}
        )
    with pytest.raises(ValidationError):
        ProposalProjection.model_validate(
            proposal.model_copy(update={"summary": "tampered"})
        )


def test_review_request_normalizes_utc_and_rejects_extra_fields() -> None:
    request = HumanReviewRequest(
        proposal_id="proposal-1",
        reviewer="engineer-1",
        decision=HumanReviewDecision.APPROVED,
        review_comment=None,
        timestamp=NOW,
    )

    assert request.timestamp.utcoffset().total_seconds() == 0
    with pytest.raises(ValidationError):
        HumanReviewRequest.model_validate(
            {**request.model_dump(mode="python"), "approval_bypass": True}
        )
    with pytest.raises(ValidationError):
        HumanReviewRequest(
            proposal_id="proposal-1",
            reviewer="engineer-1",
            decision=HumanReviewDecision.APPROVED,
            review_comment=None,
            timestamp=datetime(2026, 8, 6, 9, 0),
        )


def test_changes_requested_requires_human_comment() -> None:
    with pytest.raises(ValidationError):
        HumanReviewRequest(
            proposal_id="proposal-1",
            reviewer="engineer-1",
            decision=HumanReviewDecision.CHANGES_REQUESTED,
            review_comment=None,
            timestamp=NOW,
        )


def test_engineering_proposal_projects_metadata_without_artifact_body() -> None:
    values = {
        "generation_id": "generation-1",
        "workflow_id": "workflow-1",
        "task_id": "task-1",
        "artifact_type": ArtifactType.HARDWARE_DESIGN,
        "summary": "Generated proposal requires engineering review.",
        "structured_output": HardwareDesignStructuredOutput(
            mcu="ESP32-S3",
            peripherals=("CAMERA",),
            communications=("WIFI",),
            power_architecture="3V3_REGULATED",
        ),
        "references": (
            GenerationContextReference(
                reference_type=GenerationReferenceType.DATASHEET_REFERENCE,
                reference_id="datasheet-reference-1",
            ),
        ),
        "metrics": (),
    }
    proposal = ArtifactProposal(
        **values,
        fingerprint=artifact_proposal_fingerprint(**values),
    )

    projection = project_proposal_projection(
        proposal,
        proposal_id="proposal-1",
        artifact_version=1,
    )

    assert projection.reference_ids == ("datasheet-reference-1",)
    serialized = projection.model_dump(mode="json")
    assert "structured_output" not in serialized
    assert "metrics" not in serialized
    assert "generation_id" not in serialized
