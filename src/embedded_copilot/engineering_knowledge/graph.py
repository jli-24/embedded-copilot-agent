from __future__ import annotations

from .models import (
    EngineeringGraphSnapshot,
    EngineeringKnowledgeNode,
    EngineeringRelation,
)


def build_graph_snapshot(
    *,
    project_id: str,
    nodes: tuple[EngineeringKnowledgeNode, ...],
    relations: tuple[EngineeringRelation, ...],
) -> EngineeringGraphSnapshot:
    return EngineeringGraphSnapshot.create(
        project_id=project_id,
        nodes=tuple(sorted(nodes, key=lambda node: node.node_id)),
        relations=tuple(sorted(relations, key=lambda relation: relation.relation_id)),
    )


__all__ = ("build_graph_snapshot",)
