from __future__ import annotations

import asyncio

from embedded_copilot.file_runtime.contracts import (
    DocumentSummary,
    Extractor,
    FileIntelligencePort,
    FileIntelligenceResponse,
    FileReference,
    FileReferenceCatalog,
    FileReferenceRequest,
    FileType,
)
from embedded_copilot.file_runtime.contracts.models import format_document_summary
from embedded_copilot.file_runtime.exceptions import (
    FileRuntimeError,
    FileRuntimeUnavailable,
)
from embedded_copilot.file_runtime.extractors.pdf import PdfExtractor
from embedded_copilot.file_runtime.extractors.text import TextExtractor
from embedded_copilot.file_runtime.facade import FileRuntime
from embedded_copilot.file_runtime.reader.resolver import RootedFileResolver
from embedded_copilot.file_runtime.reader.stream import SecureFileReader
from embedded_copilot.file_runtime.security.policy import (
    FileSettingsSource,
    load_file_security_policy,
)


class _UnavailableFilePort:
    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse:
        raise FileRuntimeUnavailable()


class _StructuralExtractor:
    __slots__ = ("_pdf", "_text")

    def __init__(self, *, max_size_bytes: int) -> None:
        self._text = TextExtractor()
        self._pdf = PdfExtractor(max_size_bytes=max_size_bytes)

    def extract(
        self,
        stream,
        *,
        reference: FileReference,
    ) -> DocumentSummary:
        extractor: Extractor
        if reference.document_type in {FileType.PDF, FileType.DATASHEET}:
            extractor = self._pdf
        elif reference.document_type in {
            FileType.TEXT,
            FileType.SOURCE_CODE,
        }:
            extractor = self._text
        else:
            raise FileRuntimeUnavailable()
        return extractor.extract(stream, reference=reference)


class _StructuralFilePort:
    __slots__ = ("_extractor", "_reader")

    def __init__(
        self,
        reader: SecureFileReader,
        extractor: Extractor,
    ) -> None:
        self._reader = reader
        self._extractor = extractor

    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse:
        try:
            summary = await asyncio.to_thread(
                self._reader.extract,
                request,
                self._extractor,
            )
            return FileIntelligenceResponse(summary=format_document_summary(summary))
        except FileRuntimeError:
            raise
        except Exception:
            raise FileRuntimeUnavailable() from None


def create_file_runtime(
    settings: FileSettingsSource,
    catalog: FileReferenceCatalog,
) -> FileRuntime:
    policy = load_file_security_policy(settings)
    port: FileIntelligencePort
    if policy.workspace_root is None:
        port = _UnavailableFilePort()
    else:
        resolver = RootedFileResolver(policy.workspace_root, catalog)
        reader = SecureFileReader(
            resolver,
            max_size_bytes=policy.max_size_bytes,
        )
        port = _StructuralFilePort(
            reader,
            _StructuralExtractor(max_size_bytes=policy.max_size_bytes),
        )
    return FileRuntime._compose(port)
