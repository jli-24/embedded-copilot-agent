"""Typed, content-minimized input projection for Engineering Artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import field_validator, model_validator

from embedded_copilot.engineering_artifacts.models import (
    _ArtifactContract,
    _identifier,
    _utc,
)
from embedded_copilot.engineering_firmware import FirmwareEngineeringProposal
from embedded_copilot.engineering_hardware import HardwareEngineeringProposal
from embedded_copilot.engineering_intelligence import (
    EngineeringContextSnapshot,
    EngineeringRequirementDocument,
)
from embedded_copilot.engineering_validation import HardwareValidationReport


class EngineeringGenerationRequest(_ArtifactContract):
    proposal_id: str
    requirement: EngineeringRequirementDocument
    context: EngineeringContextSnapshot
    hardware_proposal: HardwareEngineeringProposal
    firmware_proposal: FirmwareEngineeringProposal
    validation_report: HardwareValidationReport | None = None
    proposed_at: datetime

    _proposal_id = field_validator("proposal_id")(
        lambda value: _identifier(value, field="proposal_id")
    )
    _proposed_at = field_validator("proposed_at")(
        lambda value: _utc(value, field="proposed_at")
    )

    @model_validator(mode="after")
    def validate_binding(self) -> EngineeringGenerationRequest:
        project_id = self.requirement.project_id
        if not all(
            value == project_id
            for value in (
                self.context.project.project_id,
                self.hardware_proposal.project_id,
                self.firmware_proposal.project_id,
            )
        ):
            raise ValueError("artifact project binding mismatch")
        if (
            self.context.requirement_fingerprint != self.requirement.fingerprint
            or self.hardware_proposal.requirement_fingerprint
            != self.requirement.fingerprint
            or self.firmware_proposal.requirement_fingerprint
            != self.requirement.fingerprint
            or self.hardware_proposal.plan_fingerprint != self.context.plan_fingerprint
            or self.firmware_proposal.plan_fingerprint != self.context.plan_fingerprint
            or self.hardware_proposal.context_fingerprint != self.context.fingerprint
            or self.firmware_proposal.context_fingerprint != self.context.fingerprint
            or self.firmware_proposal.hardware_proposal_fingerprint
            != self.hardware_proposal.fingerprint
        ):
            raise ValueError("artifact fingerprint binding mismatch")
        if self.validation_report is not None and (
            self.validation_report.project_id != project_id
            or self.validation_report.requirement_fingerprint
            != self.requirement.fingerprint
            or self.validation_report.plan_fingerprint != self.context.plan_fingerprint
            or self.validation_report.context_fingerprint != self.context.fingerprint
            or self.validation_report.hardware_proposal_fingerprint
            != self.hardware_proposal.fingerprint
            or self.validation_report.firmware_proposal_fingerprint
            != self.firmware_proposal.fingerprint
        ):
            raise ValueError("artifact validation binding mismatch")
        return self


@dataclass(frozen=True, slots=True)
class _FirmwareModuleInput:
    layer: str
    responsibility: str
    dependency_references: tuple[str, ...]
    unresolved: bool


@dataclass(frozen=True, slots=True)
class _CodeSkeletonInput:
    source_kind: str
    module_reference: str
    module_group: str
    responsibility: str
    dependency_references: tuple[str, ...]
    unresolved: bool


@dataclass(frozen=True, slots=True)
class _ComponentInput:
    component_id: str
    category: str
    reference: str
    evidence_ids: tuple[str, ...]
    unresolved: bool


@dataclass(frozen=True, slots=True)
class _InterfaceInput:
    interface_id: str
    protocol: str
    source_component: str | None
    target_component: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ConstraintInput:
    category: str
    key: str
    value: str | None


@dataclass(frozen=True, slots=True)
class _PCBConstraintInput:
    category: str
    subject_reference: str
    rule_code: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ValidationInput:
    report_fingerprint: str
    acquisition_status: str
    coverage_count: int
    finding_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _EngineeringArtifactInput:
    proposal_id: str
    project_id: str
    requirement_fingerprint: str
    plan_fingerprint: str
    context_fingerprint: str
    hardware_proposal_fingerprint: str
    firmware_proposal_fingerprint: str
    firmware_modules: tuple[_FirmwareModuleInput, ...]
    code_skeletons: tuple[_CodeSkeletonInput, ...]
    components: tuple[_ComponentInput, ...]
    interfaces: tuple[_InterfaceInput, ...]
    constraints: tuple[_ConstraintInput, ...]
    schematic_component_references: tuple[str, ...]
    schematic_interface_references: tuple[str, ...]
    schematic_power_references: tuple[str, ...]
    pcb_constraints: tuple[_PCBConstraintInput, ...]
    validation: _ValidationInput | None
    firmware_unresolved_count: int
    proposed_at: datetime


def project_input(value: object) -> _EngineeringArtifactInput:
    if type(value) is not EngineeringGenerationRequest:
        raise TypeError("typed engineering generation request is required")
    if (
        type(value.requirement) is not EngineeringRequirementDocument
        or type(value.context) is not EngineeringContextSnapshot
        or type(value.hardware_proposal) is not HardwareEngineeringProposal
        or type(value.firmware_proposal) is not FirmwareEngineeringProposal
        or (
            value.validation_report is not None
            and type(value.validation_report) is not HardwareValidationReport
        )
    ):
        raise TypeError("typed engineering artifact inputs are required")
    copied = value.model_copy(deep=True)
    checked = EngineeringGenerationRequest.model_validate(copied)
    constraints = tuple(
        sorted(
            (
                *(
                    _ConstraintInput("FUNCTIONAL", item, None)
                    for item in checked.requirement.functional_requirements
                ),
                *(
                    _ConstraintInput("COMMUNICATION", item, None)
                    for item in checked.requirement.communication_requirements
                ),
                *(
                    _ConstraintInput("POWER", item, None)
                    for item in checked.requirement.power_requirements
                ),
                *(
                    _ConstraintInput("HARDWARE", item.key, item.value)
                    for item in checked.requirement.hardware_constraints
                ),
            ),
            key=lambda item: (item.category, item.key, item.value or ""),
        )
    )
    skeletons = tuple(
        sorted(
            (
                *(
                    _CodeSkeletonInput(
                        source_kind="DRIVER",
                        module_reference=item.driver_reference,
                        module_group="DRIVERS",
                        responsibility=item.responsibility,
                        dependency_references=tuple(
                            sorted(
                                {
                                    *item.dependency_references,
                                    *item.interface_references,
                                    *(
                                        (item.component_reference,)
                                        if item.component_reference is not None
                                        else ()
                                    ),
                                }
                            )
                        ),
                        unresolved=item.status.value != "PROPOSED",
                    )
                    for item in checked.firmware_proposal.driver_design.drivers
                ),
                *(
                    _CodeSkeletonInput(
                        source_kind="INTENT",
                        module_reference=item.intent_code,
                        module_group=item.module_group.value,
                        responsibility=item.responsibility,
                        dependency_references=tuple(item.dependency_references),
                        unresolved=False,
                    )
                    for item in checked.firmware_proposal.code_generation.intents
                ),
            ),
            key=lambda item: (item.source_kind, item.module_reference),
        )
    )
    validation = (
        None
        if checked.validation_report is None
        else _ValidationInput(
            report_fingerprint=checked.validation_report.fingerprint,
            acquisition_status=checked.validation_report.acquisition_status.value,
            coverage_count=checked.validation_report.review.coverage_count,
            finding_codes=tuple(
                item.value for item in checked.validation_report.review.finding_codes
            ),
        )
    )
    return _EngineeringArtifactInput(
        proposal_id=checked.proposal_id,
        project_id=checked.requirement.project_id,
        requirement_fingerprint=checked.requirement.fingerprint,
        plan_fingerprint=checked.context.plan_fingerprint,
        context_fingerprint=checked.context.fingerprint,
        hardware_proposal_fingerprint=checked.hardware_proposal.fingerprint,
        firmware_proposal_fingerprint=checked.firmware_proposal.fingerprint,
        firmware_modules=tuple(
            _FirmwareModuleInput(
                layer=item.layer.value,
                responsibility=item.responsibility,
                dependency_references=tuple(
                    sorted({*item.component_references, *item.interface_references})
                ),
                unresolved=item.status.value != "PROPOSED",
            )
            for item in checked.firmware_proposal.architecture.modules
        ),
        code_skeletons=skeletons,
        components=tuple(
            _ComponentInput(
                component_id=item.component_reference,
                category=item.requirement_key,
                reference=item.candidate,
                evidence_ids=tuple(item.evidence_ids),
                unresolved=item.status.value in ("CONFLICT", "UNRESOLVED"),
            )
            for item in checked.hardware_proposal.component_selection.items
        ),
        interfaces=tuple(
            _InterfaceInput(
                interface_id=item.interface_id,
                protocol=item.protocol,
                source_component=item.provider_component_reference,
                target_component=item.consumer_reference,
                evidence_ids=tuple(item.evidence_ids),
            )
            for item in checked.hardware_proposal.interface_contracts.contracts
        ),
        constraints=constraints,
        schematic_component_references=tuple(
            checked.hardware_proposal.schematic_intent.component_references
        ),
        schematic_interface_references=tuple(
            checked.hardware_proposal.schematic_intent.interface_references
        ),
        schematic_power_references=tuple(
            checked.hardware_proposal.schematic_intent.power_requirement_references
        ),
        pcb_constraints=tuple(
            _PCBConstraintInput(
                category=item.category.value,
                subject_reference=item.subject_reference,
                rule_code=item.rule_code,
                evidence_ids=tuple(item.evidence_ids),
            )
            for item in checked.hardware_proposal.pcb_constraints.constraints
        ),
        validation=validation,
        firmware_unresolved_count=checked.firmware_proposal.review.unresolved_count,
        proposed_at=checked.proposed_at,
    )
