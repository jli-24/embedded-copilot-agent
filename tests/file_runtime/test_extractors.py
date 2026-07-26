from __future__ import annotations

import io
from pathlib import Path

import fitz
import pytest

from embedded_copilot.file_runtime import (
    DocumentSummary,
    FileReference,
    FileRuntimeUnavailable,
    FileType,
)
from embedded_copilot.file_runtime.extractors.pdf import PdfExtractor
from embedded_copilot.file_runtime.extractors.text import TextExtractor


def _reference(
    basename: str,
    document_type: FileType,
    *,
    size_bytes: int,
) -> FileReference:
    return FileReference(
        session_id="session:1",
        file_id="file:1",
        basename=basename,
        document_type=document_type,
        size_bytes=size_bytes,
        relative_path=Path(basename),
    )


def test_text_extractor_returns_only_structural_document_summary() -> None:
    payload = b"def private_function():\n    return 'secret'\n"
    reference = _reference(
        "main.py",
        FileType.SOURCE_CODE,
        size_bytes=len(payload),
    )

    summary = TextExtractor(chunk_size=7).extract(
        io.BytesIO(payload),
        reference=reference,
    )

    assert summary == DocumentSummary(
        file_id="file:1",
        document_type=FileType.SOURCE_CODE,
        line_count=2,
        character_count=44,
    )
    serialized = summary.model_dump(mode="json")
    assert "private_function" not in str(serialized)
    assert "secret" not in str(serialized)
    assert set(serialized) == {
        "file_id",
        "document_type",
        "page_count",
        "line_count",
        "character_count",
        "candidate",
    }


def test_text_extractor_rejects_invalid_utf8_without_echoing_input() -> None:
    payload = b"\xffprivate"
    reference = _reference("debug.log", FileType.TEXT, size_bytes=len(payload))

    with pytest.raises(FileRuntimeUnavailable) as raised:
        TextExtractor().extract(io.BytesIO(payload), reference=reference)

    assert str(raised.value) == "file_unavailable"
    assert "private" not in str(raised.value)


def test_pdf_extractor_returns_page_count_without_text_or_metadata() -> None:
    document = fitz.open()
    document.set_metadata(
        {
            "title": r"C:\private\datasheet.pdf",
            "author": "Confidential author",
        }
    )
    page = document.new_page()
    page.insert_text((72, 72), "SECRET DATASHEET PARAMETER 3.3V")
    document.new_page()
    payload = document.tobytes()
    document.close()
    reference = _reference(
        "datasheet.pdf",
        FileType.DATASHEET,
        size_bytes=len(payload),
    )

    summary = PdfExtractor(max_size_bytes=len(payload) + 1).extract(
        io.BytesIO(payload),
        reference=reference,
    )

    assert summary == DocumentSummary(
        file_id="file:1",
        document_type=FileType.DATASHEET,
        page_count=2,
    )
    serialized = str(summary.model_dump(mode="json"))
    assert "SECRET" not in serialized
    assert "Confidential" not in serialized
    assert "private" not in serialized
    assert summary.candidate == ()


@pytest.mark.parametrize(
    ("payload", "max_size_bytes"),
    (
        (b"not a PDF", 1024),
        (b"%PDF-" + b"x" * 32, 8),
    ),
)
def test_pdf_extractor_rejects_malformed_or_oversized_payload(
    payload: bytes,
    max_size_bytes: int,
) -> None:
    reference = _reference("document.pdf", FileType.PDF, size_bytes=len(payload))

    with pytest.raises(FileRuntimeUnavailable):
        PdfExtractor(max_size_bytes=max_size_bytes).extract(
            io.BytesIO(payload),
            reference=reference,
        )
