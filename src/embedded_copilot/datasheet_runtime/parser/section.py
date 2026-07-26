from __future__ import annotations

import re

from embedded_copilot.datasheet_runtime.contracts.models import (
    SectionCandidate,
    SectionName,
)
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PdfStructure,
)

_SECTION_PATTERNS: tuple[tuple[SectionName, re.Pattern[str]], ...] = (
    (
        "Pin Description",
        re.compile(r"^(?:\d+(?:\.\d+)*\s+)?pin\s+description$", re.IGNORECASE),
    ),
    (
        "Electrical Characteristics",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\s+)?electrical\s+characteristics$",
            re.IGNORECASE,
        ),
    ),
    (
        "Absolute Maximum Ratings",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\s+)?absolute\s+maximum\s+ratings$",
            re.IGNORECASE,
        ),
    ),
    (
        "Functional Description",
        re.compile(
            r"^(?:\d+(?:\.\d+)*\s+)?functional\s+description$",
            re.IGNORECASE,
        ),
    ),
    (
        "Peripheral",
        re.compile(r"^(?:\d+(?:\.\d+)*\s+)?peripherals?$", re.IGNORECASE),
    ),
)


def detect_sections(structure: PdfStructure) -> tuple[SectionCandidate, ...]:
    detected: list[SectionCandidate] = []
    names: set[SectionName] = set()
    for page in structure.pages:
        for raw_line in page.text.splitlines():
            line = " ".join(raw_line.strip().rstrip(":").split())
            for name, pattern in _SECTION_PATTERNS:
                if name not in names and pattern.fullmatch(line):
                    names.add(name)
                    detected.append(
                        SectionCandidate(
                            semantics="candidate",
                            name=name,
                        )
                    )
                    break
    return tuple(detected)
