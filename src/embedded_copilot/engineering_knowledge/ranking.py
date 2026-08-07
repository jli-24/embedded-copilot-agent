from __future__ import annotations

from .models import EngineeringKnowledgeNode, tokens


def rank_nodes(
    nodes: tuple[EngineeringKnowledgeNode, ...],
    query: str,
    distances: dict[str, int],
) -> tuple[EngineeringKnowledgeNode, ...]:
    query_tokens = tokens(query)

    def key(node: EngineeringKnowledgeNode) -> tuple[int, int, int, str]:
        overlap = len(query_tokens & tokens(f"{node.entity_name} {node.summary}"))
        exact = int(node.entity_name.casefold() == query.casefold())
        return (-exact, -overlap, distances.get(node.node_id, 10**6), node.node_id)

    return tuple(sorted(nodes, key=key))


__all__ = ("rank_nodes",)
