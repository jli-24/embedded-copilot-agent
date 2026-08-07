from __future__ import annotations

from embedded_copilot.engineering_knowledge import (
    EngineeringGraphSnapshot,
    EngineeringKnowledgeNode,
    NodeType,
)
from embedded_copilot.knowledge_writer import artifact_from_approved_graph_snapshot


def test_graph_markdown_projection_is_one_artifact_per_node() -> None:
    node = EngineeringKnowledgeNode.create(
        node_id="memory-1",
        project_id="project-1",
        node_type=NodeType.DECISION,
        entity_name="memory-1",
        summary="approved decision",
        source_memory_id="memory-1",
        source_reference="decision:1",
        confidence=0.9,
        verification_status="APPROVED",
    )
    snapshot = EngineeringGraphSnapshot.create(
        project_id="project-1", nodes=(node,), relations=()
    )
    artifacts = artifact_from_approved_graph_snapshot(snapshot)
    assert len(artifacts) == 1
    assert artifacts[0].relative_path == (
        "docs/knowledge/99_KnowledgeGraph/memory-1.md"
    )
