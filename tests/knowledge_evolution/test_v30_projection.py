from datetime import UTC, datetime

from embedded_copilot.engineering_memory import (
    ApprovalAudit,
    ApprovedEngineeringMemory,
    EngineeringMemoryType,
    InMemoryApprovedEngineeringMemoryStore,
)
from embedded_copilot.knowledge_evolution import (
    ApprovedMemoryKnowledgeEvolutionService,
)
from embedded_copilot.knowledge_evolution.adapters.memory import (
    ApprovedEngineeringMemoryKnowledgeAdapter,
)


def test_knowledge_evolution_reads_only_approved_memory_projection() -> None:
    store = InMemoryApprovedEngineeringMemoryStore()
    fact = ApprovedEngineeringMemory.create(
        memory_id="memory-knowledge",
        project_id="project-1",
        source_reference="conversation:session-1",
        memory_type=EngineeringMemoryType.ARCHITECTURE,
        summary="Keep memory projection read-only.",
        decision="Use a one-way projection.",
        reason="The source of truth remains Engineering Memory.",
        confidence=0.95,
        evidence=("conversation:session-1",),
        approval_audit=ApprovalAudit(
            approval_id="approval-knowledge",
            candidate_fingerprint="sha256:" + "b" * 64,
            reviewer="reviewer-1",
            decision="APPROVED",
            approved_at=datetime(2026, 8, 6, tzinfo=UTC),
        ),
    )
    store.save(fact)
    snapshot = ApprovedMemoryKnowledgeEvolutionService(
        ApprovedEngineeringMemoryKnowledgeAdapter(store)
    ).get_snapshot("project-1")
    assert snapshot is not None
    assert snapshot.nodes[0].attributes == (
        "ARCHITECTURE",
        fact.fingerprint,
        fact.approval_audit.candidate_fingerprint,
    )
