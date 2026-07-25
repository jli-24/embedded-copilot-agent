from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from embedded_copilot.engineering.crosscheck import cross_check
from embedded_copilot.engineering.models import RealEngineeringEnvelope
from embedded_copilot.hardware.models import HardwareComponent, HardwarePlan
from embedded_copilot.hardware_design._validation import safe_identifier, safe_text
from embedded_copilot.hardware_design.approval import DesignApproval
from embedded_copilot.hardware_design.artifact import HardwareDesignArtifact
from embedded_copilot.hardware_design.decision import DesignDecision
from embedded_copilot.hardware_design.evidence import (
    DesignEvidence,
    DesignEvidenceSourceType,
)
from embedded_copilot.hardware_design.models import (
    DesignComponent,
    DesignModule,
    GPIOAssignment,
    GPIOAssignmentStatus,
    HardwareDesignBlueprint,
    PowerTree,
)


@dataclass(frozen=True)
class _Projection:
    blueprint: HardwareDesignBlueprint
    evidence: tuple[DesignEvidence, ...]
    decisions: tuple[DesignDecision, ...]


def project(
    plan: HardwarePlan,
    envelope: RealEngineeringEnvelope | None = None,
) -> HardwareDesignBlueprint:
    """Project existing observations without making new hardware conclusions."""
    return _project_all(plan, envelope).blueprint


def project_artifact(
    plan: HardwarePlan,
    envelope: RealEngineeringEnvelope | None = None,
) -> HardwareDesignArtifact:
    """Build the optional, read-only explanation artifact."""
    projected = _project_all(plan, envelope)
    return HardwareDesignArtifact(
        blueprint=projected.blueprint,
        evidence=projected.evidence,
        decisions=projected.decisions,
        approval=DesignApproval(),
    )


def _project_all(
    plan: HardwarePlan,
    envelope: RealEngineeringEnvelope | None,
) -> _Projection:
    if not isinstance(plan, HardwarePlan):
        raise TypeError("hardware design projection requires a HardwarePlan")
    if envelope is not None and not isinstance(envelope, RealEngineeringEnvelope):
        raise TypeError("hardware design projection envelope is invalid")
    isolated_plan = plan.model_copy(deep=True)
    isolated_envelope = envelope.model_copy(deep=True) if envelope is not None else None

    evidence, evidence_by_source, datasheet_component_evidence = _evidence(
        isolated_plan,
        isolated_envelope,
    )
    datasheet_source = _datasheet_source(isolated_envelope)
    rag_sources = _rag_sources(isolated_plan)
    mcu_sources = (
        (datasheet_source,)
        if datasheet_source is not None
        and isolated_envelope is not None
        and isolated_envelope.datasheet is not None
        and isolated_envelope.datasheet.component.part_number.casefold()
        == isolated_plan.mcu.casefold()
        else ()
    )

    limitations: list[str] = []
    mcu_name = _required_text(isolated_plan.mcu, "Unresolved MCU", limitations)
    modules = [
        DesignModule(
            name=mcu_name,
            description="MCU observation copied from HardwarePlan; design correctness is unresolved.",
            source_ids=mcu_sources,
        )
    ]
    if not mcu_sources:
        limitations.append(
            f"No confirmed evidence is bound to HardwarePlan MCU {mcu_name}."
        )

    components: list[DesignComponent] = []
    component_decisions: list[DesignDecision] = []
    for index, component in enumerate(isolated_plan.components, start=1):
        component_sources = _component_sources(component, rag_sources)
        name = _required_text(
            component.name,
            f"Unresolved component {index}",
            limitations,
        )
        description = _required_text(
            component.description,
            "Component description omitted because it is unsafe to expose.",
            limitations,
        )
        category = _required_text(
            component.category,
            "unresolved",
            limitations,
        )
        modules.append(
            DesignModule(
                name=name,
                description=description,
                source_ids=component_sources,
            )
        )
        components.append(
            DesignComponent(
                name=name,
                category=category,
                purpose=description,
                source_ids=component_sources,
            )
        )
        if component_sources:
            evidence_ids = tuple(
                evidence_by_source[source_id][0] for source_id in component_sources
            )
            component_decisions.append(
                _decision(
                    "component_observation",
                    f"HardwarePlan includes component {name}.",
                    "The existing plan observation references an explicit RAG source identifier; electrical and connection correctness remain unresolved.",
                    evidence_ids,
                )
            )
        else:
            limitations.append(
                f"No confirmed evidence is bound to HardwarePlan component {name}."
            )

    for interface in isolated_plan.interfaces:
        safe_interface = _optional_text(interface)
        if safe_interface is None:
            limitations.append(
                "A HardwarePlan interface was omitted because it is unsafe to expose."
            )
        else:
            limitations.append(
                f"Unresolved connection endpoints for interface {safe_interface}."
            )

    constraints = _safe_collection(
        isolated_plan.constraints,
        limitations,
        "A HardwarePlan constraint was omitted because it is unsafe to expose.",
    )
    power_limitations = [
        "Power input, electrical parameters, margins, and guarantees are unresolved."
    ]
    for requirement in isolated_plan.power_requirements:
        safe_requirement = _optional_text(requirement)
        if safe_requirement is None:
            power_limitations.append(
                "A HardwarePlan power requirement was omitted because it is unsafe to expose."
            )
        else:
            power_limitations.append(
                f"Unverified HardwarePlan power requirement: {safe_requirement}"
            )
    power_stages = tuple(
        component.name
        for component in components
        if component.category.casefold() == "power"
    )

    gpio_assignments, gpio_decisions = _gpio_projection(
        isolated_envelope,
        evidence_by_source,
        datasheet_component_evidence,
    )
    source_values = tuple(item.source_id for item in evidence)
    blueprint = HardwareDesignBlueprint(
        project_name=_required_text(
            isolated_plan.project_name,
            "hardware-design",
            limitations,
        ),
        target_platform=_required_text(
            isolated_plan.platform,
            "unresolved",
            limitations,
        ),
        modules=tuple(modules),
        components=tuple(components),
        connections=(),
        gpio_assignments=gpio_assignments,
        power_tree=PowerTree(
            input="unresolved",
            stages=power_stages,
            consumers=(),
            limitations=tuple(power_limitations),
        ),
        constraints=constraints,
        limitations=tuple(dict.fromkeys(limitations)),
        source_ids=source_values,
    )

    decisions: list[DesignDecision] = []
    if mcu_sources and datasheet_component_evidence is not None:
        decisions.append(
            _decision(
                "mcu_observation",
                f"HardwarePlan identifies MCU {mcu_name}.",
                "The MCU name matches the structured Datasheet component record; design correctness remains unresolved.",
                (datasheet_component_evidence,),
            )
        )
    decisions.extend(component_decisions)
    decisions.extend(gpio_decisions)
    return _Projection(
        blueprint=blueprint,
        evidence=evidence,
        decisions=tuple(decisions),
    )


def _evidence(
    plan: HardwarePlan,
    envelope: RealEngineeringEnvelope | None,
) -> tuple[tuple[DesignEvidence, ...], dict[str, tuple[str, ...]], str | None]:
    result: list[DesignEvidence] = []
    by_source: dict[str, list[str]] = {}
    datasheet_component_evidence: str | None = None

    if envelope is not None and envelope.datasheet is not None:
        datasheet = envelope.datasheet
        source_id = _datasheet_source(envelope)
        if source_id is not None:
            datasheet_component_evidence = _append_evidence(
                result,
                by_source,
                source_id=source_id,
                source_type=DesignEvidenceSourceType.DATASHEET,
                location="structured:datasheet",
                summary=(
                    "Structured Datasheet component record identifies part number "
                    f"{datasheet.component.part_number}."
                ),
            )
            for pin in datasheet.pins:
                _append_evidence(
                    result,
                    by_source,
                    source_id=source_id,
                    source_type=DesignEvidenceSourceType.DATASHEET,
                    location="structured:datasheet",
                    summary=(
                        "Structured Datasheet pin record identifies number "
                        f"{pin.number}, name {pin.name}, and type {pin.type}."
                    ),
                )
            for interface in datasheet.interfaces:
                _append_evidence(
                    result,
                    by_source,
                    source_id=source_id,
                    source_type=DesignEvidenceSourceType.DATASHEET,
                    location="structured:datasheet",
                    summary=(
                        "Structured Datasheet interface record identifies "
                        f"{interface.name}, protocol {interface.protocol}, and "
                        f"{len(interface.pins)} pin identifier(s)."
                    ),
                )
            for specification in (
                *datasheet.electrical_specs,
                *datasheet.power_requirements,
            ):
                values = ", ".join(
                    f"{label}={value:g}"
                    for label, value in (
                        ("min", specification.min_value),
                        ("typical", specification.typical_value),
                        ("max", specification.max_value),
                    )
                    if value is not None
                )
                _append_evidence(
                    result,
                    by_source,
                    source_id=source_id,
                    source_type=DesignEvidenceSourceType.DATASHEET,
                    location="structured:datasheet",
                    summary=(
                        "Structured Datasheet electrical record identifies parameter "
                        f"{specification.parameter}, {values}, unit {specification.unit}."
                    ),
                )

    if envelope is not None and envelope.firmware_review is not None:
        for assignment in envelope.firmware_review.gpio_assignments:
            _append_evidence(
                result,
                by_source,
                source_id=assignment.source_id,
                source_type=DesignEvidenceSourceType.FIRMWARE,
                location=f"line:{assignment.line}",
                summary=(
                    "Structured Firmware review records pin "
                    f"{assignment.pin} with role {assignment.role}; "
                    f"initialized={str(assignment.initialized).lower()}."
                ),
            )

    for source_id in _rag_sources(plan):
        _append_evidence(
            result,
            by_source,
            source_id=source_id,
            source_type=DesignEvidenceSourceType.RAG,
            location="retrieval:metadata",
            summary=f"HardwarePlan references RAG source identifier {source_id}.",
        )
    return (
        tuple(result),
        {key: tuple(value) for key, value in by_source.items()},
        datasheet_component_evidence,
    )


def _append_evidence(
    result: list[DesignEvidence],
    by_source: dict[str, list[str]],
    *,
    source_id: str,
    source_type: DesignEvidenceSourceType,
    location: str,
    summary: str,
) -> str:
    safe_summary = safe_text(summary, field="content_summary", max_length=512)
    evidence_id = _stable_id(
        "evidence",
        source_type.value,
        source_id,
        location,
        safe_summary,
    )
    source_evidence = by_source.setdefault(source_id, [])
    if evidence_id in source_evidence:
        return evidence_id
    result.append(
        DesignEvidence(
            evidence_id=evidence_id,
            source_id=source_id,
            source_type=source_type,
            location=location,
            content_summary=safe_summary,
            confidence=1.0,
        )
    )
    source_evidence.append(evidence_id)
    return evidence_id


def _gpio_projection(
    envelope: RealEngineeringEnvelope | None,
    evidence_by_source: dict[str, tuple[str, ...]],
    datasheet_component_evidence: str | None,
) -> tuple[tuple[GPIOAssignment, ...], tuple[DesignDecision, ...]]:
    if envelope is None or envelope.firmware_review is None:
        return (), ()
    findings = (
        cross_check(envelope.datasheet, envelope.firmware_review)
        if envelope.datasheet is not None
        else ()
    )
    datasheet_source = _datasheet_source(envelope)
    assignments: list[GPIOAssignment] = []
    decisions: list[DesignDecision] = []
    for assignment in envelope.firmware_review.gpio_assignments:
        firmware_finding_source = f"{assignment.source_id}#line:{assignment.line}"
        conflict = next(
            (
                finding
                for finding in findings
                if firmware_finding_source in finding.source_ids
            ),
            None,
        )
        sources = [assignment.source_id]
        evidence_ids = list(evidence_by_source.get(assignment.source_id, ()))
        if conflict is not None and datasheet_source is not None:
            sources.append(datasheet_source)
            if datasheet_component_evidence is not None:
                evidence_ids.append(datasheet_component_evidence)
        status = (
            GPIOAssignmentStatus.CONFLICT
            if conflict is not None
            else GPIOAssignmentStatus.UNRESOLVED
        )
        reason = (
            "Existing engineering cross-check reports a restricted-pin conflict; hardware connection correctness remains unresolved."
            if conflict is not None
            else "Observed in Firmware; hardware correctness is unresolved."
        )
        projected = GPIOAssignment(
            function=assignment.role,
            gpio=assignment.pin,
            interface="unresolved",
            reason=reason,
            status=status,
            source_ids=tuple(sources),
        )
        assignments.append(projected)
        decisions.append(
            _decision(
                "firmware_gpio_observation",
                f"Firmware review observes {assignment.pin} for role {assignment.role}.",
                reason,
                tuple(dict.fromkeys(evidence_ids)),
            )
        )
    return tuple(assignments), tuple(decisions)


def _decision(
    decision_type: str,
    decision: str,
    reason: str,
    evidence_ids: tuple[str, ...],
) -> DesignDecision:
    return DesignDecision(
        decision_id=_stable_id(
            "decision",
            decision_type,
            decision,
            reason,
            *evidence_ids,
        ),
        decision_type=decision_type,
        decision=decision,
        reason=reason,
        evidence_ids=evidence_ids,
        confidence=1.0,
    )


def _datasheet_source(envelope: RealEngineeringEnvelope | None) -> str | None:
    if envelope is None or envelope.datasheet is None:
        return None
    raw = envelope.datasheet.metadata.get("source_id")
    return _safe_source(raw)


def _rag_sources(plan: HardwarePlan) -> tuple[str, ...]:
    candidates: list[object] = []
    raw_plan_sources = plan.metadata.get("evidence_document_ids", [])
    if isinstance(raw_plan_sources, (list, tuple)):
        candidates.extend(raw_plan_sources)
    for component in plan.components:
        candidates.append(component.metadata.get("evidence_document_id"))
    return tuple(
        sorted(
            {
                source_id
                for candidate in candidates
                if (source_id := _safe_source(candidate)) is not None
            }
        )
    )


def _component_sources(
    component: HardwareComponent,
    rag_sources: tuple[str, ...],
) -> tuple[str, ...]:
    source_id = _safe_source(component.metadata.get("evidence_document_id"))
    return (source_id,) if source_id is not None and source_id in rag_sources else ()


def _safe_source(value: object) -> str | None:
    if value is None:
        return None
    try:
        return safe_identifier(value, field="source_id")
    except ValueError:
        return None


def _required_text(
    value: object,
    fallback: str,
    limitations: list[str],
) -> str:
    try:
        return safe_text(value, field="projected_value")
    except ValueError:
        limitations.append(fallback)
        return fallback


def _optional_text(value: object) -> str | None:
    try:
        return safe_text(value, field="projected_value")
    except ValueError:
        return None


def _safe_collection(
    values: list[str],
    limitations: list[str],
    unsafe_limitation: str,
) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        candidate = _optional_text(value)
        if candidate is None:
            limitations.append(unsafe_limitation)
        else:
            result.append(candidate)
    return tuple(result)


def _stable_id(prefix: str, *values: str) -> str:
    canonical = json.dumps(values, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"
