"""Payload-free Engineering Memory context projection."""

from embedded_copilot.engineering_memory.context import MemoryContext

from embedded_copilot.engineering_intelligence.exceptions import (
    EngineeringIntelligenceRejected,
)
from embedded_copilot.engineering_intelligence.models import (
    EngineeringKnowledgeEvidence,
    EngineeringKnowledgeSourceType,
    EvidenceStatus,
    engineering_evidence_fingerprint,
)


def project_verified_memory(value: object) -> tuple[EngineeringKnowledgeEvidence, ...]:
    try:
        if type(value) is not MemoryContext:
            raise TypeError("typed memory context is required")
        copied = value.model_copy(deep=True)
        checked = MemoryContext.model_validate(copied)
        projected = []
        for item in checked.evidence:
            values = dict(
                evidence_id=f"memory:{item.record_id}",
                source_type=EngineeringKnowledgeSourceType.MEMORY,
                fact_type=item.memory_type.value,
                key="memory_reference",
                value=item.logical_key,
                summary="Verified engineering memory reference.",
                status=EvidenceStatus.VERIFIED,
                confidence=1.0,
                reference_ids=(item.provenance_reference,),
                observed_at=item.last_transition_at,
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
