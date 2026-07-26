from __future__ import annotations

import re
from pathlib import PurePath

from pydantic import ValidationError

from embedded_copilot.context_runtime.contracts import (
    ComponentContextCandidate,
    ContextDocumentType,
    ContextImageType,
    ContextReference,
    ContextReferenceKind,
    DatasheetContext,
    EngineeringContextRequest,
    FileContext,
    InterfaceContextCandidate,
    SectionContextCandidate,
    VisionContext,
    EngineeringContextResponse,
)
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextConflict,
    EngineeringContextError,
    EngineeringContextReferenceNotFound,
    EngineeringContextRejected,
    EngineeringContextTimeout,
    EngineeringContextUnavailable,
)
from embedded_copilot.datasheet_runtime import (
    DatasheetAnalysisTimeout,
    DatasheetDocumentRejected,
    DatasheetIntelligencePort,
    DatasheetRequest,
    DatasheetRuntimeUnavailable,
)
from embedded_copilot.file_runtime import (
    FileAnalysisTimeout,
    FileIntelligencePort,
    FileReferenceConflict,
    FileReferenceNotFound,
    FileReferenceRequest,
    FileRuntimeUnavailable,
    FileType,
)
from embedded_copilot.multimodal.context import (
    AttachmentBindingNotFound,
    AttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import MultimodalInputType
from embedded_copilot.vision_runtime import VisionPort

_SOURCE_SUFFIXES = frozenset({".c", ".cpp", ".h", ".py"})
_TEXT_SUFFIXES = frozenset({".md", ".txt", ".log", ".json"})
_PDF_SUMMARY = re.compile(r"^(PDF|DATASHEET) file structure: (\d+) pages\.$")
_TEXT_SUMMARY = re.compile(
    r"^(TEXT|SOURCE_CODE) file structure: (\d+) lines, (\d+) characters\.$"
)


class CopilotContextReferenceResolver:
    __slots__ = ("_repository",)

    def __init__(self, repository: AttachmentBindingRepository) -> None:
        self._repository = repository

    def resolve(
        self,
        request: EngineeringContextRequest,
    ) -> tuple[ContextReference, ...]:
        references: list[ContextReference] = []
        for reference_id in request.reference_ids:
            try:
                binding = self._repository.get(request.session_id, reference_id)
            except AttachmentBindingNotFound:
                raise EngineeringContextReferenceNotFound() from None
            except Exception:
                raise EngineeringContextConflict() from None
            if binding.input.type is MultimodalInputType.IMAGE:
                references.append(
                    ContextReference(
                        reference_id=reference_id,
                        kind=ContextReferenceKind.VISION,
                        image_type=ContextImageType.UNKNOWN,
                    )
                )
                continue
            if binding.input.type is not MultimodalInputType.FILE:
                raise EngineeringContextRejected()
            document_type = _document_type(binding.basename)
            references.append(
                ContextReference(
                    reference_id=reference_id,
                    kind=(
                        ContextReferenceKind.DATASHEET
                        if document_type is ContextDocumentType.PDF
                        else ContextReferenceKind.FILE
                    ),
                    document_type=document_type,
                )
            )
        return tuple(references)


class UnavailableEngineeringContextPort:
    async def compose(
        self,
        request: EngineeringContextRequest,
    ) -> EngineeringContextResponse:
        raise EngineeringContextUnavailable()


class CopilotFileContextSource:
    __slots__ = ("_port",)

    def __init__(self, port: FileIntelligencePort) -> None:
        if not isinstance(port, FileIntelligencePort):
            raise EngineeringContextUnavailable()
        self._port = port

    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> FileContext:
        try:
            response = await self._port.analyze(
                FileReferenceRequest(
                    session_id=request.session_id,
                    file_id=reference.reference_id,
                    file_type=FileType.UNKNOWN,
                    instruction_summary=request.task_intent,
                )
            )
            return _file_context(reference.reference_id, response.summary)
        except Exception as error:
            _raise_context_error(error)


class CopilotDatasheetContextSource:
    __slots__ = ("_port",)

    def __init__(self, port: DatasheetIntelligencePort) -> None:
        if not isinstance(port, DatasheetIntelligencePort):
            raise EngineeringContextUnavailable()
        self._port = port

    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> DatasheetContext:
        try:
            response = await self._port.analyze(
                DatasheetRequest(
                    session_id=request.session_id,
                    file_id=reference.reference_id,
                    instruction_summary=request.task_intent,
                )
            )
            summary = response.summary
            component = (
                ComponentContextCandidate(
                    family=summary.component_candidate.family,
                    model=summary.component_candidate.model,
                )
                if summary.component_candidate is not None
                else None
            )
            return DatasheetContext(
                file_id=summary.file_id,
                component_candidate=component,
                interfaces=tuple(
                    InterfaceContextCandidate(name=item.name)
                    for item in summary.interface_candidates
                ),
                sections=tuple(
                    SectionContextCandidate(name=item.name)
                    for item in summary.section_candidates
                ),
            )
        except Exception as error:
            _raise_context_error(error)


class CopilotVisionContextSource:
    __slots__ = ("_port",)

    def __init__(self, port: VisionPort) -> None:
        if not isinstance(port, VisionPort):
            raise EngineeringContextUnavailable()
        self._port = port

    async def summarize(
        self,
        request: EngineeringContextRequest,
        reference: ContextReference,
    ) -> VisionContext:
        if reference.image_type is None:
            raise EngineeringContextConflict()
        # Vision inference output is deliberately outside the fusion contract.
        return VisionContext(
            reference_id=reference.reference_id,
            image_type=reference.image_type,
        )


def _document_type(basename: str) -> ContextDocumentType:
    suffix = PurePath(basename).suffix.casefold()
    if suffix in _SOURCE_SUFFIXES:
        return ContextDocumentType.SOURCE_CODE
    if suffix in _TEXT_SUFFIXES:
        return ContextDocumentType.TEXT
    if suffix == ".pdf":
        return ContextDocumentType.PDF
    raise EngineeringContextRejected()


def _file_context(file_id: str, summary: str) -> FileContext:
    pdf_match = _PDF_SUMMARY.fullmatch(summary)
    if pdf_match is not None:
        return FileContext(
            file_id=file_id,
            document_type=ContextDocumentType(pdf_match.group(1)),
            page_count=int(pdf_match.group(2)),
        )
    text_match = _TEXT_SUMMARY.fullmatch(summary)
    if text_match is not None:
        return FileContext(
            file_id=file_id,
            document_type=ContextDocumentType(text_match.group(1)),
            line_count=int(text_match.group(2)),
            character_count=int(text_match.group(3)),
        )
    raise EngineeringContextRejected()


def _raise_context_error(error: Exception) -> None:
    if isinstance(error, EngineeringContextError):
        raise error
    if isinstance(error, (FileReferenceNotFound, AttachmentBindingNotFound)):
        raise EngineeringContextReferenceNotFound() from None
    if isinstance(error, FileReferenceConflict):
        raise EngineeringContextConflict() from None
    if isinstance(error, (DatasheetDocumentRejected, ValidationError)):
        raise EngineeringContextRejected() from None
    if isinstance(
        error,
        (FileRuntimeUnavailable, DatasheetRuntimeUnavailable),
    ):
        raise EngineeringContextUnavailable() from None
    if isinstance(error, (FileAnalysisTimeout, DatasheetAnalysisTimeout)):
        raise EngineeringContextTimeout() from None
    raise EngineeringContextUnavailable() from None
