from __future__ import annotations

from .models import EngineeringContextItem, EngineeringContextQuery
from .ranking import rank_items


class EngineeringContextRetrievalService:
    """Read-only deterministic item retrieval."""

    def retrieve(
        self,
        *,
        items: tuple[EngineeringContextItem, ...],
        graph: object | None,
        query: EngineeringContextQuery,
    ) -> tuple[EngineeringContextItem, ...]:
        return retrieve_items(items=items, graph=graph, query=query)


def retrieve_items(
    *,
    items: tuple[EngineeringContextItem, ...],
    graph: object | None,
    query: EngineeringContextQuery,
) -> tuple[EngineeringContextItem, ...]:
    return rank_items(items, query.query, graph, query.limit)


__all__ = ("EngineeringContextRetrievalService", "retrieve_items")
