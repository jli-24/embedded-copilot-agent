from __future__ import annotations

import json
from pathlib import Path

import fitz

from embedded_copilot.rag.loader import load_document


def _write_pdf(path: Path) -> None:
    pdf = fitz.open()
    for content in ("ESP32-S3 SPI overview", "ESP32-S3 SPI DMA"):
        page = pdf.new_page()
        page.insert_text((72, 72), content)
    pdf.save(path)
    pdf.close()


def test_pdf_loader_combines_sidecar_with_one_based_page_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "esp32_s3_datasheet.pdf"
    _write_pdf(path)
    (tmp_path / "esp32_s3_datasheet.pdf.metadata.json").write_text(
        json.dumps(
            {
                "chip": "ESP32-S3",
                "manufacturer": "Espressif",
                "category": "MCU",
                "chapter": "SPI",
                "page": 99,
                "document_type": "datasheet",
            }
        ),
        encoding="utf-8",
    )

    documents = load_document(path, source_root=tmp_path)

    assert [document.page for document in documents] == [1, 2]
    assert [document.metadata.page for document in documents] == [1, 2]
    assert all(document.metadata.chip == "ESP32-S3" for document in documents)
    assert all(document.metadata.chapter == "SPI" for document in documents)
    assert all(
        document.metadata.document_type == "datasheet" for document in documents
    )
