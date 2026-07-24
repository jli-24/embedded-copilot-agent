from __future__ import annotations

import inspect
from pathlib import Path

import fitz
import pytest

from embedded_copilot.datasheet.exceptions import DatasheetParseError
from embedded_copilot.datasheet.parser import (
    PDFDatasheetParser,
    RootedDatasheetSourceResolver,
)
from embedded_copilot.input import InputLoader

from tests.datasheet.parser.fixtures import STM32_PDF_TEXT


def _write_pdf(path: Path, pages: list[str | None]) -> None:
    pdf = fitz.open()
    for content in pages:
        page = pdf.new_page()
        if content is not None:
            page.insert_textbox(
                fitz.Rect(36, 36, 560, 800),
                content,
                fontsize=10,
            )
    pdf.save(path)
    pdf.close()


def _parse(
    root: Path,
    *,
    max_pages: int = 512,
    max_text_chars: int = 2_000_000,
):
    attachment = InputLoader(root).load(
        "stm32.pdf",
        attachment_id="datasheet-pdf",
    )
    parser = PDFDatasheetParser(
        RootedDatasheetSourceResolver(
            root,
            {"datasheet-pdf": "stm32.pdf"},
        ),
        max_pages=max_pages,
        max_text_chars=max_text_chars,
    )
    return parser.parse(attachment)


def test_pdf_parser_extracts_bounded_text_without_table_guessing(
    tmp_path: Path,
) -> None:
    _write_pdf(tmp_path / "stm32.pdf", [STM32_PDF_TEXT])

    model = _parse(tmp_path)

    assert model.component.manufacturer == "STMicroelectronics"
    assert model.component.part_number == "STM32F407VG"
    assert [pin.number for pin in model.pins] == ["42", "43"]
    assert model.interfaces[0].pins == ("42", "43")
    assert model.electrical_specs[1].max_value == pytest.approx(0.08)
    assert model.metadata == {"format": "pdf", "record_count": 5}


@pytest.mark.parametrize(
    ("pages", "max_pages", "max_text_chars"),
    [
        ([None], 512, 2_000_000),
        ([STM32_PDF_TEXT, "second"], 1, 2_000_000),
        ([STM32_PDF_TEXT], 512, 32),
        (
            [
                "Manufacturer: STMicroelectronics\n"
                "Part Number: STM32F407VG\n"
                "Category: MCU\n"
                "Package: LQFP-100\n"
                "Description: Arm MCU\n"
                "Pin Number Pin Name Type Description\n"
                "42 PA9 alternate USART transmit"
            ],
            512,
            2_000_000,
        ),
    ],
)
def test_pdf_parser_safely_rejects_textless_limits_and_complex_tables(
    tmp_path: Path,
    pages: list[str | None],
    max_pages: int,
    max_text_chars: int,
) -> None:
    _write_pdf(tmp_path / "stm32.pdf", pages)

    with pytest.raises(DatasheetParseError) as captured:
        _parse(
            tmp_path,
            max_pages=max_pages,
            max_text_chars=max_text_chars,
        )

    assert str(tmp_path) not in str(captured.value)
    assert "STMicroelectronics" not in str(captured.value)


def test_pdf_parser_has_no_multimodal_rag_ocr_or_llm_fallback() -> None:
    source = inspect.getsource(PDFDatasheetParser).casefold()

    assert "multimodal" not in source
    assert "rag" not in source
    assert "ocr" not in source
    assert "llm" not in source


def test_pdf_parser_maps_unexpected_library_failures_to_safe_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_pdf(tmp_path / "stm32.pdf", [STM32_PDF_TEXT])

    def fail_open(*args, **kwargs):
        raise KeyError("C:/private/library-state")

    monkeypatch.setattr("embedded_copilot.datasheet.parser.pdf.fitz.open", fail_open)

    with pytest.raises(DatasheetParseError) as captured:
        _parse(tmp_path)

    assert str(captured.value) == "PDF Datasheet parsing failed"
