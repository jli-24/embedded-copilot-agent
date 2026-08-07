from __future__ import annotations

import copy
from typing import Protocol, runtime_checkable

from .contracts import ApprovedEngineeringMemory, EngineeringMemoryQuery
from .exceptions import MemoryOperationConflict


@runtime_checkable
class ApprovedEngineeringMemoryStorePort(Protocol):
    def create_record(self, memory: ApprovedEngineeringMemory) -> ApprovedEngineeringMemory: ...

    def get_record(
        self, project_id: str, memory_id: str
    ) -> ApprovedEngineeringMemory | None: ...

    def query_records(
        self, request: EngineeringMemoryQuery
    ) -> tuple[ApprovedEngineeringMemory, ...]: ...

    def retrieve_verified(
        self, project_id: str
    ) -> tuple[ApprovedEngineeringMemory, ...]: ...

    def fingerprint_check(
        self, project_id: str, memory_id: str, fingerprint: str
    ) -> bool: ...

    # Compatibility facade for existing callers.
    def save(self, memory: ApprovedEngineeringMemory) -> ApprovedEngineeringMemory: ...

    def get(self, project_id: str, memory_id: str) -> ApprovedEngineeringMemory | None: ...

    def list(self, project_id: str) -> tuple[ApprovedEngineeringMemory, ...]: ...


class InMemoryApprovedEngineeringMemoryStore:
    __slots__ = ("_memories",)

    def __init__(self) -> None:
        self._memories: dict[tuple[str, str], ApprovedEngineeringMemory] = {}

    def create_record(self, memory: ApprovedEngineeringMemory) -> ApprovedEngineeringMemory:
        if type(memory) is not ApprovedEngineeringMemory:
            raise TypeError("approved memory must be a typed contract")
        checked = ApprovedEngineeringMemory.model_validate(copy.deepcopy(memory))
        key = (checked.project_id, checked.memory_id)
        existing = self._memories.get(key)
        if existing is not None:
            if existing.fingerprint != checked.fingerprint:
                raise MemoryOperationConflict()
            return ApprovedEngineeringMemory.model_validate(copy.deepcopy(existing))
        self._memories[key] = checked
        return ApprovedEngineeringMemory.model_validate(copy.deepcopy(checked))

    def save(self, memory: ApprovedEngineeringMemory) -> ApprovedEngineeringMemory:
        return self.create_record(memory)

    def get_record(
        self, project_id: str, memory_id: str
    ) -> ApprovedEngineeringMemory | None:
        value = self._memories.get((project_id, memory_id))
        return None if value is None else ApprovedEngineeringMemory.model_validate(copy.deepcopy(value))

    def get(self, project_id: str, memory_id: str) -> ApprovedEngineeringMemory | None:
        return self.get_record(project_id, memory_id)

    def retrieve_verified(
        self, project_id: str
    ) -> tuple[ApprovedEngineeringMemory, ...]:
        values = tuple(
            value
            for (stored_project, _), value in sorted(self._memories.items())
            if stored_project == project_id and value.status == "APPROVED"
        )
        return tuple(ApprovedEngineeringMemory.model_validate(copy.deepcopy(value)) for value in values)

    def list(self, project_id: str) -> tuple[ApprovedEngineeringMemory, ...]:
        return self.retrieve_verified(project_id)

    def query_records(
        self, request: EngineeringMemoryQuery
    ) -> tuple[ApprovedEngineeringMemory, ...]:
        checked = EngineeringMemoryQuery.model_validate(copy.deepcopy(request))
        values = self.retrieve_verified(checked.project_id)
        if checked.memory_type is None:
            return values
        return tuple(item for item in values if item.memory_type is checked.memory_type)

    def fingerprint_check(
        self, project_id: str, memory_id: str, fingerprint: str
    ) -> bool:
        value = self.get_record(project_id, memory_id)
        return value is not None and value.fingerprint == fingerprint


__all__ = (
    "ApprovedEngineeringMemoryStorePort",
    "InMemoryApprovedEngineeringMemoryStore",
)
