from __future__ import annotations

from ..contracts import (
    EngineeringKnowledgeNode,
    EngineeringKnowledgeRelation,
    EngineeringKnowledgeSnapshot,
    KnowledgeConfidence,
    KnowledgeEntityType,
    KnowledgeEvolutionPort,
    KnowledgeQueryRequest,
    KnowledgeRelationType,
    KnowledgeRetrievalPort,
    KnowledgeSuggestion,
)


def _snapshot(project_id: str) -> EngineeringKnowledgeSnapshot:
    hardware = EngineeringKnowledgeNode.create(
        node_id=f"node:{project_id}:hardware",
        project_id=project_id,
        entity_type=KnowledgeEntityType.HARDWARE,
        reference=f"hardware:{project_id}",
        attributes=("board profile",),
        confidence=KnowledgeConfidence.PROJECTED,
    )
    validation = EngineeringKnowledgeNode.create(
        node_id=f"node:{project_id}:validation",
        project_id=project_id,
        entity_type=KnowledgeEntityType.VALIDATION,
        reference=f"validation:{project_id}",
        attributes=("historical result",),
        confidence=KnowledgeConfidence.VERIFIED,
    )
    relation = EngineeringKnowledgeRelation.create(
        relation_id=f"relation:{project_id}:1",
        source_id=hardware.node_id,
        target_id=validation.node_id,
        relation_type=KnowledgeRelationType.VALIDATED_BY,
        evidence_reference=f"evidence:{project_id}",
        confidence=KnowledgeConfidence.VERIFIED,
    )
    return EngineeringKnowledgeSnapshot.create(
        project_id=project_id,
        nodes=(hardware, validation),
        relations=(relation,),
    )


class FakeKnowledgeEvolutionPort(KnowledgeEvolutionPort):
    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot:
        return _snapshot(project_id)


class FakeKnowledgeRetrievalPort(KnowledgeRetrievalPort):
    def query(self, request: KnowledgeQueryRequest) -> tuple[KnowledgeSuggestion, ...]:
        return (
            KnowledgeSuggestion.create(
                recommendation_id=f"recommendation:{request.project_id}:1",
                project_id=request.project_id,
                matched_reference=f"validation:{request.project_id}",
                reason="Historical validation evidence matches the requested engineering context.",
                evidence_reference=f"evidence:{request.project_id}",
                confidence=KnowledgeConfidence.PROJECTED,
                risk="Projection requires engineering review before reuse.",
            ),
        )


__all__ = ["FakeKnowledgeEvolutionPort", "FakeKnowledgeRetrievalPort"]
