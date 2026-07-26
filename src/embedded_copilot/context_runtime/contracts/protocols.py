from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.context_runtime.contracts.models import (
    ContextReference,
    DatasheetContext,
    EngineeringContextRequest,
    EngineeringContextResponse,
    FileContext,
    VisionContext,
)


@runtime_checkable
class EngineeringContextPort(Protocol):
    async def compose(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse: ...


@runtime_checkable
class ContextReferenceResolver(Protocol):
    def resolve(
        self,
        request: EngineeringContextRequest,
    ) -> tuple[ContextReference, ...]: ...


@runtime_checkable
class FileContextSource(Protocol):
    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> FileContext: ...


@runtime_checkable
class DatasheetContextSource(Protocol):
    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> DatasheetContext: ...


@runtime_checkable
class VisionContextSource(Protocol):
    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> VisionContext: ...
