from __future__ import annotations

from .contracts import EvidenceSourceType, EvidenceTrustBasis, EngineeringEvidence

_TIERS = {
    (EvidenceSourceType.DATASHEET, EvidenceTrustBasis.VERIFIED): 6000,
    (EvidenceSourceType.MEMORY, EvidenceTrustBasis.VERIFIED): 5000,
    (EvidenceSourceType.MEMORY, EvidenceTrustBasis.HUMAN_APPROVED): 4500,
    (EvidenceSourceType.DATASHEET, EvidenceTrustBasis.PROJECTED): 4000,
    (EvidenceSourceType.LOCAL_KNOWLEDGE, EvidenceTrustBasis.PROJECTED): 3000,
    (EvidenceSourceType.WEB, EvidenceTrustBasis.PROJECTED): 2000,
}
_CAPS = {
    EvidenceTrustBasis.VERIFIED: 1.0,
    EvidenceTrustBasis.HUMAN_APPROVED: 0.5,
    EvidenceTrustBasis.PROJECTED: 0.5,
    EvidenceTrustBasis.UNKNOWN: 0.0,
}


def evidence_tier(value: EngineeringEvidence) -> int:
    return _TIERS.get((value.source_type, value.trust_basis), 1000)


def evidence_cap(value: EngineeringEvidence) -> float:
    return _CAPS[value.trust_basis]


def ranking_key(value: EngineeringEvidence) -> tuple[object, ...]:
    return (
        -evidence_tier(value),
        -value.confidence,
        value.source_rank,
        value.source_type.value,
        value.reference_id,
        value.evidence_id,
    )
