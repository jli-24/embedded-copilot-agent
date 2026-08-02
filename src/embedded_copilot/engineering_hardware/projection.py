"""Deterministic, evidence-bound Hardware Engineering projections."""

from __future__ import annotations

from collections import defaultdict

from embedded_copilot.engineering_hardware.integration.intelligence import (
    _EvidenceInput,
    _HardwareEngineeringInput,
)
from embedded_copilot.engineering_hardware.models import (
    BOMLineItem,
    BOMProposal,
    ComponentSelectionItem,
    ComponentSelectionProposal,
    ComponentSelectionStatus,
    HardwareDesignReviewProjection,
    HardwareEngineeringProposal,
    HardwareEvidenceTrace,
    HardwareFindingCode,
    HardwareFindingSeverity,
    HardwareReviewFinding,
    InterfaceContract,
    InterfaceContractProposal,
    PCBConstraint,
    PCBConstraintCategory,
    PCBConstraintProposal,
    PowerDesignProposal,
    SchematicIntentModel,
    SystemArchitectureBlock,
    SystemArchitectureProposal,
    SystemArchitectureRelation,
    bom_fingerprint,
    component_selection_fingerprint,
    hardware_engineering_proposal_fingerprint,
    hardware_review_fingerprint,
    interface_contracts_fingerprint,
    pcb_constraints_fingerprint,
    power_design_fingerprint,
    schematic_intent_fingerprint,
    system_architecture_fingerprint,
)


def build_hardware_proposal(
    source: _HardwareEngineeringInput,
) -> HardwareEngineeringProposal:
    evidence_trace = _evidence_trace(source.verified_evidence)
    selections, selection_findings = _component_selection(source)
    architecture = _architecture(source, selections)
    interfaces, interface_findings = _interfaces(source, selections)
    power = _power(source, selections)
    bom = _bom(selections)
    schematic = _schematic(selections, interfaces, source.power_requirements)
    pcb = _pcb_constraints(selections, interfaces)
    findings = _sorted_findings(
        (*selection_findings, *interface_findings, _power_finding())
    )
    review = _review(
        source=source,
        selections=selections,
        interfaces=interfaces,
        bom=bom,
        evidence_trace=evidence_trace,
        findings=findings,
    )
    values = dict(
        proposal_id=source.proposal_id,
        project_id=source.project_id,
        requirement_fingerprint=source.requirement_fingerprint,
        plan_fingerprint=source.plan_fingerprint,
        context_fingerprint=source.context_fingerprint,
        architecture=architecture,
        component_selection=selections,
        interface_contracts=interfaces,
        power_design=power,
        bom=bom,
        schematic_intent=schematic,
        pcb_constraints=pcb,
        evidence_trace=evidence_trace,
        review=review,
        proposed_at=source.proposed_at,
        candidate_semantics="unverified",
        review_required=True,
    )
    return HardwareEngineeringProposal(
        **values,
        fingerprint=hardware_engineering_proposal_fingerprint(**values),
    )


def _evidence_trace(
    evidence: tuple[_EvidenceInput, ...],
) -> tuple[HardwareEvidenceTrace, ...]:
    return tuple(
        HardwareEvidenceTrace(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            reference_ids=item.reference_ids,
            source_fingerprint=item.fingerprint,
        )
        for item in sorted(evidence, key=lambda item: item.evidence_id)
    )


def _component_selection(
    source: _HardwareEngineeringInput,
) -> tuple[ComponentSelectionProposal, tuple[HardwareReviewFinding, ...]]:
    constraints: dict[str, list[str]] = defaultdict(list)
    for item in source.hardware_constraints:
        constraints[item.key].append(item.value)
    evidence: dict[str, list[_EvidenceInput]] = defaultdict(list)
    for item in source.verified_evidence:
        evidence[item.key.casefold()].append(item)

    selections: list[ComponentSelectionItem] = []
    findings: list[HardwareReviewFinding] = []
    for key in sorted(constraints):
        values = tuple(sorted(set(constraints[key])))
        component_reference = f"component-{key.casefold()}"
        key_evidence = tuple(
            sorted(evidence.get(key.casefold(), ()), key=lambda item: item.evidence_id)
        )
        evidence_values = {item.value.casefold() for item in key_evidence}
        if len(values) > 1:
            selections.append(
                ComponentSelectionItem(
                    component_reference=component_reference,
                    requirement_key=key,
                    candidate="UNRESOLVED",
                    status=ComponentSelectionStatus.CONFLICT,
                    evidence_ids=(),
                )
            )
            findings.append(
                _finding(
                    HardwareFindingCode.CONSTRAINT_CONFLICT,
                    HardwareFindingSeverity.BLOCKING,
                    component_reference,
                )
            )
            continue

        candidate = values[0]
        matching = tuple(
            item
            for item in key_evidence
            if item.value.casefold() == candidate.casefold()
        )
        if len(evidence_values) > 1:
            status = ComponentSelectionStatus.CONFLICT
            evidence_ids = ()
            findings.append(
                _finding(
                    HardwareFindingCode.VERIFIED_EVIDENCE_CONFLICT,
                    HardwareFindingSeverity.BLOCKING,
                    component_reference,
                )
            )
        elif key_evidence and not matching:
            status = ComponentSelectionStatus.CONFLICT
            evidence_ids = ()
            findings.append(
                _finding(
                    HardwareFindingCode.REQUIREMENT_EVIDENCE_CONFLICT,
                    HardwareFindingSeverity.BLOCKING,
                    component_reference,
                    tuple(item.evidence_id for item in key_evidence),
                )
            )
        elif matching:
            status = ComponentSelectionStatus.SUPPORTED
            evidence_ids = tuple(item.evidence_id for item in matching)
        else:
            status = ComponentSelectionStatus.UNVERIFIED
            evidence_ids = ()
            findings.append(
                _finding(
                    HardwareFindingCode.COMPONENT_UNRESOLVED,
                    HardwareFindingSeverity.REVIEW,
                    component_reference,
                )
            )
        selections.append(
            ComponentSelectionItem(
                component_reference=component_reference,
                requirement_key=key,
                candidate=candidate,
                status=status,
                evidence_ids=evidence_ids,
            )
        )

    items = tuple(
        sorted(selections, key=lambda item: (item.requirement_key, item.candidate))
    )
    proposal = ComponentSelectionProposal(
        items=items,
        fingerprint=component_selection_fingerprint(items=items),
    )
    return proposal, tuple(findings)


def _architecture(
    source: _HardwareEngineeringInput,
    selections: ComponentSelectionProposal,
) -> SystemArchitectureProposal:
    blocks = [
        SystemArchitectureBlock(
            block_id="system",
            block_type="SYSTEM",
            label=source.product,
            component_reference=None,
            evidence_ids=(),
        )
    ]
    relations = []
    for item in selections.items:
        block_id = f"block-{item.requirement_key.casefold()}"
        blocks.append(
            SystemArchitectureBlock(
                block_id=block_id,
                block_type="COMPONENT",
                label=item.candidate,
                component_reference=item.component_reference,
                evidence_ids=item.evidence_ids,
            )
        )
        relations.append(
            SystemArchitectureRelation(
                source_block_id="system",
                target_block_id=block_id,
                relation_type="SYSTEM_CONTAINS_COMPONENT",
            )
        )
    sorted_blocks = tuple(sorted(blocks, key=lambda item: item.block_id))
    sorted_relations = tuple(
        sorted(
            relations,
            key=lambda item: (
                item.source_block_id,
                item.target_block_id,
                item.relation_type,
            ),
        )
    )
    values = dict(
        product=source.product,
        capabilities=source.functional_requirements,
        blocks=sorted_blocks,
        relations=sorted_relations,
    )
    return SystemArchitectureProposal(
        **values,
        fingerprint=system_architecture_fingerprint(**values),
    )


def _interfaces(
    source: _HardwareEngineeringInput,
    selections: ComponentSelectionProposal,
) -> tuple[InterfaceContractProposal, tuple[HardwareReviewFinding, ...]]:
    mcu = next(
        (
            item
            for item in selections.items
            if item.requirement_key == "MCU"
            and item.status
            in {ComponentSelectionStatus.SUPPORTED, ComponentSelectionStatus.UNVERIFIED}
        ),
        None,
    )
    contracts = tuple(
        InterfaceContract(
            interface_id=f"interface-{protocol.casefold()}",
            protocol=protocol,
            provider_component_reference=(
                mcu.component_reference if mcu is not None else None
            ),
            consumer_reference=None,
            electrical_standard=None,
            pin_bindings=(),
            evidence_ids=(),
        )
        for protocol in source.communication_requirements
    )
    findings = tuple(
        _finding(
            HardwareFindingCode.INTERFACE_BINDING_UNRESOLVED,
            HardwareFindingSeverity.REVIEW,
            item.interface_id,
        )
        for item in contracts
    )
    return (
        InterfaceContractProposal(
            contracts=contracts,
            fingerprint=interface_contracts_fingerprint(contracts=contracts),
        ),
        findings,
    )


def _power(
    source: _HardwareEngineeringInput,
    selections: ComponentSelectionProposal,
) -> PowerDesignProposal:
    consumers = tuple(
        sorted(
            item.component_reference
            for item in selections.items
            if item.status is not ComponentSelectionStatus.CONFLICT
        )
    )
    values = dict(
        requirements=source.power_requirements,
        consumer_references=consumers,
        input_voltage=None,
        current_budget=None,
        margin_percent=None,
        evidence_ids=(),
    )
    return PowerDesignProposal(
        **values,
        fingerprint=power_design_fingerprint(**values),
    )


def _bom(selections: ComponentSelectionProposal) -> BOMProposal:
    items = tuple(
        sorted(
            (
                BOMLineItem(
                    line_id=f"line-{item.requirement_key.casefold()}",
                    component_reference=item.component_reference,
                    requirement_key=item.requirement_key,
                    candidate=item.candidate,
                    evidence_ids=item.evidence_ids,
                )
                for item in selections.items
                if item.status is not ComponentSelectionStatus.CONFLICT
            ),
            key=lambda item: item.line_id,
        )
    )
    return BOMProposal(items=items, fingerprint=bom_fingerprint(items=items))


def _schematic(
    selections: ComponentSelectionProposal,
    interfaces: InterfaceContractProposal,
    power_requirements: tuple[str, ...],
) -> SchematicIntentModel:
    values = dict(
        component_references=tuple(
            sorted(
                item.component_reference
                for item in selections.items
                if item.status is not ComponentSelectionStatus.CONFLICT
            )
        ),
        interface_references=tuple(item.interface_id for item in interfaces.contracts),
        power_requirement_references=power_requirements,
        net_intents=(),
    )
    return SchematicIntentModel(
        **values,
        fingerprint=schematic_intent_fingerprint(**values),
    )


def _pcb_constraints(
    selections: ComponentSelectionProposal,
    interfaces: InterfaceContractProposal,
) -> PCBConstraintProposal:
    constraints = [
        PCBConstraint(
            constraint_id="pcb-ground-return",
            category=PCBConstraintCategory.GROUND_RETURN,
            subject_reference="system",
            rule_code="GROUND_RETURN_REVIEW",
        ),
        PCBConstraint(
            constraint_id="pcb-power-distribution",
            category=PCBConstraintCategory.POWER_DISTRIBUTION,
            subject_reference="system",
            rule_code="POWER_DISTRIBUTION_REVIEW",
        ),
    ]
    constraints.extend(
        PCBConstraint(
            constraint_id=f"pcb-placement-{item.requirement_key.casefold()}",
            category=PCBConstraintCategory.PLACEMENT,
            subject_reference=item.component_reference,
            rule_code="COMPONENT_PLACEMENT_REVIEW",
            evidence_ids=item.evidence_ids,
        )
        for item in selections.items
    )
    constraints.extend(
        PCBConstraint(
            constraint_id=f"pcb-routing-{item.protocol.casefold()}",
            category=PCBConstraintCategory.INTERFACE_ROUTING,
            subject_reference=item.interface_id,
            rule_code="INTERFACE_ROUTING_REVIEW",
        )
        for item in interfaces.contracts
    )
    result = tuple(sorted(constraints, key=lambda item: item.constraint_id))
    return PCBConstraintProposal(
        constraints=result,
        fingerprint=pcb_constraints_fingerprint(constraints=result),
    )


def _power_finding() -> HardwareReviewFinding:
    return _finding(
        HardwareFindingCode.POWER_BUDGET_UNKNOWN,
        HardwareFindingSeverity.REVIEW,
        "system",
    )


def _finding(
    code: HardwareFindingCode,
    severity: HardwareFindingSeverity,
    subject_reference: str,
    evidence_ids: tuple[str, ...] = (),
) -> HardwareReviewFinding:
    return HardwareReviewFinding(
        code=code,
        severity=severity,
        subject_reference=subject_reference,
        evidence_ids=tuple(sorted(evidence_ids)),
    )


def _sorted_findings(
    findings: tuple[HardwareReviewFinding, ...],
) -> tuple[HardwareReviewFinding, ...]:
    unique = {(item.code.value, item.subject_reference): item for item in findings}
    return tuple(unique[key] for key in sorted(unique))


def _review(
    *,
    source: _HardwareEngineeringInput,
    selections: ComponentSelectionProposal,
    interfaces: InterfaceContractProposal,
    bom: BOMProposal,
    evidence_trace: tuple[HardwareEvidenceTrace, ...],
    findings: tuple[HardwareReviewFinding, ...],
) -> HardwareDesignReviewProjection:
    values = dict(
        proposal_id=source.proposal_id,
        requirement_fingerprint=source.requirement_fingerprint,
        plan_fingerprint=source.plan_fingerprint,
        context_fingerprint=source.context_fingerprint,
        component_count=len(selections.items),
        interface_count=len(interfaces.contracts),
        bom_item_count=len(bom.items),
        evidence_count=len(evidence_trace),
        findings=findings,
        finding_codes=tuple(
            sorted({item.code for item in findings}, key=lambda item: item.value)
        ),
        review_required=True,
    )
    return HardwareDesignReviewProjection(
        **values,
        fingerprint=hardware_review_fingerprint(**values),
    )
