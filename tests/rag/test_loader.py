from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from embedded_copilot.rag.loader import DocumentLoadError, load_document


def test_markdown_loader_preserves_source_metadata(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    path = knowledge_dir / "spi.md"
    path.write_text("# SPI\n\nSPI uses SCLK and chip select.", encoding="utf-8")

    documents = load_document(path, source_root=tmp_path)

    assert len(documents) == 1
    assert documents[0].source == "knowledge/spi.md"
    assert documents[0].filename == "spi.md"
    assert documents[0].page is None
    assert documents[0].checksum


def test_pdf_loader_uses_one_based_page_numbers(tmp_path: Path) -> None:
    path = tmp_path / "manual.pdf"
    pdf = fitz.open()
    for text in ("ESP32 SPI controller", "FreeRTOS task scheduling"):
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()

    documents = load_document(path, source_root=tmp_path)

    assert [document.page for document in documents] == [1, 2]
    assert "ESP32 SPI controller" in documents[0].text
    assert all(document.source == "manual.pdf" for document in documents)


def test_loader_rejects_unsupported_document_type(tmp_path: Path) -> None:
    path = tmp_path / "manual.docx"
    path.write_text("unsupported", encoding="utf-8")

    with pytest.raises(DocumentLoadError, match="Unsupported"):
        load_document(path)
