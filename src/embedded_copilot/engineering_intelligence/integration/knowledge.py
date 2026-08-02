"""Verified Knowledge Intelligence result projection."""

from embedded_copilot.knowledge.intelligence import KnowledgeIntelligenceResult

from embedded_copilot.engineering_intelligence.exceptions import (
    EngineeringIntelligenceRejected,
)
from embedded_copilot.engineering_intelligence.models import (
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EvidenceStatus,
    engineering_evidence_fingerprint,
)


def project_verified_knowledge(
    value: object,
) -> tuple[EngineeringKnowledgeEvidence, ...]:
    try:
        if type(value) is not KnowledgeIntelligenceResult:
            raise TypeError("typed knowledge result is required")
        copied = value.model_copy(deep=True)
        checked = KnowledgeIntelligenceResult.model_validate(copied)
        projected = []
        for item in checked.verified_evidence:
            references = tuple(sorted({entry.reference for entry in item.provenance}))
            values = dict(
                evidence_id=item.evidence_id,
                source_type=EngineeringKnowledgeSourceType.RAG,
                fact_type=item.entity_type.value,
                key=item.fact_key,
                value=item.canonical_value,
                summary=item.summary,
                status=EvidenceStatus.VERIFIED,
                confidence=1.0,
                reference_ids=references,
                observed_at=max(entry.verified_at for entry in item.provenance),
            )
            projected.append(
                EngineeringKnowledgeEvidence(
                    **values,
                    fingerprint=engineering_evidence_fingerprint(**values),
                )
            )
        return tuple(sorted(projected, key=lambda item: item.evidence_id))
    except Exception:
        raise EngineeringIntelligenceRejected("intelligence request rejected") from None
