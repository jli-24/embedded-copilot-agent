from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    EngineeringContextQuery,
    EngineeringContextSnapshot,
    EngineeringGraphSnapshot,
)


@runtime_checkable
class ApprovedEngineeringMemoryProjectionPort(Protocol):
    def list_approved(
        self, project_id: str
    ) -> tuple[object, ...]: ...


@runtime_checkable
class EngineeringKnowledgeProjectionPort(Protocol):
    def project(self, project_id: str) -> EngineeringGraphSnapshot | None: ...


@runtime_checkable
class EngineeringContextProviderPort(Protocol):
    def get_context(
        self, query: EngineeringContextQuery
    ) -> EngineeringContextSnapshot | None: ...


__all__ = (
    "ApprovedEngineeringMemoryProjectionPort",
    "EngineeringContextProviderPort",
    "EngineeringKnowledgeProjectionPort",
)
