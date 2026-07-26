from __future__ import annotations

import re

from embedded_copilot.datasheet_runtime.contracts.models import (
    InterfaceCandidate,
    InterfaceName,
)
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PdfStructure,
)

_INTERFACES: tuple[InterfaceName, ...] = (
    "UART",
    "SPI",
    "I2C",
    "USB",
    "CAN",
    "ADC",
    "PWM",
    "I2S",
)
_PATTERNS = {
    name: re.compile(
        rf"(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )
    for name in _INTERFACES
}


def extract_interface_candidates(
    structure: PdfStructure,
) -> tuple[InterfaceCandidate, ...]:
    text = "\n".join(_contexts(structure))
    return tuple(
        InterfaceCandidate(
            semantics="candidate",
            name=name,
        )
        for name in _INTERFACES
        if _PATTERNS[name].search(text)
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
