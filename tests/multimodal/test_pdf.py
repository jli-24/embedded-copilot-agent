from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from embedded_copilot.multimodal.models import MultimodalProcessingError
from embedded_copilot.multimodal.pdf import PDFAnalyzer


def _write_pdf(path: Path, contents: list[str | None]) -> None:
    pdf = fitz.open()
    for content in contents:
        page = pdf.new_page()
        if content is not None:
            page.insert_text((72, 72), content)
    pdf.save(path)
    pdf.close()


def test_pdf_analyzer_returns_one_based_page_content(tmp_path: Path) -> None:
    path = tmp_path / "manual.pdf"
    _write_pdf(path, ["ESP32 SPI controller", "FreeRTOS scheduler"])

    pages = PDFAnalyzer.analyze(path)

    assert [page["page"] for page in pages] == [1, 2]
    assert "ESP32 SPI controller" in pages[0]["content"]
    assert "FreeRTOS scheduler" in pages[1]["content"]


def test_pdf_analyzer_preserves_blank_pages(tmp_path: Path) -> None:
    path = tmp_path / "blank-page.pdf"
    _write_pdf(path, [None])

    assert PDFAnalyzer.analyze(path) == [{"page": 1, "content": ""}]


@pytest.mark.parametrize("kind", ["missing", "directory", "corrupt"])
def test_pdf_analyzer_maps_invalid_inputs_to_multimodal_error(
    tmp_path: Path,
    kind: str,
) -> None:
    path = tmp_path / "input.pdf"
    if kind == "directory":
        path.mkdir()
    elif kind == "corrupt":
        path.write_bytes(b"not a PDF")

    with pytest.raises(MultimodalProcessingError):
        PDFAnalyzer.analyze(path)
