from __future__ import annotations

import re

from embedded_copilot.datasheet_runtime.contracts.models import (
    ComponentCandidate,
    ComponentFamily,
)
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PdfStructure,
)

_MODEL_PATTERNS: tuple[
    tuple[ComponentFamily, re.Pattern[str]],
    ...,
] = (
    (
        "STM32",
        re.compile(
            r"(?<![A-Za-z0-9])STM32[A-Z0-9]{4,18}(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    (
        "ESP32",
        re.compile(
            r"(?<![A-Za-z0-9])ESP32(?:-[A-Z0-9]{1,12})+(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    (
        "nRF52",
        re.compile(
            r"(?<![A-Za-z0-9])NRF52\d{3}(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    (
        "RP2040",
        re.compile(
            r"(?<![A-Za-z0-9])RP2040(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
)
_FAMILY_PATTERNS: tuple[
    tuple[ComponentFamily, re.Pattern[str]],
    ...,
] = (
    (
        "STM32",
        re.compile(
            r"(?<![A-Za-z0-9])STM32(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    (
        "ESP32",
        re.compile(
            r"(?<![A-Za-z0-9])ESP32(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    (
        "nRF52",
        re.compile(
            r"(?<![A-Za-z0-9])NRF52(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
    (
        "RP2040",
        re.compile(
            r"(?<![A-Za-z0-9])RP2040(?![A-Za-z0-9])",
            re.IGNORECASE,
        ),
    ),
)


def extract_component_candidate(
    structure: PdfStructure,
) -> ComponentCandidate | None:
    text = "\n".join(_contexts(structure))
    models: set[tuple[ComponentFamily, str]] = set()
    families: set[ComponentFamily] = set()
    for family, pattern in _MODEL_PATTERNS:
        for match in pattern.finditer(text):
            models.add((family, _canonical_model(family, match.group())))
    for family, pattern in _FAMILY_PATTERNS:
        if pattern.search(text):
            families.add(family)
    families.update(family for family, _ in models)
    if len(models) > 1 or len(families) != 1:
        return None
    if models:
        family, model = next(iter(models))
        return ComponentCandidate(
            semantics="candidate",
            family=family,
            model=model,
        )
    family = next(iter(families))
    return ComponentCandidate(
        semantics="candidate",
        family=family,
        model=None,
    )


def _contexts(structure: PdfStructure) -> tuple[str, ...]:
    values: list[str] = []
    for page in structure.pages:
        values.append(page.text)
        values.extend(
            cell
            for table in page.tables
            for row in table.rows
            for cell in row
            if cell
        )
    return tuple(values)


def _canonical_model(family: ComponentFamily, value: str) -> str:
    normalized = value.upper()
    if family == "nRF52":
        return f"nRF{normalized[3:]}"
    return normalized
