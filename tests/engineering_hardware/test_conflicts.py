from __future__ import annotations

from embedded_copilot.engineering_hardware import (
    ComponentSelectionStatus,
    HardwareEngineeringRequest,
    HardwareFindingCode,
    create_engineering_hardware_runtime,
)
from embedded_copilot.engineering_intelligence import (
    EngineeringContextRequest,
    RequirementConstraint,
    create_engineering_intelligence_runtime,
)
from embedded_copilot.engineering_intelligence.models import (
    EngineeringRequirementDocument,
    context_snapshot_fingerprint,
    requirement_document_fingerprint,
)

from .conftest import NOW, evidence


def _proposal(snapshot):
    return (
        create_engineering_hardware_runtime()
        .hardware_engineering_port()
        .prepare_proposal(
            HardwareEngineeringRequest(
                proposal_id="proposal-conflict",
                requirement=snapshot.requirement,
                plan=snapshot.plan,
                context=snapshot.context,
                proposed_at=NOW,
            )
        )
    )


def _requirement_with_constraints(snapshot, constraints):
    values = dict(
        project_id=snapshot.requirement.project_id,
        session_id=snapshot.requirement.session_id,
        message_id=snapshot.requirement.message_id,
        product=snapshot.requirement.product,
        functional_requirements=snapshot.requirement.functional_requirements,
        performance_requirements=snapshot.requirement.performance_requirements,
        hardware_constraints=constraints,
        software_constraints=snapshot.requirement.software_constraints,
        power_requirements=snapshot.requirement.power_requirements,
        communication_requirements=snapshot.requirement.communication_requirements,
        review_required=True,
    )
    return EngineeringRequirementDocument(
        **values,
        fingerprint=requirement_document_fingerprint(**values),
    )


def test_conflicting_requirement_candidates_are_excluded_from_bom(
    intelligence_snapshot,
) -> None:
    requirement = _requirement_with_constraints(
        intelligence_snapshot,
        (
            RequirementConstraint(key="MCU", value="ESP32-S3"),
            RequirementConstraint(key="MCU", value="STM32H7"),
        ),
    )
    plan = (
        create_engineering_intelligence_runtime()
        .engineering_intelligence_port()
        .create_plan(requirement)
    )
    context_values = dict(
        project=intelligence_snapshot.context.project,
        requirement_fingerprint=requirement.fingerprint,
        plan_fingerprint=plan.fingerprint,
        evidence=(),
        decisions=(),
        confidence=0.0,
        conflict_count=0,
        review_required=True,
    )
    context = type(intelligence_snapshot.context)(
        **context_values,
        fingerprint=context_snapshot_fingerprint(**context_values),
    )
    snapshot = intelligence_snapshot.model_copy(
        update={"requirement": requirement, "plan": plan, "context": context},
        deep=True,
    )

    proposal = _proposal(snapshot)

    assert tuple(item.status for item in proposal.component_selection.items) == (
        ComponentSelectionStatus.CONFLICT,
    )
    assert proposal.bom.items == ()
    assert HardwareFindingCode.CONSTRAINT_CONFLICT in proposal.review.finding_codes


def test_verified_evidence_conflict_is_reported_without_partial_authority(
    intelligence_snapshot,
) -> None:
    conflicting = evidence(
        evidence_id="evidence-mcu-conflict",
        key="mcu",
        value="STM32H7",
    )
    context = (
        create_engineering_intelligence_runtime()
        .engineering_intelligence_port()
        .build_context(
            EngineeringContextRequest(
                project=intelligence_snapshot.context.project,
                requirement=intelligence_snapshot.requirement,
                plan=intelligence_snapshot.plan,
                evidence=(
                    next(
                        item
                        for item in intelligence_snapshot.context.evidence
                        if item.evidence_id == "evidence-mcu"
                    ),
                    conflicting,
                ),
                requested_at=NOW,
            )
        )
    )
    snapshot = intelligence_snapshot.model_copy(
        update={"context": context},
        deep=True,
    )

    proposal = _proposal(snapshot)

    mcu = next(
        item
        for item in proposal.component_selection.items
        if item.requirement_key == "MCU"
    )
    assert mcu.status is ComponentSelectionStatus.CONFLICT
    assert mcu.evidence_ids == ()
    assert HardwareFindingCode.VERIFIED_EVIDENCE_CONFLICT in (
        proposal.review.finding_codes
    )


def test_candidate_evidence_never_enters_authoritative_trace(
    intelligence_snapshot,
) -> None:
    proposal = _proposal(intelligence_snapshot)

    assert tuple(item.evidence_id for item in proposal.evidence_trace) == (
        "evidence-mcu",
    )
    assert "evidence-camera-candidate" not in proposal.model_dump_json()
