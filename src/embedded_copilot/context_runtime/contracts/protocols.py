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


class ContextReferenceResolver(Protocol):
    def resolve(
        self,
        request: EngineeringContextRequest,
    ) -> tuple[ContextReference, ...]: ...


class FileContextSource(Protocol):
    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> FileContext: ...


class DatasheetContextSource(Protocol):
    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> DatasheetContext: ...


class VisionContextSource(Protocol):
    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> VisionContext: ...
