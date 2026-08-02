"""Typed, content-minimized Hardware Validation input projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import field_validator, model_validator

from embedded_copilot.engineering_firmware import (
    FirmwareBuildArtifactType,
    FirmwareEngineeringProposal,
    FirmwareTaskType,
)
from embedded_copilot.engineering_hardware import HardwareEngineeringProposal
from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringRequirementDocument,
)
from embedded_copilot.engineering_validation.models import (
    EvidenceSnapshot,
    _ValidationContract,
    _identifier,
    _utc,
)


class HardwareValidationRequest(_ValidationContract):
    proposal_id: str
    hardware_proposal: HardwareEngineeringProposal
    firmware_proposal: FirmwareEngineeringProposal
    requirement: EngineeringRequirementDocument
    context: EngineeringContextSnapshot
    evidence_snapshot: EvidenceSnapshot
    proposed_at: datetime

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )

    @model_validator(mode="after")
    def validate_binding(self) -> HardwareValidationRequest:
        project_id = self.requirement.project_id
        if not all(
            value == project_id
            for value in (
                self.context.project.project_id,
                self.hardware_proposal.project_id,
                self.firmware_proposal.project_id,
                self.evidence_snapshot.project_id,
            )
        ):
            raise ValueError("validation project binding mismatch")
        if (
            self.context.requirement_fingerprint != self.requirement.fingerprint
            or self.hardware_proposal.requirement_fingerprint
            != self.requirement.fingerprint
            or self.firmware_proposal.requirement_fingerprint
            != self.requirement.fingerprint
            or self.evidence_snapshot.requirement_fingerprint
            != self.requirement.fingerprint
            or self.hardware_proposal.plan_fingerprint != self.context.plan_fingerprint
            or self.firmware_proposal.plan_fingerprint != self.context.plan_fingerprint
            or self.hardware_proposal.context_fingerprint != self.context.fingerprint
            or self.firmware_proposal.context_fingerprint != self.context.fingerprint
            or self.evidence_snapshot.context_fingerprint != self.context.fingerprint
            or self.firmware_proposal.hardware_proposal_fingerprint
            != self.hardware_proposal.fingerprint
            or self.evidence_snapshot.hardware_proposal_fingerprint
            != self.hardware_proposal.fingerprint
            or self.evidence_snapshot.firmware_proposal_fingerprint
            != self.firmware_proposal.fingerprint
        ):
            raise ValueError("validation fingerprint binding mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _ValidationInput:
    proposal_id: str
    project_id: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    baseline: EvidenceSnapshot
    functional_requirements: tuple[str, ...]
    communication_requirements: tuple[str, ...]
    power_requirements: tuple[str, ...]
    component_references: tuple[tuple[str, str], ...]
    task_types: tuple[str, ...]
    expected_build_artifact: str
    proposed_at: datetime


def project_validation_input(value: object) -> _ValidationInput:
    if type(value) is not HardwareValidationRequest:
        raise TypeError("typed hardware validation request is required")
    if (
        type(value.hardware_proposal) is not HardwareEngineeringProposal
        or type(value.firmware_proposal) is not FirmwareEngineeringProposal
        or type(value.requirement) is not EngineeringRequirementDocument
        or type(value.context) is not EngineeringContextSnapshot
        or type(value.evidence_snapshot) is not EvidenceSnapshot
    ):
        raise TypeError("typed hardware validation inputs are required")
    copied = value.model_copy(deep=True)
    checked = HardwareValidationRequest.model_validate(copied)
    return _ValidationInput(
        proposal_id=checked.proposal_id,
        project_id=checked.requirement.project_id,
        hardware_proposal_fingerprint=checked.hardware_proposal.fingerprint,
        firmware_proposal_fingerprint=checked.firmware_proposal.fingerprint,
        requirement_fingerprint=checked.requirement.fingerprint,
        plan_fingerprint=checked.context.plan_fingerprint,
        context_fingerprint=checked.context.fingerprint,
        baseline=checked.evidence_snapshot.model_copy(deep=True),
        functional_requirements=tuple(checked.requirement.functional_requirements),
        communication_requirements=tuple(
            checked.requirement.communication_requirements
        ),
        power_requirements=tuple(checked.requirement.power_requirements),
        component_references=tuple(
            sorted(
                (item.requirement_key, item.component_reference)
                for item in checked.hardware_proposal.component_selection.items
            )
        ),
        task_types=tuple(
            item.task_type.value
            for item in checked.firmware_proposal.task_architecture.tasks
            if item.task_type in tuple(FirmwareTaskType)
        ),
        expected_build_artifact=(
            checked.firmware_proposal.build.expected_artifact_type.value
            if checked.firmware_proposal.build.expected_artifact_type
            is not FirmwareBuildArtifactType.UNRESOLVED
            else FirmwareBuildArtifactType.UNRESOLVED.value
        ),
        proposed_at=checked.proposed_at,
    )
