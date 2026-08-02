"""Pure deterministic Engineering Artifact projections."""

from __future__ import annotations

from embedded_copilot.engineering_artifacts.integration.inputs import (
    _EngineeringArtifactInput,
)
from embedded_copilot.engineering_artifacts.models import (
    ArtifactContractEntry,
    ArtifactFindingCode,
    ArtifactReviewProjection,
    ArtifactReviewState,
    ArtifactSourceBinding,
    ArtifactSourceReference,
    ArtifactSourceType,
    ArtifactStatus,
    ArtifactType,
    CodeSkeletonProjection,
    ConstraintCategory,
    EngineeringArtifactContract,
    EngineeringGenerationReport,
    FirmwareArtifactProjection,
    FirmwareModuleArtifact,
    FirmwareModuleGroup,
    FirmwareModuleKind,
    HardwareArtifactProjection,
    PCBConstraintArtifact,
    PCBConstraintArtifactItem,
    SchematicIntentArtifact,
    UnifiedComponent,
    UnifiedConstraint,
    UnifiedHardwareModel,
    UnifiedInterface,
    ValidationAcquisitionStatus,
    _Fingerprinted,
    _model_fingerprint,
    artifact_source_fingerprint,
    engineering_generation_report_fingerprint,
)


def _model(model_type: type[_Fingerprinted], **values: object):
    return model_type(
        **values,
        fingerprint=_model_fingerprint(model_type, **values),
    )


def build_report(source: _EngineeringArtifactInput) -> EngineeringGenerationReport:
    firmware = _firmware_artifact(source)
    hardware_model = _hardware_model(source)
    schematic = _schematic(source)
    pcb = _pcb(source)
    hardware = _model(
        HardwareArtifactProjection,
        candidate_semantics="unverified",
        unified_model=hardware_model,
        schematic_intent=schematic,
        pcb_constraints=pcb,
    )
    statuses = _artifact_statuses(source, firmware, hardware_model, schematic, pcb)
    contract = _artifact_contract(
        source, statuses, firmware, hardware_model, schematic, pcb
    )
    review = _review(source, statuses)
    values = dict(
        proposal_id=source.proposal_id,
        project_id=source.project_id,
        requirement_fingerprint=source.requirement_fingerprint,
        plan_fingerprint=source.plan_fingerprint,
        context_fingerprint=source.context_fingerprint,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        firmware_proposal_fingerprint=source.firmware_proposal_fingerprint,
        validation_report_fingerprint=(
            None if source.validation is None else source.validation.report_fingerprint
        ),
        firmware_artifact=firmware,
        hardware_artifact=hardware,
        unified_hardware_model=hardware_model,
        review=review,
        artifact_contract=contract,
        proposed_at=source.proposed_at,
        candidate_semantics="unverified",
        review_required=True,
    )
    return EngineeringGenerationReport(
        **values,
        fingerprint=engineering_generation_report_fingerprint(**values),
    )


def _firmware_artifact(
    source: _EngineeringArtifactInput,
) -> FirmwareArtifactProjection:
    modules = tuple(
        _model(
            FirmwareModuleArtifact,
            module_reference=item.layer,
            module_group=FirmwareModuleGroup(item.layer),
            responsibility=item.responsibility,
            dependency_references=item.dependency_references,
            unresolved=item.unresolved,
        )
        for item in source.firmware_modules
    )
    skeletons = tuple(
        _model(
            CodeSkeletonProjection,
            source_kind=FirmwareModuleKind(item.source_kind),
            module_reference=item.module_reference,
            module_group=FirmwareModuleGroup(item.module_group),
            responsibility=item.responsibility,
            dependency_references=item.dependency_references,
            unresolved=item.unresolved,
        )
        for item in source.code_skeletons
    )
    return _model(
        FirmwareArtifactProjection,
        candidate_semantics="unverified",
        modules=modules,
        code_skeletons=skeletons,
    )


def _hardware_model(source: _EngineeringArtifactInput) -> UnifiedHardwareModel:
    components = tuple(
        _model(
            UnifiedComponent,
            component_id=item.component_id,
            category=item.category,
            reference=item.reference,
            evidence_ids=item.evidence_ids,
            unresolved=item.unresolved,
        )
        for item in source.components
    )
    interfaces = tuple(
        _model(
            UnifiedInterface,
            interface_id=item.interface_id,
            protocol=item.protocol,
            source_component=item.source_component,
            target_component=item.target_component,
            evidence_ids=item.evidence_ids,
        )
        for item in source.interfaces
    )
    order = {value.value: index for index, value in enumerate(ConstraintCategory)}
    constraints = tuple(
        _model(
            UnifiedConstraint,
            category=ConstraintCategory(item.category),
            key=item.key,
            value=item.value,
        )
        for item in sorted(
            source.constraints,
            key=lambda item: (order[item.category], item.key, item.value or ""),
        )
    )
    return _model(
        UnifiedHardwareModel,
        candidate_semantics="unverified",
        components=components,
        interfaces=interfaces,
        constraints=constraints,
    )


def _schematic(source: _EngineeringArtifactInput) -> SchematicIntentArtifact:
    return _model(
        SchematicIntentArtifact,
        candidate_semantics="unverified",
        component_references=source.schematic_component_references,
        interface_references=source.schematic_interface_references,
        power_requirement_references=source.schematic_power_references,
        net_intents=(),
    )


def _pcb(source: _EngineeringArtifactInput) -> PCBConstraintArtifact:
    constraints = tuple(
        _model(
            PCBConstraintArtifactItem,
            category=item.category,
            subject_reference=item.subject_reference,
            rule_code=item.rule_code,
            evidence_ids=item.evidence_ids,
        )
        for item in sorted(
            source.pcb_constraints,
            key=lambda item: (
                item.category,
                item.subject_reference,
                item.rule_code,
            ),
        )
    )
    return _model(
        PCBConstraintArtifact,
        candidate_semantics="unverified",
        constraints=constraints,
    )


def _artifact_statuses(
    source: _EngineeringArtifactInput,
    firmware: FirmwareArtifactProjection,
    hardware: UnifiedHardwareModel,
    schematic: SchematicIntentArtifact,
    pcb: PCBConstraintArtifact,
) -> tuple[tuple[ArtifactType, ArtifactStatus], ...]:
    firmware_status = (
        ArtifactStatus.UNAVAILABLE
        if not firmware.modules and not firmware.code_skeletons
        else (
            ArtifactStatus.REVIEW_REQUIRED
            if source.firmware_unresolved_count
            or any(item.unresolved for item in firmware.modules)
            or any(item.unresolved for item in firmware.code_skeletons)
            else ArtifactStatus.GENERATED
        )
    )
    hardware_status = (
        ArtifactStatus.UNAVAILABLE
        if not hardware.components
        and not hardware.interfaces
        and not hardware.constraints
        else (
            ArtifactStatus.REVIEW_REQUIRED
            if any(item.unresolved for item in hardware.components)
            or any(
                item.source_component is None or item.target_component is None
                for item in hardware.interfaces
            )
            else ArtifactStatus.GENERATED
        )
    )
    schematic_status = (
        ArtifactStatus.UNAVAILABLE
        if not schematic.component_references
        and not schematic.interface_references
        and not schematic.power_requirement_references
        else ArtifactStatus.REVIEW_REQUIRED
    )
    pcb_status = (
        ArtifactStatus.GENERATED if pcb.constraints else ArtifactStatus.UNAVAILABLE
    )
    return (
        (ArtifactType.FIRMWARE_STRUCTURE, firmware_status),
        (ArtifactType.HARDWARE_MODEL, hardware_status),
        (ArtifactType.SCHEMATIC_INTENT, schematic_status),
        (ArtifactType.PCB_CONSTRAINT, pcb_status),
    )


def _source_reference(
    source_type: ArtifactSourceType, source_fingerprint: str
) -> ArtifactSourceReference:
    return _model(
        ArtifactSourceReference,
        source_type=source_type,
        source_fingerprint=source_fingerprint,
    )


def _artifact_contract(
    source: _EngineeringArtifactInput,
    statuses: tuple[tuple[ArtifactType, ArtifactStatus], ...],
    firmware: FirmwareArtifactProjection,
    hardware: UnifiedHardwareModel,
    schematic: SchematicIntentArtifact,
    pcb: PCBConstraintArtifact,
) -> EngineeringArtifactContract:
    fingerprints = {
        ArtifactType.FIRMWARE_STRUCTURE: firmware.fingerprint,
        ArtifactType.HARDWARE_MODEL: hardware.fingerprint,
        ArtifactType.SCHEMATIC_INTENT: schematic.fingerprint,
        ArtifactType.PCB_CONSTRAINT: pcb.fingerprint,
    }
    artifacts = tuple(
        _model(
            ArtifactContractEntry,
            artifact_type=artifact_type,
            status=status,
            artifact_fingerprint=fingerprints[artifact_type],
        )
        for artifact_type, status in statuses
    )
    common = (
        _source_reference(
            ArtifactSourceType.REQUIREMENT, source.requirement_fingerprint
        ),
        _source_reference(ArtifactSourceType.CONTEXT, source.context_fingerprint),
        _source_reference(
            ArtifactSourceType.HARDWARE_PROPOSAL,
            source.hardware_proposal_fingerprint,
        ),
    )
    firmware_sources = (
        *common,
        _source_reference(
            ArtifactSourceType.FIRMWARE_PROPOSAL,
            source.firmware_proposal_fingerprint,
        ),
    )
    bindings = tuple(
        _model(
            ArtifactSourceBinding,
            artifact_type=artifact_type,
            sources=(
                firmware_sources
                if artifact_type is ArtifactType.FIRMWARE_STRUCTURE
                else common
            ),
        )
        for artifact_type in ArtifactType
    )
    source_fingerprint = artifact_source_fingerprint(source_bindings=bindings)
    return _model(
        EngineeringArtifactContract,
        candidate_semantics="unverified",
        artifacts=artifacts,
        source_bindings=bindings,
        artifact_source_fingerprint=source_fingerprint,
        review_required=True,
    )


def _review(
    source: _EngineeringArtifactInput,
    statuses: tuple[tuple[ArtifactType, ArtifactStatus], ...],
) -> ArtifactReviewProjection:
    validation = source.validation
    return _model(
        ArtifactReviewProjection,
        proposal_id=source.proposal_id,
        hardware_proposal_fingerprint=source.hardware_proposal_fingerprint,
        firmware_proposal_fingerprint=source.firmware_proposal_fingerprint,
        requirement_fingerprint=source.requirement_fingerprint,
        context_fingerprint=source.context_fingerprint,
        validation_report_fingerprint=(
            None if validation is None else validation.report_fingerprint
        ),
        validation_acquisition_status=(
            None
            if validation is None
            else ValidationAcquisitionStatus(validation.acquisition_status)
        ),
        validation_coverage_count=(
            0 if validation is None else validation.coverage_count
        ),
        validation_finding_codes=(
            () if validation is None else tuple(sorted(validation.finding_codes))
        ),
        artifact_count=sum(
            status is not ArtifactStatus.UNAVAILABLE for _kind, status in statuses
        ),
        unresolved_count=sum(
            status is not ArtifactStatus.GENERATED for _kind, status in statuses
        ),
        finding_codes=tuple(ArtifactFindingCode),
        review_state=ArtifactReviewState.PENDING,
        review_required=True,
    )
