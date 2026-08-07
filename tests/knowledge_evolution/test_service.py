from __future__ import annotations

from embedded_copilot.knowledge_evolution.adapters.fake import FakeKnowledgeEvolutionPort
from embedded_copilot.knowledge_evolution.service import KnowledgeEvolutionService


def test_service_revalidates_read_only_knowledge_projection() -> None:
    snapshot = KnowledgeEvolutionService(FakeKnowledgeEvolutionPort()).get_snapshot("demo")
    assert snapshot is not None
    assert snapshot.project_id == "demo"
    assert all(node.project_id == "demo" for node in snapshot.nodes)
