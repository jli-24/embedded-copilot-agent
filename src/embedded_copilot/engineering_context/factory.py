from __future__ import annotations

from .contracts import (
    ApprovedMemoryProjectionPort,
    DatasheetMetadataProjectionPort,
    EngineeringGraphProjectionPort,
    KnowledgeEvolutionProjectionPort,
)
from .service import EngineeringContextService


def create_engineering_context_service(
    *,
    memory_port: ApprovedMemoryProjectionPort,
    graph_port: EngineeringGraphProjectionPort,
    knowledge_port: KnowledgeEvolutionProjectionPort | None = None,
    datasheet_port: DatasheetMetadataProjectionPort | None = None,
) -> EngineeringContextService:
    return EngineeringContextService(
        memory_port=memory_port,
        graph_port=graph_port,
        knowledge_port=knowledge_port,
        datasheet_port=datasheet_port,
    )


__all__ = ("create_engineering_context_service",)
