from embedded_copilot.engineering_intelligence import (
    EngineeringContextInputProjection,
    ContextStage,
    EvidenceSourceType,
    EvidenceTrustBasis,
    build_context_snapshot,
    build_evidence,
    build_recommendation,
    fuse_evidence,
)


def test_recommendation_binds_evidence_and_is_repeatable() -> None:
    context = build_context_snapshot(
        EngineeringContextInputProjection(
            project_id="project-1",
            project_name="Board",
            stage=ContextStage.PCB_DESIGN,
            decision_topic="interface",
            constraints=(),
        )
    )
    fused = fuse_evidence(
        (
            build_evidence(
                evidence_id="e-1",
                source_type=EvidenceSourceType.LOCAL_KNOWLEDGE,
                trust_basis=EvidenceTrustBasis.PROJECTED,
                summary="SPI guidance",
                reference_id="local-1",
                confidence=0.5,
                source_rank=0,
            ),
        )
    )
    first = build_recommendation(context, fused)
    second = build_recommendation(context, fused)
    assert first == second
    assert first.evidence_refs == ("e-1",)
    assert first.review_required is True
