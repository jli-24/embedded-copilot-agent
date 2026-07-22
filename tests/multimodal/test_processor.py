from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from PIL import Image

from embedded_copilot.multimodal.models import (
    FileDocument,
    FileType,
    MultimodalProcessingError,
)
from embedded_copilot.multimodal.processor import MultimodalProcessor


def _write_pdf(path: Path, content: str) -> None:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), content)
    pdf.save(path)
    pdf.close()


def test_processor_returns_pdf_document(tmp_path: Path) -> None:
    path = tmp_path / "manual.pdf"
    _write_pdf(path, "STM32 reference manual")

    document = MultimodalProcessor.process(path)

    assert isinstance(document, FileDocument)
    assert document.filename == "manual.pdf"
    assert document.file_type is FileType.PDF
    assert document.path == str(path)
    assert document.metadata["page_count"] == 1
    assert document.metadata["pages"] == [
        {"page": 1, "content": "STM32 reference manual"}
    ]


def test_processor_returns_image_document(tmp_path: Path) -> None:
    path = tmp_path / "board.webp"
    Image.new("RGB", (12, 7), color="green").save(path)

    document = MultimodalProcessor.process(path)

    assert document.file_type is FileType.IMAGE
    assert document.metadata == {
        "width": 12,
        "height": 7,
        "format": "WEBP",
        "path": str(path),
        "analysis_mode": "offline_metadata",
    }


@pytest.mark.parametrize(
    ("filename", "expected_type"),
    [
        ("main.c", FileType.CODE),
        ("driver.h", FileType.CODE),
        ("task.cpp", FileType.CODE),
        ("script.py", FileType.CODE),
        ("module.rs", FileType.CODE),
        ("README.md", FileType.TEXT),
        ("notes.txt", FileType.TEXT),
    ],
)
def test_processor_preserves_utf8_code_and_text(
    tmp_path: Path,
    filename: str,
    expected_type: FileType,
) -> None:
    path = tmp_path / filename
    content = "ESP32 外设配置\nsecond line\n"
    path.write_text(content, encoding="utf-8")

    document = MultimodalProcessor.process(path)

    assert document.file_type is expected_type
    assert document.metadata == {"content": content, "encoding": "utf-8"}


def test_processor_returns_unknown_document_for_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "capture.bin"
    path.write_bytes(b"\x00\x01")

    document = MultimodalProcessor.process(path)

    assert document.file_type is FileType.UNKNOWN
    assert document.metadata == {}


def test_processor_maps_invalid_utf8_to_multimodal_error(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(MultimodalProcessingError):
        MultimodalProcessor.process(path)


def test_processor_preserves_analyzer_errors(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(MultimodalProcessingError):
        MultimodalProcessor.process(path)


def test_processor_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(MultimodalProcessingError):
        MultimodalProcessor.process(tmp_path / "missing.txt")
