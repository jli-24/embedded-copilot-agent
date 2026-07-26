from __future__ import annotations

from embedded_copilot.datasheet_runtime.extractors.interface import (
    extract_interface_candidates,
)
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PdfPageStructure,
    PdfStructure,
)
from embedded_copilot.datasheet_runtime.parser.table import TableStructure


def _structure(
    text: str,
    *,
    cells: tuple[str, ...] = (),
) -> PdfStructure:
    return PdfStructure(
        page_count=1,
        pages=(
            PdfPageStructure(
                page_number=1,
                text=text,
                tables=(
                    (TableStructure(rows=(cells,)),)
                    if cells
                    else ()
                ),
            ),
        ),
    )


def test_interfaces_are_deduplicated_in_canonical_order() -> None:
    candidates = extract_interface_candidates(
        _structure(
            "I2S PWM ADC CAN USB I2C SPI UART\n"
            "spi uart i2c usb can adc pwm i2s"
        )
    )

    assert tuple(
        (candidate.semantics, candidate.name)
        for candidate in candidates
    ) == (
        ("candidate", "UART"),
        ("candidate", "SPI"),
        ("candidate", "I2C"),
        ("candidate", "USB"),
        ("candidate", "CAN"),
        ("candidate", "ADC"),
        ("candidate", "PWM"),
        ("candidate", "I2S"),
    )


def test_interface_candidates_can_come_from_table_cells() -> None:
    candidates = extract_interface_candidates(
        _structure(
            "Peripheral summary",
            cells=("Communication", "UART", "SPI", "I2C"),
        )
    )

    assert tuple(candidate.name for candidate in candidates) == (
        "UART",
        "SPI",
        "I2C",
    )


def test_interface_extraction_does_not_infer_gpio_or_pin_relationships() -> None:
    candidates = extract_interface_candidates(
        _structure(
            "SPI GPIO4 MOSI pin connection; UART0 TX pin; CANARY SPICE"
        )
    )

    assert tuple(candidate.name for candidate in candidates) == ("SPI",)
    serialized = tuple(
        candidate.model_dump(mode="json") for candidate in candidates
    )
    assert serialized == (
        {"semantics": "candidate", "name": "SPI"},
    )
    assert "GPIO4" not in str(serialized)
    assert "MOSI" not in str(serialized)
    assert not hasattr(candidates[0], "pins")
    assert not hasattr(candidates[0], "mapping")


def test_unbounded_interface_fragments_are_not_candidates() -> None:
    candidates = extract_interface_candidates(
        _structure("SPICE CANARY UART0 I2C1 USBHS ADCS PWMS I2S2")
    )

    assert candidates == ()
