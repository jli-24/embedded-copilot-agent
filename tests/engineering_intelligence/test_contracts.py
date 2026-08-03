from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.engineering_intelligence import (
    EngineeringContextInputProjection,
    EngineeringContextSnapshot,
    EvidenceClaim,
    EvidenceSourceType,
    EvidenceTrustBasis,
    ContextStage,
    RequirementProjection,
    build_context_snapshot,
)


def _input() -> EngineeringContextInputProjection:
    return EngineeringContextInputProjection(
        project_id="project-1",
        project_name="ESP32 Camera",
        stage=ContextStage.PCB_DESIGN,
        decision_topic="camera interface",
        constraints=("low power", "GPIO limited"),
        requirements=(
            RequirementProjection(
                requirement_id="req-1",
                summary="Select a camera interface",
            ),
        ),
    )


def test_context_is_frozen_strict_and_fingerprinted() -> None:
    snapshot = build_context_snapshot(_input())
    assert snapshot.context_fingerprint.startswith("sha256:")
    assert len(snapshot.context_fingerprint) == 71
    with pytest.raises(ValidationError):
        snapshot.project_id = "changed"
    with pytest.raises(ValidationError):
        EngineeringContextSnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "unexpected": True}
        )
    with pytest.raises(ValidationError):
        EngineeringContextSnapshot.model_validate(
            {
                **snapshot.model_dump(mode="python"),
                "context_fingerprint": "sha256:" + "0" * 64,
            }
        )


def test_context_input_rejects_list_and_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.DEBUG,
            decision_topic="fault",
            constraints=["unsafe"],  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.DEBUG,
            decision_topic="fault",
            constraints=(),
            build_observations=(
                {
                    "observation_id": "build-1",
                    "status": "FAILED",
                    "observed_at": datetime(2026, 1, 1),
                },
            ),  # type: ignore[arg-type]
        )


def test_evidence_is_projection_only_and_deterministic() -> None:
    from embedded_copilot.engineering_intelligence import build_evidence

    evidence = build_evidence(
        evidence_id="evidence-1",
        source_type=EvidenceSourceType.DATASHEET,
        trust_basis=EvidenceTrustBasis.PROJECTED,
        summary="SPI interface candidate",
        reference_id="datasheet-1",
        confidence=0.5,
        source_rank=0,
        claim=EvidenceClaim(
            subject="camera", parameter="interface", value="SPI", unit=""
        ),
    )
    assert evidence.model_dump(mode="json") == evidence.model_dump(mode="json")
    assert "payload" not in evidence.model_dump()


def test_context_fingerprint_is_repeatable_and_input_is_unchanged() -> None:
    value = _input()
    before = value.model_dump(mode="json")
    snapshots = tuple(build_context_snapshot(value) for _ in range(100))
    assert len({item.context_fingerprint for item in snapshots}) == 1
    assert value.model_dump(mode="json") == before
