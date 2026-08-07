from __future__ import annotations

from typing import Protocol

from embedded_copilot.engineering_memory.models import (
    EngineeringMemorySnapshot,
    MemorySnapshotType,
)
from embedded_copilot.engineering_memory import ApprovedEngineeringMemory

from ..contracts import (
    EngineeringKnowledgeNode,
    EngineeringKnowledgeSnapshot,
    KnowledgeConfidence,
    KnowledgeEntityType,
    EngineeringMemoryProjectionPort,
    ApprovedEngineeringMemoryProjectionPort,
)


class _SnapshotSource(Protocol):
    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None: ...


class MemoryKnowledgeAdapter(EngineeringMemoryProjectionPort):
    def __init__(self, source: _SnapshotSource) -> None:
        self._source = source

    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None:
        return self._source.get_snapshot(project_id)


MemoryProjectionAdapter = MemoryKnowledgeAdapter


class EngineeringMemorySnapshotSource(Protocol):
    def get_verified_snapshot(self, project_id: str) -> EngineeringMemorySnapshot | None: ...


class EngineeringMemoryProjectionAdapter(EngineeringMemoryProjectionPort):
    def __init__(self, source: EngineeringMemorySnapshotSource) -> None:
        self._source = source

    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None:
        snapshot = self._source.get_verified_snapshot(project_id)
        if snapshot is None:
            return None
        if snapshot.snapshot_type is not MemorySnapshotType.VERIFIED:
            raise ValueError("knowledge evolution requires verified memory")
        nodes = tuple(
            EngineeringKnowledgeNode.create(
                node_id=f"memory:{record.record_id}",
                project_id=snapshot.project_id,
                entity_type=(
                    KnowledgeEntityType.DECISION
                    if record.memory_type.value == "ENGINEERING_DECISION"
                    else KnowledgeEntityType.CONSTRAINT
                ),
                reference=record.logical_key,
                attributes=(record.provenance.source_reference,),
                confidence=KnowledgeConfidence.VERIFIED,
            )
            for record in snapshot.records
        )
        return EngineeringKnowledgeSnapshot.create(
            project_id=snapshot.project_id,
            nodes=nodes,
            relations=(),
        )


class ApprovedEngineeringMemoryKnowledgeAdapter(
    ApprovedEngineeringMemoryProjectionPort
):
    def __init__(self, source) -> None:
        self._source = source

    def list_approved(self, project_id: str) -> tuple[ApprovedEngineeringMemory, ...]:
        values = self._source.list(project_id)
        if not isinstance(values, tuple):
            raise ValueError("approved memory projection must be a tuple")
        return tuple(
            ApprovedEngineeringMemory.model_validate(value.model_copy(deep=True))
            for value in values
            if value.status == "APPROVED"
        )

    def get_snapshot(self, project_id: str) -> EngineeringKnowledgeSnapshot | None:
        memories = self.list_approved(project_id)
        nodes = tuple(
            EngineeringKnowledgeNode.create(
                node_id=f"memory:{memory.memory_id}",
                project_id=memory.project_id,
                entity_type=KnowledgeEntityType.DECISION,
                reference=memory.source_reference,
                attributes=(
                    memory.memory_type.value,
                    memory.fingerprint,
                    memory.approval_audit.candidate_fingerprint,
                ),
                confidence=KnowledgeConfidence.VERIFIED,
            )
            for memory in memories
        )
        return EngineeringKnowledgeSnapshot.create(
            project_id=project_id,
            nodes=nodes,
            relations=(),
        )


__all__ = [
    "EngineeringMemoryProjectionAdapter",
    "ApprovedEngineeringMemoryKnowledgeAdapter",
    "EngineeringMemorySnapshotSource",
    "MemoryKnowledgeAdapter",
    "MemoryProjectionAdapter",
]
