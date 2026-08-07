from __future__ import annotations

import copy
from typing import Final

from .contracts import ApprovedEngineeringMemoryProjectionPort
from .exceptions import EngineeringKnowledgeProjectionRejected
from .graph import build_graph_snapshot
from .models import (
    EngineeringGraphSnapshot,
    EngineeringKnowledgeNode,
    NodeType,
    identifier,
)
from .relation import DeterministicRelationProjector

_NODE_TYPE_MAP: Final[tuple[tuple[str, NodeType], ...]] = (
    ("REQUIREMENT", NodeType.REQUIREMENT),
    ("ARCHITECTURE", NodeType.CONSTRAINT),
    ("DECISION", NodeType.DECISION),
    ("INTERFACE", NodeType.INTERFACE),
    ("DEBUG_EXPERIENCE", NodeType.PROBLEM),
    ("OPTIMIZATION", NodeType.SOLUTION),
    ("VALIDATION", NodeType.MEMORY),
    ("TRADEOFF", NodeType.CONSTRAINT),
)


def _node_type(memory_type: object) -> NodeType:
    value = memory_type.value if hasattr(memory_type, "value") else memory_type
    return next(
        (node_type for candidate, node_type in _NODE_TYPE_MAP if candidate == value),
        NodeType.MEMORY,
    )


class EngineeringKnowledgeGraphProjectionService:
    """Read-only projection from approved facts into a graph snapshot."""

    __slots__ = ("_memory_port", "_relation_projector")

    def __init__(
        self,
        memory_port: ApprovedEngineeringMemoryProjectionPort,
        relation_projector: DeterministicRelationProjector | None = None,
    ) -> None:
        if not isinstance(memory_port, ApprovedEngineeringMemoryProjectionPort):
            raise TypeError("approved memory projection port is invalid")
        self._memory_port = memory_port
        self._relation_projector = relation_projector or DeterministicRelationProjector()

    def project(self, project_id: str) -> EngineeringGraphSnapshot | None:
        project = identifier(project_id, field="project_id")
        values = self._memory_port.list_approved(copy.deepcopy(project))
        if not isinstance(values, tuple):
            raise EngineeringKnowledgeProjectionRejected()
        memories: list[object] = []
        for value in values:
            try:
                validator = getattr(type(value), "model_validate", None)
                if not callable(validator):
                    raise TypeError("approved memory projection is invalid")
                memory = validator(copy.deepcopy(value))
            except Exception as error:
                raise EngineeringKnowledgeProjectionRejected() from error
            if memory.status != "APPROVED" or memory.project_id != project:
                raise EngineeringKnowledgeProjectionRejected()
            memories.append(memory)
        if not memories:
            return None
        checked_memories = tuple(sorted(memories, key=lambda item: item.memory_id))
        nodes = tuple(
            EngineeringKnowledgeNode.create(
                node_id=f"memory-{memory.memory_id}",
                project_id=project,
                node_type=_node_type(memory.memory_type),
                entity_name=memory.memory_id,
                summary=memory.summary,
                source_memory_id=memory.memory_id,
                source_reference=memory.source_reference,
                confidence=memory.confidence,
                verification_status="APPROVED",
            )
            for memory in checked_memories
        )
        relations = self._relation_projector.project(checked_memories, nodes)
        return build_graph_snapshot(
            project_id=project,
            nodes=nodes,
            relations=relations,
        )


__all__ = ("EngineeringKnowledgeGraphProjectionService",)
