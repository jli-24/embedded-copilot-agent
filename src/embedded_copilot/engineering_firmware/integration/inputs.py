"""Typed, content-minimized Firmware Engineering input projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import field_validator, model_validator

from embedded_copilot.engineering_firmware.models import (
    FirmwareBuildSystem,
    FirmwarePlatformProfile,
    FirmwarePlatformProjection,
    FirmwarePlatformStatus,
    FirmwareToolchainRequirement,
    _FirmwareContract,
    _identifier,
    _utc,
)
from embedded_copilot.engineering_hardware import HardwareEngineeringProposal
from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringRequirementDocument,
    EvidenceStatus,
)


class FirmwareEngineeringRequest(_FirmwareContract):
    proposal_id: str
    hardware_proposal: HardwareEngineeringProposal
    requirement: EngineeringRequirementDocument
    context: EngineeringContextSnapshot
    platform: FirmwarePlatformProjection
    proposed_at: datetime

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )

    @model_validator(mode="after")
    def validate_binding(self) -> FirmwareEngineeringRequest:
        if (
            self.requirement.project_id != self.hardware_proposal.project_id
            or self.requirement.project_id != self.context.project.project_id
            or self.requirement.project_id != self.platform.project_id
        ):
            raise ValueError("firmware project binding mismatch")
        if (
            self.hardware_proposal.requirement_fingerprint
            != self.requirement.fingerprint
            or self.context.requirement_fingerprint != self.requirement.fingerprint
            or self.hardware_proposal.plan_fingerprint != self.context.plan_fingerprint
            or self.hardware_proposal.context_fingerprint != self.context.fingerprint
            or self.platform.requirement_fingerprint != self.requirement.fingerprint
            or self.platform.hardware_proposal_fingerprint
            != self.hardware_proposal.fingerprint
            or self.platform.context_fingerprint != self.context.fingerprint
        ):
            raise ValueError("firmware fingerprint binding mismatch")
        verified = {
            item.evidence_id: item
            for item in self.context.evidence
            if item.status is EvidenceStatus.VERIFIED
        }
        for item in self.hardware_proposal.evidence_trace:
            source = verified.get(item.evidence_id)
            if source is None or source.fingerprint != item.source_fingerprint:
                raise ValueError("hardware evidence binding mismatch")
        if self.platform.status is FirmwarePlatformStatus.SUPPORTED:
            for evidence_id in self.platform.evidence_ids:
                source = verified.get(evidence_id)
                if (
                    source is None
                    or source.fact_type != "FIRMWARE_PLATFORM_PROFILE"
                    or source.value != self.platform.platform_profile.value
                ):
                    raise ValueError("platform evidence binding mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _ComponentInput:
    component_reference: str
    requirement_key: str
    status: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _InterfaceInput:
    interface_id: str
    protocol: str
    component_reference: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _EvidenceInput:
    evidence_id: str
    source_type: str
    fact_type: str
    reference_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class _PlatformInput:
    projection: FirmwarePlatformProjection
    profile: FirmwarePlatformProfile
    build_system: FirmwareBuildSystem
    toolchain_requirement: FirmwareToolchainRequirement
    status: FirmwarePlatformStatus
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _FirmwareEngineeringInput:
    proposal_id: str
    project_id: str
    hardware_proposal_fingerprint: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    platform: _PlatformInput
    functional_requirements: tuple[str, ...]
    software_constraints: tuple[str, ...]
    communication_requirements: tuple[str, ...]
    components: tuple[_ComponentInput, ...]
    interfaces: tuple[_InterfaceInput, ...]
    hardware_finding_codes: tuple[str, ...]
    verified_evidence: tuple[_EvidenceInput, ...]
    proposed_at: datetime


def project_firmware_input(value: object) -> _FirmwareEngineeringInput:
    if type(value) is not FirmwareEngineeringRequest:
        raise TypeError("typed firmware engineering request is required")
    if (
        type(value.hardware_proposal) is not HardwareEngineeringProposal
        or type(value.requirement) is not EngineeringRequirementDocument
        or type(value.context) is not EngineeringContextSnapshot
        or type(value.platform) is not FirmwarePlatformProjection
    ):
        raise TypeError("typed firmware engineering inputs are required")
    copied = value.model_copy(deep=True)
    checked = FirmwareEngineeringRequest.model_validate(copied)
    return _FirmwareEngineeringInput(
        proposal_id=checked.proposal_id,
        project_id=checked.requirement.project_id,
        hardware_proposal_fingerprint=checked.hardware_proposal.fingerprint,
        requirement_fingerprint=checked.requirement.fingerprint,
        plan_fingerprint=checked.hardware_proposal.plan_fingerprint,
        context_fingerprint=checked.context.fingerprint,
        platform=_PlatformInput(
            projection=checked.platform.model_copy(deep=True),
            profile=checked.platform.platform_profile,
            build_system=checked.platform.build_system,
            toolchain_requirement=checked.platform.toolchain_requirement,
            status=checked.platform.status,
            evidence_ids=tuple(checked.platform.evidence_ids),
        ),
        functional_requirements=tuple(checked.requirement.functional_requirements),
        software_constraints=tuple(checked.requirement.software_constraints),
        communication_requirements=tuple(
            checked.requirement.communication_requirements
        ),
        components=tuple(
            _ComponentInput(
                component_reference=item.component_reference,
                requirement_key=item.requirement_key,
                status=item.status.value,
                evidence_ids=tuple(item.evidence_ids),
            )
            for item in checked.hardware_proposal.component_selection.items
        ),
        interfaces=tuple(
            _InterfaceInput(
                interface_id=item.interface_id,
                protocol=item.protocol,
                component_reference=item.provider_component_reference,
                evidence_ids=tuple(item.evidence_ids),
            )
            for item in checked.hardware_proposal.interface_contracts.contracts
        ),
        hardware_finding_codes=tuple(
            item.value for item in checked.hardware_proposal.review.finding_codes
        ),
        verified_evidence=tuple(
            _EvidenceInput(
                evidence_id=item.evidence_id,
                source_type=item.source_type.value,
                fact_type=item.fact_type,
                reference_ids=tuple(item.reference_ids),
                fingerprint=item.fingerprint,
            )
            for item in checked.context.evidence
            if item.status is EvidenceStatus.VERIFIED
        ),
        proposed_at=checked.proposed_at,
    )
