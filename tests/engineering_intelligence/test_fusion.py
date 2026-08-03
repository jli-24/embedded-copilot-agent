from embedded_copilot.engineering_intelligence import (
    EngineeringEvidence,
    EvidenceClaim,
    EvidenceSourceType,
    EvidenceTrustBasis,
    EngineeringKnowledgeContext,
    build_evidence,
    fuse_evidence,
)


def _evidence(evidence_id: str, value: str, rank: int) -> EngineeringEvidence:
    return build_evidence(
        evidence_id=evidence_id,
        source_type=EvidenceSourceType.DATASHEET,
        trust_basis=EvidenceTrustBasis.PROJECTED,
        summary="candidate",
        reference_id=evidence_id,
        confidence=0.5,
        source_rank=rank,
        claim=EvidenceClaim(
            subject="camera",
            parameter="interface",
            value=value,
            unit="",
        ),
    )


def test_fusion_is_deterministic_and_keeps_conflicts() -> None:
    result = fuse_evidence((_evidence("b", "I2C", 1), _evidence("a", "SPI", 0)))
    assert isinstance(result, EngineeringKnowledgeContext)
    assert result.evidence_refs == ("a", "b")
    assert len(result.conflicts) == 1
    assert result.confidence == 0.5
    assert result == fuse_evidence((result.evidence[1], result.evidence[0]))
