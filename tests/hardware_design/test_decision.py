from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_design.approval import (
    DesignApproval,
    DesignApprovalStatus,
)
from embedded_copilot.hardware_design.artifact import HardwareDesignArtifact
from embedded_copilot.hardware_design.decision import (
    DesignDecision,
    DesignDecisionStatus,
)
from embedded_copilot.hardware_design.evidence import DesignEvidence
from embedded_copilot.hardware_design.models import (
    DesignModule,
    HardwareDesignBlueprint,
    PowerTree,
)


def _blueprint() -> HardwareDesignBlueprint:
    return HardwareDesignBlueprint(
        project_name="security-terminal",
        target_platform="ESP32",
        modules=(
            DesignModule(
                name="ESP32-S3",
                description="Controller copied from HardwarePlan.",
                source_ids=("datasheet:esp32-s3",),
            ),
        ),
        power_tree=PowerTree(input="unresolved"),
        source_ids=("datasheet:esp32-s3",),
    )


def _evidence() -> DesignEvidence:
    return DesignEvidence(
        evidence_id="evidence:0123456789abcdef",
        source_id="datasheet:esp32-s3",
        source_type="datasheet",
        location="structured:datasheet",
        content_summary="Structured Datasheet identifies ESP32-S3.",
        confidence=1.0,
    )


def _decision(evidence_id: str = "evidence:0123456789abcdef") -> DesignDecision:
    return DesignDecision(
        decision_id="decision:0123456789abcdef",
        decision_type="component_observation",
        decision="HardwarePlan includes ESP32-S3.",
        reason="The observation is traceable to structured Datasheet evidence.",
        evidence_ids=(evidence_id,),
        confidence=1.0,
        status=DesignDecisionStatus.PROPOSED,
    )


def test_artifact_binds_decisions_to_local_evidence() -> None:
    artifact = HardwareDesignArtifact(
        blueprint=_blueprint(),
        evidence=(_evidence(),),
        decisions=(_decision(),),
        approval=DesignApproval(),
    )

    assert artifact.schema_version == 1
    assert artifact.approval.status is DesignApprovalStatus.PROPOSED
    assert artifact.approval.revision == 1


def test_artifact_rejects_unknown_decision_evidence() -> None:
    with pytest.raises(ValidationError):
        HardwareDesignArtifact(
            blueprint=_blueprint(),
            evidence=(_evidence(),),
            decisions=(_decision("evidence:missing"),),
            approval=DesignApproval(),
        )


def test_artifact_rejects_nested_source_outside_blueprint_sources() -> None:
    evidence = _evidence().model_copy(update={"source_id": "datasheet:other"})
    with pytest.raises(ValidationError):
        HardwareDesignArtifact(
            blueprint=_blueprint(),
            evidence=(evidence,),
            approval=DesignApproval(),
        )


def test_artifact_rejects_blueprint_source_without_local_evidence() -> None:
    with pytest.raises(ValidationError):
        HardwareDesignArtifact(
            blueprint=_blueprint(),
            approval=DesignApproval(),
        )


def test_decision_and_approval_contracts_are_read_only() -> None:
    decision = _decision()
    approval = DesignApproval()

    assert [item.value for item in DesignDecisionStatus] == [
        "PROPOSED",
        "CONFIRMED",
        "REJECTED",
    ]
    assert [item.value for item in DesignApprovalStatus] == [
        "PROPOSED",
        "REVIEWING",
        "APPROVED",
        "REJECTED",
        "MODIFIED",
    ]
    with pytest.raises(ValidationError):
        decision.status = DesignDecisionStatus.CONFIRMED  # type: ignore[misc]
    with pytest.raises(ValidationError):
        approval.status = DesignApprovalStatus.APPROVED  # type: ignore[misc]
