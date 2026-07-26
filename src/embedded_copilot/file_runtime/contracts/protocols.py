from __future__ import annotations

from typing import BinaryIO, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from embedded_copilot.file_runtime.contracts.models import (
    DocumentSummary,
    FileIntelligenceResponse,
    FileReference,
    FileReferenceRequest,
)

ExtractionResultT = TypeVar("ExtractionResultT", bound=BaseModel)


@runtime_checkable
class FileIntelligencePort(Protocol):
    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse: ...


@runtime_checkable
class FileReferenceCatalog(Protocol):
    def resolve(self, session_id: str, file_id: str) -> FileReference | None: ...


class ReadOnlyExtractor(Protocol[ExtractionResultT]):
    def extract(
        self,
        stream: BinaryIO,
        *,
        reference: FileReference,
    ) -> ExtractionResultT: ...


class Extractor(ReadOnlyExtractor[DocumentSummary], Protocol):
    """A structural extractor retained for File Intelligence compatibility."""


@runtime_checkable
class FileExtractionPort(Protocol):
    async def extract(
        self,
        request: FileReferenceRequest,
        extractor: ReadOnlyExtractor[ExtractionResultT],
        *,
        result_type: type[ExtractionResultT],
    ) -> ExtractionResultT: ...
