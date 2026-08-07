from __future__ import annotations

from .contracts import (
    ApprovedEngineeringMemoryProjectionPort,
    EngineeringKnowledgeProjectionPort,
)
from .projection import EngineeringKnowledgeGraphProjectionService
from .retrieval import EngineeringContextRetrievalService


def create_engineering_knowledge_projection(
    memory_port: ApprovedEngineeringMemoryProjectionPort,
) -> EngineeringKnowledgeGraphProjectionService:
    return EngineeringKnowledgeGraphProjectionService(memory_port)


def create_engineering_context_provider(
    graph_port: EngineeringKnowledgeProjectionPort,
) -> EngineeringContextRetrievalService:
    return EngineeringContextRetrievalService(graph_port)


__all__ = (
    "create_engineering_context_provider",
    "create_engineering_knowledge_projection",
)
