from __future__ import annotations

import asyncio
from pathlib import Path
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from embedded_copilot.file_runtime import (
    DocumentSummary,
    FileIntelligencePort,
    FileIntelligenceResponse,
    FileReference,
    FileReferenceCatalog,
    FileReferenceRequest,
    FileRuntime,
    FileType,
)


class _Port:
    async def analyze(
        self,
        request: FileReferenceRequest,
    ) -> FileIntelligenceResponse:
        return FileIntelligenceResponse(
            summary="TEXT file structure: 2 lines, 12 characters."
        )


def test_file_reference_request_rejects_infrastructure_fields() -> None:
    payload = {
        "session_id": "session:1",
        "file_id": "file:1",
        "file_type": FileType.UNKNOWN,
        "instruction_summary": "Inspect the referenced file structure.",
    }

    request = FileReferenceRequest(**payload)

    assert tuple(FileReferenceRequest.model_fields) == (
        "session_id",
        "file_id",
        "file_type",
        "instruction_summary",
    )
    for forbidden in (
        "filename",
        "path",
        "absolute_path",
        "mime",
        "size",
        "bytes",
        "content",
        "file_url",
        "model",
        "provider",
    ):
        with pytest.raises(ValidationError):
            FileReferenceRequest(**payload, **{forbidden: "forbidden"})


def test_document_summary_is_frozen_extra_forbid_and_candidate_empty() -> None:
    summary = DocumentSummary(
        file_id="file:1",
        document_type=FileType.SOURCE_CODE,
        line_count=2,
        character_count=12,
    )

    assert summary.candidate == ()
    assert tuple(DocumentSummary.model_fields) == (
        "file_id",
        "document_type",
        "page_count",
        "line_count",
        "character_count",
        "candidate",
    )
    with pytest.raises(ValidationError):
        summary.line_count = 3
    with pytest.raises(ValidationError):
        DocumentSummary(
            file_id="file:1",
            document_type=FileType.SOURCE_CODE,
            line_count=2,
            character_count=12,
            keywords=("unsafe",),
        )
    with pytest.raises(ValidationError):
        DocumentSummary(
            file_id="file:1",
            document_type=FileType.PDF,
            page_count=1,
            candidate=("chip_candidate",),
        )


def test_file_reference_string_and_serialization_hide_relative_path() -> None:
    reference = FileReference(
        session_id="session:1",
        file_id="file:1",
        basename="main.c",
        document_type=FileType.SOURCE_CODE,
        size_bytes=42,
        relative_path=Path("private/main.c"),
    )

    assert reference.relative_path == Path("private/main.c")
    assert "private" not in str(reference)
    assert "main.c" not in str(reference)
    assert "private" not in repr(reference)
    assert "main.c" not in repr(reference)
    assert "relative_path" not in reference.model_dump(mode="json")


def test_ports_are_read_only_and_facade_hides_runtime_internals() -> None:
    assert {
        name
        for name, value in FileReferenceCatalog.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"resolve"}
    assert {
        name
        for name, value in FileIntelligencePort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"analyze"}
    assert get_type_hints(FileRuntime.file_port)["return"] is FileIntelligencePort

    runtime = FileRuntime._compose(_Port())
    response = asyncio.run(
        runtime.file_port().analyze(
            FileReferenceRequest(
                session_id="session:1",
                file_id="file:1",
                file_type=FileType.UNKNOWN,
                instruction_summary="Inspect the referenced file structure.",
            )
        )
    )

    assert response == FileIntelligenceResponse(
        summary="TEXT file structure: 2 lines, 12 characters."
    )
    for forbidden in (
        "reader",
        "extractor",
        "resolver",
        "catalog",
        "root",
        "settings",
        "configuration",
        "write",
        "patch",
        "execute",
    ):
        assert not hasattr(runtime, forbidden)
        assert not hasattr(runtime.file_port(), forbidden)


def test_file_intelligence_response_accepts_only_structural_summary() -> None:
    assert FileIntelligenceResponse(
        summary="PDF file structure: 12 pages."
    ).model_dump(mode="json") == {
        "output_type": "reasoning_suggestion",
        "summary": "PDF file structure: 12 pages.",
        "review_required": True,
    }

    for unsafe in (
        "int main(void) { return 0; }",
        "C:\\workspace\\main.c",
        "/workspace/main.c",
        "ESP32-S3 GPIO 4 supports 20 mA.",
    ):
        with pytest.raises(ValidationError):
            FileIntelligenceResponse(summary=unsafe)
