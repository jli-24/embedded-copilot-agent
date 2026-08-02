"""Typed, content-minimized projection from Engineering Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import field_validator, model_validator

from embedded_copilot.engineering_hardware.models import (
    _HardwareContract,
    _identifier,
    _utc,
)
from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringProjectPlan,
    EngineeringRequirementDocument,
    EvidenceStatus,
)


class HardwareEngineeringRequest(_HardwareContract):
    proposal_id: str
    requirement: EngineeringRequirementDocument
    plan: EngineeringProjectPlan
    context: EngineeringContextSnapshot
    proposed_at: datetime

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )

    @model_validator(mode="after")
    def validate_binding(self) -> HardwareEngineeringRequest:
        project_id = self.requirement.project_id
        if (
            project_id != self.plan.project_id
            or project_id != self.context.project.project_id
        ):
            raise ValueError("project binding mismatch")
        if (
            self.plan.requirement_fingerprint != self.requirement.fingerprint
            or self.context.requirement_fingerprint != self.requirement.fingerprint
            or self.context.plan_fingerprint != self.plan.fingerprint
        ):
            raise ValueError("intelligence fingerprint binding mismatch")
        if not any(task.domain.value == "HARDWARE" for task in self.plan.tasks):
            raise ValueError("hardware planning task is required")
        return self


@dataclass(frozen=True, slots=True)
class _ConstraintInput:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class _EvidenceInput:
    evidence_id: str
    source_type: str
    fact_type: str
    key: str
    value: str
    reference_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class _HardwareEngineeringInput:
    proposal_id: str
    project_id: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    product: str
    functional_requirements: tuple[str, ...]
    hardware_constraints: tuple[_ConstraintInput, ...]
    power_requirements: tuple[str, ...]
    communication_requirements: tuple[str, ...]
    verified_evidence: tuple[_EvidenceInput, ...]
    proposed_at: datetime


def project_intelligence_input(value: object) -> _HardwareEngineeringInput:
    if type(value) is not HardwareEngineeringRequest:
        raise TypeError("typed hardware engineering request is required")
    copied = value.model_copy(deep=True)
    checked = HardwareEngineeringRequest.model_validate(copied)
    evidence = tuple(
        _EvidenceInput(
            evidence_id=item.evidence_id,
            source_type=item.source_type.value,
            fact_type=item.fact_type,
            key=item.key,
            value=item.value,
            reference_ids=tuple(item.reference_ids),
            fingerprint=item.fingerprint,
        )
        for item in checked.context.evidence
        if item.status is EvidenceStatus.VERIFIED
    )
    return _HardwareEngineeringInput(
        proposal_id=checked.proposal_id,
        project_id=checked.requirement.project_id,
        requirement_fingerprint=checked.requirement.fingerprint,
        plan_fingerprint=checked.plan.fingerprint,
        context_fingerprint=checked.context.fingerprint,
        product=checked.requirement.product,
        functional_requirements=tuple(checked.requirement.functional_requirements),
        hardware_constraints=tuple(
            _ConstraintInput(key=item.key, value=item.value)
            for item in checked.requirement.hardware_constraints
        ),
        power_requirements=tuple(checked.requirement.power_requirements),
        communication_requirements=tuple(
            checked.requirement.communication_requirements
        ),
        verified_evidence=evidence,
        proposed_at=checked.proposed_at,
    )
