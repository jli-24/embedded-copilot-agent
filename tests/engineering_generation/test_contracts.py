from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_generation import (
    ArtifactGenerationRequest,
    ArtifactType,
    GeneratorBindingMetadata,
    GeneratorType,
    artifact_proposal_fingerprint,
)

from .conftest import proposal_for, request_for


def test_generation_request_is_frozen_strict_and_tuple_only() -> None:
    request = request_for()

    with pytest.raises(ValidationError):
        request.task_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ArtifactGenerationRequest.model_validate(
            {**request.model_dump(mode="python"), "prompt": "hidden reasoning"}
        )
    with pytest.raises(ValidationError):
        ArtifactGenerationRequest(
            **{**request.model_dump(mode="python"), "constraints": []}
        )
    with pytest.raises(ValidationError):
        ArtifactGenerationRequest(
            **{
                **request.model_dump(mode="python"),
                "timestamp": datetime(2026, 8, 4, 9, 0),
            }
        )


@pytest.mark.parametrize("artifact_type", tuple(ArtifactType))
def test_all_artifact_proposals_are_typed_and_fingerprinted(artifact_type) -> None:
    proposal = proposal_for(request_for(artifact_type=artifact_type))

    assert proposal.artifact_type is artifact_type
    with pytest.raises(ValidationError):
        type(proposal).model_validate(
            proposal.model_copy(update={"summary": "Changed proposal."})
        )
    assert (
        artifact_proposal_fingerprint(
            generation_id=proposal.generation_id,
            workflow_id=proposal.workflow_id,
            task_id=proposal.task_id,
            artifact_type=proposal.artifact_type,
            summary=proposal.summary,
            structured_output=proposal.structured_output,
            references=proposal.references,
            metrics=proposal.metrics,
        )
        == proposal.fingerprint
    )


def test_generator_binding_rejects_duplicate_capabilities() -> None:
    with pytest.raises(ValidationError):
        GeneratorBindingMetadata(
            generator_type=GeneratorType.HARDWARE_DESIGN,
            capabilities=("GENERATE_ARTIFACT", "GENERATE_ARTIFACT"),
            fingerprint="sha256:" + "0" * 64,
        )
