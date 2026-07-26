from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable

from embedded_copilot.file_runtime.contracts.models import (
    DocumentSummary,
    FileIntelligenceResponse,
    FileReference,
    FileReferenceRequest,
)


@runtime_checkable
class FileIntelligencePort(Protocol):
    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse: ...


@runtime_checkable
class FileReferenceCatalog(Protocol):
    def resolve(self, session_id: str, file_id: str) -> FileReference | None: ...


class Extractor(Protocol):
    def extract(
        self,
        stream: BinaryIO,
        *,
        reference: FileReference,
    ) -> DocumentSummary: ...
