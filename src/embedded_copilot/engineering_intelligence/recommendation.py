from __future__ import annotations

import copy

from .contracts import (
    EngineeringContextSnapshot,
    EngineeringKnowledgeContext,
    EngineeringRecommendation,
    canonical_fingerprint,
)


def build_recommendation(
    context: EngineeringContextSnapshot,
    knowledge: EngineeringKnowledgeContext,
) -> EngineeringRecommendation:
    checked_context = EngineeringContextSnapshot.model_validate(copy.deepcopy(context))
    checked_knowledge = EngineeringKnowledgeContext.model_validate(
        copy.deepcopy(knowledge)
    )
    top = checked_knowledge.evidence[0] if checked_knowledge.evidence else None
    if checked_knowledge.conflicts:
        conflict = checked_knowledge.conflicts[0]
        summary = (
            f"Resolve conflicting evidence for {conflict.subject} {conflict.parameter} "
            f"before deciding {checked_context.decision_topic}."
        )
    elif top is not None and top.claim is not None:
        summary = (
            f"Review {top.claim.subject} {top.claim.parameter}={top.claim.value} "
            f"from {top.reference_id} before deciding {checked_context.decision_topic}."
        )
    elif top is not None:
        summary = (
            f"Review evidence {top.reference_id} before deciding "
            f"{checked_context.decision_topic}."
        )
    else:
        summary = (
            f"Collect verified engineering evidence before deciding "
            f"{checked_context.decision_topic}."
        )
    risks = list(checked_context.constraints)
    if checked_knowledge.conflicts:
        risks.append("Conflicting evidence requires engineering review")
    if top is None:
        risks.append("No usable evidence is available")
    elif top.trust_basis.value != "VERIFIED":
        risks.append("Top evidence is not verified")
    for status in checked_knowledge.source_statuses:
        if status.status.value in {"UNAVAILABLE", "PARTIAL", "INVALID"}:
            risks.append(
                f"{status.source_type.value} evidence is {status.status.value}"
            )
    risk_values = tuple(dict.fromkeys(risks))
    material = EngineeringRecommendation.model_construct(
        recommendation_id="recommendation-" + checked_knowledge.fingerprint[7:31],
        title=f"{checked_context.project_name}: {checked_context.decision_topic} recommendation",
        summary=summary,
        evidence_refs=checked_knowledge.evidence_refs,
        confidence=checked_knowledge.confidence,
        risks=risk_values,
        conflicts=checked_knowledge.conflicts,
        review_required=True,
        fingerprint="sha256:" + "0" * 64,
    )
    return EngineeringRecommendation.model_validate(
        {
            **material.model_dump(mode="python"),
            "fingerprint": canonical_fingerprint(material, exclude={"fingerprint"}),
        }
    )
