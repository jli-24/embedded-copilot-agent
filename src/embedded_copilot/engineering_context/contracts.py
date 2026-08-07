from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import (
    ApprovedMemoryProjection,
    DatasheetMetadataProjection,
    EngineeringContextQuery,
    EngineeringContextSnapshot,
    VerifiedKnowledgeProjection,
)


@runtime_checkable
class ApprovedMemoryProjectionPort(Protocol):
    def list_approved(
        self, project_id: str
    ) -> tuple[ApprovedMemoryProjection, ...]: ...


@runtime_checkable
class EngineeringGraphProjectionPort(Protocol):
    def project(self, project_id: str) -> Any | None: ...


@runtime_checkable
class KnowledgeEvolutionProjectionPort(Protocol):
    def get_snapshot(
        self, project_id: str
    ) -> tuple[VerifiedKnowledgeProjection, ...]: ...


@runtime_checkable
class DatasheetMetadataProjectionPort(Protocol):
    def list_metadata(
        self, project_id: str, query: str
    ) -> tuple[DatasheetMetadataProjection, ...]: ...


@runtime_checkable
class EngineeringContextProviderPort(Protocol):
    def get_context(
        self, query: EngineeringContextQuery
    ) -> EngineeringContextSnapshot | None: ...


__all__ = (
    "ApprovedMemoryProjectionPort",
    "DatasheetMetadataProjectionPort",
    "EngineeringContextProviderPort",
    "EngineeringGraphProjectionPort",
    "KnowledgeEvolutionProjectionPort",
)
