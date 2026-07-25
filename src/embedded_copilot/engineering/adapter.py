from __future__ import annotations

import copy
from typing import Protocol

from embedded_copilot.agents.types import AgentResult, AgentTask
from embedded_copilot.datasheet.extensions.real_pdf.parser import (
    RealPDFBackendUnavailable,
    RealPDFParseError,
)
from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.engineering.models import (
    RealEngineeringEnvelope,
    RealEngineeringError,
)
from embedded_copilot.engineering.resolver import (
    EngineeringResolutionError,
    TrustedEngineeringResolver,
)
from embedded_copilot.firmware.review.analyzer import (
    FirmwareReviewAnalyzer,
    FirmwareReviewError,
)
from embedded_copilot.firmware.review.models import FirmwareSource
from embedded_copilot.input.adapters.supervisor import _consume_input_context
from embedded_copilot.input.models import AttachmentType, UnifiedInputContext


_ENVELOPE_KEY = "_real_engineering_input"


class _PDFParser(Protocol):
    def parse(self, raw_pdf: bytes, *, source_id: str) -> UnifiedDatasheetModel: ...


class _FirmwareAnalyzer(Protocol):
    def analyze(self, sources: tuple[FirmwareSource, ...]): ...


class _SupervisorDelegate(Protocol):
    def run(self, task: AgentTask) -> AgentResult: ...


class RealEngineeringInputAdapter:
    def __init__(
        self,
        *,
        resolver: TrustedEngineeringResolver,
        pdf_parser: _PDFParser | None,
        firmware_analyzer: _FirmwareAnalyzer | None = None,
    ) -> None:
        self._resolver = resolver
        self._pdf_parser = pdf_parser
        self._firmware_analyzer = firmware_analyzer or FirmwareReviewAnalyzer()

    def adapt(self, context: UnifiedInputContext) -> RealEngineeringEnvelope:
        datasheet = None
        firmware_review = None
        errors: list[RealEngineeringError] = []
        resolved = []
        for domain, media_type in (
            ("datasheet", AttachmentType.DOCUMENT),
            ("firmware", AttachmentType.SOURCE_CODE),
        ):
            attachments = tuple(
                item for item in context.attachments if item.media_type is media_type
            )
            if not attachments:
                continue
            try:
                domain_context = UnifiedInputContext(
                    text=context.text,
                    attachments=attachments,
                    metadata=context.metadata,
                )
                resolved.extend(self._resolver.resolve(domain_context))
            except EngineeringResolutionError:
                errors.append(
                    RealEngineeringError(
                        domain=domain,  # type: ignore[arg-type]
                        code="source_resolution_failed",
                        message=f"{domain.title()} source resolution failed",
                        source_ids=tuple(
                            f"attachment:{item.id}" for item in attachments
                        ),
                    )
                )
        references = tuple(item.reference for item in resolved)
        pdf_sources = tuple(
            item for item in resolved if item.media_type is AttachmentType.DOCUMENT
        )
        firmware_sources = tuple(
            item for item in resolved if item.media_type is AttachmentType.SOURCE_CODE
        )
        if pdf_sources:
            try:
                if self._pdf_parser is None:
                    raise RealPDFBackendUnavailable(
                        "Real PDF Datasheet backend is unavailable"
                    )
                item = pdf_sources[0]
                datasheet = self._pdf_parser.parse(
                    item.data,
                    source_id=item.reference.source_id,
                )
            except RealPDFBackendUnavailable:
                errors.append(
                    RealEngineeringError(
                        domain="datasheet",
                        code="backend_unavailable",
                        message="Datasheet text-layer backend is unavailable",
                        source_ids=(pdf_sources[0].reference.source_id,),
                    )
                )
            except RealPDFParseError:
                errors.append(
                    RealEngineeringError(
                        domain="datasheet",
                        code="parse_failed",
                        message="Datasheet text-layer parsing failed",
                        source_ids=(pdf_sources[0].reference.source_id,),
                    )
                )
        if firmware_sources:
            try:
                sources = tuple(
                    FirmwareSource(
                        filename=item.reference.filename,
                        source_id=item.reference.source_id,
                        language=_language(item.reference.filename),
                        text=item.data.decode("utf-8-sig", errors="strict"),
                    )
                    for item in firmware_sources
                )
                firmware_review = self._firmware_analyzer.analyze(sources)
            except (FirmwareReviewError, UnicodeDecodeError, ValueError):
                errors.append(
                    RealEngineeringError(
                        domain="firmware",
                        code="analysis_failed",
                        message="Firmware static analysis failed",
                        source_ids=tuple(
                            item.reference.source_id for item in firmware_sources
                        ),
                    )
                )
        return RealEngineeringEnvelope(
            datasheet=datasheet,
            firmware_review=firmware_review,
            references=references,
            errors=tuple(errors),
        )


class EngineeringSupervisorAdapter:
    """Transparent envelope injector; the delegate owns the entire workflow."""

    def __init__(
        self,
        *,
        delegate: _SupervisorDelegate,
        input_adapter: RealEngineeringInputAdapter,
    ) -> None:
        self._delegate = delegate
        self._input_adapter = input_adapter

    def run(self, task: AgentTask) -> AgentResult:
        if not isinstance(task, AgentTask):
            return self._delegate.run(task)
        _, context = _consume_input_context(copy.deepcopy(task.metadata))
        task_copy = task.model_copy(deep=True)
        if context is None or not _has_engineering_attachments(context):
            return self._delegate.run(task_copy)
        envelope = self._input_adapter.adapt(context)
        metadata = copy.deepcopy(task_copy.metadata)
        metadata[_ENVELOPE_KEY] = envelope
        enriched = task_copy.model_copy(update={"metadata": metadata}, deep=True)
        return self._delegate.run(enriched)


def _has_engineering_attachments(context: UnifiedInputContext) -> bool:
    return any(
        TrustedEngineeringResolver._is_datasheet(item)
        or TrustedEngineeringResolver._is_firmware(item)
        for item in context.attachments
    )


def _language(filename: str) -> str:
    lowered = filename.casefold()
    if lowered.endswith(".h"):
        return "C Header"
    if lowered.endswith(".hpp"):
        return "C++ Header"
    if lowered.endswith((".cc", ".cpp", ".cxx")):
        return "C++"
    return "C"
