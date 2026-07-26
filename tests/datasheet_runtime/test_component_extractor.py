from __future__ import annotations

import pytest

from embedded_copilot.datasheet_runtime.extractors.component import (
    extract_component_candidate,
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
    tables = (
        (TableStructure(rows=(cells,)),)
        if cells
        else ()
    )
    return PdfStructure(
        page_count=1,
        pages=(
            PdfPageStructure(
                page_number=1,
                text=text,
                tables=tables,
            ),
        ),
    )


@pytest.mark.parametrize(
    ("source", "family", "model"),
    (
        ("STM32F103C8T6 microcontroller", "STM32", "STM32F103C8T6"),
        ("esp32-s3 technical reference", "ESP32", "ESP32-S3"),
        ("nrf52840 product specification", "nRF52", "nRF52840"),
        ("RP2040 datasheet", "RP2040", "RP2040"),
    ),
)
def test_supported_component_models_are_unverified_candidates(
    source: str,
    family: str,
    model: str,
) -> None:
    candidate = extract_component_candidate(_structure(source))

    assert candidate is not None
    assert candidate.model_dump(mode="json") == {
        "semantics": "candidate",
        "family": family,
        "model": model,
    }
    assert not hasattr(candidate, "promote")
    assert not hasattr(candidate, "to_engineering_fact")


@pytest.mark.parametrize(
    ("source", "family"),
    (
        ("STM32 family overview", "STM32"),
        ("ESP32 family overview", "ESP32"),
        ("nRF52 family overview", "nRF52"),
    ),
)
def test_unique_family_without_model_remains_candidate(
    source: str,
    family: str,
) -> None:
    candidate = extract_component_candidate(_structure(source))

    assert candidate is not None
    assert candidate.semantics == "candidate"
    assert candidate.family == family
    assert candidate.model is None


def test_component_model_can_be_detected_from_table_cells() -> None:
    candidate = extract_component_candidate(
        _structure(
            "Ordering information",
            cells=("Part number", "STM32G431CBT6"),
        )
    )

    assert candidate is not None
    assert candidate.family == "STM32"
    assert candidate.model == "STM32G431CBT6"


@pytest.mark.parametrize(
    "source",
    (
        "STM32F103C8T6 and STM32G431CBT6",
        "STM32F103C8T6 compared with ESP32-S3",
        "STM32 and ESP32 family comparison",
        "XSTM32F103C8T6 is not a bounded part token",
        "ESP32S3 omits the required model separator",
        "nRF521 is not a complete supported model",
        "unrelated controller",
    ),
)
def test_ambiguous_or_unbounded_component_text_returns_no_candidate(
    source: str,
) -> None:
    assert extract_component_candidate(_structure(source)) is None


def test_repeated_identical_model_is_deduplicated() -> None:
    candidate = extract_component_candidate(
        _structure("ESP32-C3 overview\nESP32-C3 pin description")
    )

    assert candidate is not None
    assert candidate.family == "ESP32"
    assert candidate.model == "ESP32-C3"
