from __future__ import annotations

import copy

from embedded_copilot.engineering_knowledge.models import (
    EngineeringGraphSnapshot,
    validate_graph_snapshot,
)

from .contracts import (
    ApprovedEngineeringMemoryProjectionPort,
    EngineeringKnowledgeGraphProjectionPort,
    EngineeringKnowledgeSnapshot,
    EngineeringMemoryProjectionPort,
    validate_snapshot,
)
from .exceptions import KnowledgeRejected
from .models import identifier


class KnowledgeEvolutionService:
    __slots__ = ("_port",)

    def __init__(self, port: EngineeringMemoryProjectionPort) -> None:
        if not isinstance(port, EngineeringMemoryProjectionPort):
            raise TypeError("knowledge evolution port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None:
        try:
            project = identifier(project_id, field="project_id")
            value = self._port.get_snapshot(copy.deepcopy(project))
            if value is None:
                return None
            checked = validate_snapshot(value)
            if checked.project_id != project:
                raise ValueError("project binding mismatch")
            return checked
        except Exception as error:
            raise KnowledgeRejected() from error


class ApprovedMemoryKnowledgeEvolutionService:
    __slots__ = ("_port",)

    def __init__(self, port: ApprovedEngineeringMemoryProjectionPort) -> None:
        if not isinstance(port, ApprovedEngineeringMemoryProjectionPort):
            raise TypeError("approved memory projection port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None:
        try:
            project = identifier(project_id, field="project_id")
            values = self._port.list_approved(copy.deepcopy(project))
            if not isinstance(values, tuple):
                raise TypeError("approved memory projection must be a tuple")
            from .adapters.memory import ApprovedEngineeringMemoryKnowledgeAdapter

            snapshot = ApprovedEngineeringMemoryKnowledgeAdapter(
                _TupleApprovedMemorySource(values)
            ).get_snapshot(project)
            return None if snapshot is None else validate_snapshot(snapshot)
        except Exception as error:
            raise KnowledgeRejected() from error


class EngineeringKnowledgeGraphEvolutionService:
    """Consume immutable graph projections without mutating graph data."""

    __slots__ = ("_port",)

    def __init__(self, port: EngineeringKnowledgeGraphProjectionPort) -> None:
        if not isinstance(port, EngineeringKnowledgeGraphProjectionPort):
            raise TypeError("engineering knowledge graph port is invalid")
        self._port = port

    def get_snapshot(self, project_id: str) -> EngineeringGraphSnapshot | None:
        try:
            project = identifier(project_id, field="project_id")
            value = self._port.project(copy.deepcopy(project))
            if value is None:
                return None
            snapshot = validate_graph_snapshot(value)
            if snapshot.project_id != project:
                raise ValueError("graph project binding mismatch")
            return snapshot
        except Exception as error:
            raise KnowledgeRejected() from error


class _TupleApprovedMemorySource:
    __slots__ = ("_values",)

    def __init__(self, values) -> None:
        self._values = values

    def list(self, project_id: str):
        return tuple(value for value in self._values if value.project_id == project_id)


__all__ = [
    "ApprovedMemoryKnowledgeEvolutionService",
    "EngineeringKnowledgeGraphEvolutionService",
    "KnowledgeEvolutionService",
]
