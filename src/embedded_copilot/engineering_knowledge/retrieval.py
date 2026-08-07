from __future__ import annotations

import copy
from collections import deque

from .contracts import (
    EngineeringContextProviderPort,
    EngineeringKnowledgeProjectionPort,
)
from .exceptions import EngineeringKnowledgeUnavailable
from .models import (
    EngineeringContextQuery,
    EngineeringContextSnapshot,
    EngineeringGraphSnapshot,
    EngineeringKnowledgeNode,
    NodeType,
    tokens,
    validate_graph_snapshot,
)
from .ranking import rank_nodes


def _distances(snapshot: EngineeringGraphSnapshot, query: str) -> dict[str, int]:
    query_tokens = tokens(query)
    seeds = tuple(
        node.node_id
        for node in snapshot.nodes
        if node.entity_name.casefold() == query.casefold()
        or query_tokens & tokens(f"{node.entity_name} {node.summary}")
    )
    if not seeds:
        return {}
    adjacency: dict[str, tuple[str, ...]] = {
        node.node_id: () for node in snapshot.nodes
    }
    mutable: dict[str, list[str]] = {node_id: [] for node_id in adjacency}
    for relation in snapshot.relations:
        mutable[relation.source_node_id].append(relation.target_node_id)
        mutable[relation.target_node_id].append(relation.source_node_id)
    adjacency = {
        node_id: tuple(sorted(neighbors))
        for node_id, neighbors in mutable.items()
    }
    distances = {node_id: 0 for node_id in seeds}
    queue = deque(seeds)
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


def _category(
    nodes: tuple[EngineeringKnowledgeNode, ...], node_type: NodeType
) -> tuple[EngineeringKnowledgeNode, ...]:
    return tuple(node for node in nodes if node.node_type is node_type)


class EngineeringContextRetrievalService(EngineeringContextProviderPort):
    __slots__ = ("_graph_port",)

    def __init__(self, graph_port: EngineeringKnowledgeProjectionPort) -> None:
        if not isinstance(graph_port, EngineeringKnowledgeProjectionPort):
            raise TypeError("engineering graph projection port is invalid")
        self._graph_port = graph_port

    def get_context(
        self, query: EngineeringContextQuery
    ) -> EngineeringContextSnapshot | None:
        checked_query = EngineeringContextQuery.model_validate(copy.deepcopy(query))
        value = self._graph_port.project(copy.deepcopy(checked_query.project_id))
        if value is None:
            return None
        try:
            graph = validate_graph_snapshot(value)
        except Exception as error:
            raise EngineeringKnowledgeUnavailable() from error
        if graph.project_id != checked_query.project_id:
            raise EngineeringKnowledgeUnavailable()
        distances = _distances(graph, checked_query.query)
        ranked = rank_nodes(graph.nodes, checked_query.query, distances)
        related_nodes = tuple(
            node
            for node in ranked
            if node.node_id in distances and distances[node.node_id] <= 2
        )[: checked_query.limit]
        related_ids = frozenset(node.node_id for node in related_nodes)
        related_relations = tuple(
            relation
            for relation in graph.relations
            if relation.source_node_id in related_ids
            and relation.target_node_id in related_ids
        )
        return EngineeringContextSnapshot.create(
            project_id=graph.project_id,
            query=checked_query.query,
            related_nodes=tuple(
                EngineeringKnowledgeNode.model_validate(copy.deepcopy(node))
                for node in related_nodes
            ),
            related_relations=tuple(
                type(relation).model_validate(copy.deepcopy(relation))
                for relation in related_relations
            ),
            historical_decisions=_category(related_nodes, NodeType.DECISION),
            known_problems=_category(related_nodes, NodeType.PROBLEM),
            solutions=_category(related_nodes, NodeType.SOLUTION),
            constraints=_category(related_nodes, NodeType.CONSTRAINT),
            graph_fingerprint=graph.fingerprint,
        )

    retrieve = get_context


__all__ = ("EngineeringContextRetrievalService",)
