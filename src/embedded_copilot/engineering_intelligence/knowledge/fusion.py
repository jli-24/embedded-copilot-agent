"""Content-minimized fusion of caller-projected engineering evidence."""

from __future__ import annotations

from collections import defaultdict

from embedded_copilot.engineering_intelligence.models import (
    EngineeringContextRequest,
    EngineeringContextSnapshot,
    EngineeringDecisionProjection,
    EvidenceStatus,
    context_snapshot_fingerprint,
)


def build_engineering_context(
    request: EngineeringContextRequest,
) -> EngineeringContextSnapshot:
    checked = _typed_copy(request, EngineeringContextRequest)
    if (
        checked.project.project_id != checked.requirement.project_id
        or checked.project.project_id != checked.plan.project_id
        or checked.requirement.fingerprint != checked.plan.requirement_fingerprint
    ):
        raise ValueError("context binding mismatch")

    evidence = tuple(sorted(checked.evidence, key=lambda item: item.evidence_id))
    if len({item.evidence_id for item in evidence}) != len(evidence):
        raise ValueError("duplicate evidence")
    facts: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in evidence:
        facts[(item.fact_type, item.key)].add(item.value)
    conflict_count = sum(len(values) > 1 for values in facts.values())

    decisions = tuple(
        EngineeringDecisionProjection(
            item=item.key,
            choice=item.value,
            reason="CALLER_REQUIREMENT",
            evidence_ids=tuple(
                evidence_item.evidence_id
                for evidence_item in evidence
                if evidence_item.status is EvidenceStatus.VERIFIED
                and evidence_item.value == item.value
            ),
        )
        for item in checked.requirement.hardware_constraints
    )
    verified = tuple(
        item.confidence for item in evidence if item.status is EvidenceStatus.VERIFIED
    )
    confidence = min(verified) if verified else 0.0
    values = dict(
        project=checked.project,
        requirement_fingerprint=checked.requirement.fingerprint,
        plan_fingerprint=checked.plan.fingerprint,
        evidence=evidence,
        decisions=decisions,
        confidence=confidence,
        conflict_count=conflict_count,
        review_required=True,
    )
    return EngineeringContextSnapshot(
        **values,
        fingerprint=context_snapshot_fingerprint(**values),
    )


def _typed_copy(value: object, expected_type):
    if type(value) is not expected_type:
        raise TypeError("typed context request is required")
    copied = value.model_copy(deep=True)
    return expected_type.model_validate(copied)
