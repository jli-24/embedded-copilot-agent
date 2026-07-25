from __future__ import annotations

import importlib

import fitz
import pytest

from embedded_copilot.datasheet.extensions.real_pdf.parser import (
    RealPDFBackendUnavailable,
    RealPDFDatasheetParser,
    RealPDFParseError,
)


REAL_ESP32_S3_TEXT = """ESP32-S3 Series Datasheet
Espressif Systems
Part Number: ESP32-S3
Package: QFN-56
Family: ESP32-S3
CPU: Xtensa dual-core 32-bit LX7
Operating voltage: 3.0 V to 3.6 V
Active current: 20 mA to 40 mA
Operating temperature: -40 C to 85 C
Memory: 384 KB ROM, 512 KB SRAM, external Flash support
Interfaces: UART, SPI, I2C, USB, DVP camera interface
Pin No. Pin Name Function
12 GPIO8 Embedded Flash
13 GPIO9 DVP camera data 0
"""


def _pdf_bytes(pages: list[str | None]) -> bytes:
    document = fitz.open()
    for content in pages:
        page = document.new_page()
        if content is not None:
            page.insert_textbox(fitz.Rect(36, 36, 560, 800), content, fontsize=9)
    payload = document.tobytes()
    document.close()
    return payload


def test_real_pdf_parser_extracts_engineering_fields_from_text_layer() -> None:
    model = RealPDFDatasheetParser().parse(
        _pdf_bytes([REAL_ESP32_S3_TEXT]),
        source_id="attachment:datasheet-1",
    )

    assert model.component.manufacturer == "Espressif Systems"
    assert model.component.part_number == "ESP32-S3"
    assert model.component.package == "QFN-56"
    assert model.metadata["family"] == "ESP32-S3"
    assert "LX7" in str(model.metadata["cpu"])
    assert model.metadata["sram"] == "512 KB SRAM"
    assert "Flash" in str(model.metadata["flash"])
    assert model.metadata["temperature"] == "-40 C to 85 C"
    assert model.metadata["source_id"] == "attachment:datasheet-1"
    assert {(item.protocol, item.name) for item in model.interfaces} >= {
        ("UART", "UART"),
        ("SPI", "SPI"),
        ("I2C", "I2C"),
        ("USB", "USB"),
        ("Camera", "DVP"),
    }
    assert [(pin.number, pin.name) for pin in model.pins] == [
        ("12", "GPIO8"),
        ("13", "GPIO9"),
    ]
    assert model.electrical_specs[0].min_value == pytest.approx(3.0)
    assert model.electrical_specs[0].max_value == pytest.approx(3.6)
    assert model.electrical_specs[1].max_value == pytest.approx(0.04)


def test_real_pdf_parser_preserves_page_source_without_raw_text() -> None:
    model = RealPDFDatasheetParser().parse(
        _pdf_bytes(["Cover page", REAL_ESP32_S3_TEXT]),
        source_id="attachment:datasheet-2",
    )

    serialized = model.model_dump_json()
    assert model.metadata["source_id"] == "attachment:datasheet-2"
    assert (
        "attachment:datasheet-2#page:2"
        in str(model.metadata["extraction_coverage"])
    )
    assert REAL_ESP32_S3_TEXT not in serialized


@pytest.mark.parametrize(
    "pages",
    [
        [None],
        [
            REAL_ESP32_S3_TEXT.replace(
                "12 GPIO8 Embedded Flash\n13 GPIO9 DVP camera data 0",
                "12 | GPIO8 | Flash | unexpected",
            )
        ],
    ],
)
def test_real_pdf_parser_safely_rejects_textless_or_ambiguous_tables(
    pages: list[str | None],
) -> None:
    with pytest.raises(RealPDFParseError):
        RealPDFDatasheetParser().parse(
            _pdf_bytes(pages),
            source_id="attachment:datasheet-error",
        )


def test_real_pdf_parser_rejects_ambiguous_row_after_valid_pin() -> None:
    ambiguous = REAL_ESP32_S3_TEXT.replace(
        "13 GPIO9 DVP camera data 0",
        "13 | GPIO9 | DVP camera data 0 | unexpected",
    )

    with pytest.raises(RealPDFParseError):
        RealPDFDatasheetParser().parse(
            _pdf_bytes([ambiguous]),
            source_id="attachment:datasheet-ambiguous",
        )


def test_real_pdf_parser_loads_pymupdf_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module(
        "embedded_copilot.datasheet.extensions.real_pdf.parser"
    )
    original = importlib.import_module

    def missing(name: str, package: str | None = None):
        if name == "fitz":
            raise ModuleNotFoundError("optional backend unavailable")
        return original(name, package)

    monkeypatch.setattr(module.importlib, "import_module", missing)

    with pytest.raises(RealPDFBackendUnavailable):
        module.RealPDFDatasheetParser().parse(
            b"%PDF-1.4",
            source_id="attachment:datasheet-optional",
        )
