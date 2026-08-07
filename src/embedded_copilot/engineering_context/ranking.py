from __future__ import annotations

from collections import deque

from .models import EngineeringContextItem, tokens


def _status_rank(value: str) -> int:
    return {
        "APPROVED": 4,
        "VERIFIED": 3,
        "PROJECTED": 2,
        "SOURCE_METADATA": 1,
    }.get(value, 0)


def relation_distances(
    graph: object | None,
    query: str,
) -> dict[str, int]:
    if graph is None:
        return {}
    query_tokens = tokens(query)
    anchors = tuple(
        node.node_id
        for node in graph.nodes
        if node.entity_name.casefold() == query.casefold()
        or query_tokens & tokens(f"{node.entity_name} {node.summary}")
    )
    if not anchors:
        return {}
    adjacency: dict[str, set[str]] = {node.node_id: set() for node in graph.nodes}
    for relation in graph.relations:
        adjacency[relation.source_node_id].add(relation.target_node_id)
        adjacency[relation.target_node_id].add(relation.source_node_id)
    distances: dict[str, int] = {}
    queue = deque((anchor, 0) for anchor in sorted(set(anchors)))
    while queue:
        current, distance = queue.popleft()
        if current in distances and distances[current] <= distance:
            continue
        distances[current] = distance
        for neighbor in sorted(adjacency[current]):
            queue.append((neighbor, distance + 1))
    return distances


def rank_items(
    items: tuple[EngineeringContextItem, ...],
    query: str,
    graph: object | None,
    limit: int,
) -> tuple[EngineeringContextItem, ...]:
    query_tokens = tokens(query)
    distances = relation_distances(graph, query)

    def key(item: EngineeringContextItem) -> tuple[int, int, int, float, int, str]:
        exact = int(item.entity_name.casefold() == query.casefold())
        overlap = len(query_tokens & tokens(f"{item.entity_name} {item.summary}"))
        return (
            -exact,
            distances.get(item.item_id, 10**6),
            -overlap,
            -item.confidence,
            -_status_rank(item.verification_status),
            item.item_id,
        )

    return tuple(sorted(items, key=key)[:limit])


__all__ = ("rank_items", "relation_distances")
