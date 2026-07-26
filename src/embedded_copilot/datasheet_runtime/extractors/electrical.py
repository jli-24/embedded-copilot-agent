from __future__ import annotations

import re

from embedded_copilot.datasheet_runtime.contracts.models import (
    ElectricalCandidate,
    ElectricalKind,
)
from embedded_copilot.datasheet_runtime.parser.pdf_structure import (
    PdfStructure,
)

_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?")
_UNIT = re.compile(
    r"(?<![A-Za-z])(?:mV|V|mA|uA|A|degC|C)(?![A-Za-z])",
    re.IGNORECASE,
)


def extract_electrical_candidates(
    structure: PdfStructure,
) -> tuple[ElectricalCandidate, ...]:
    candidates: list[ElectricalCandidate] = []
    seen: set[tuple[str, float | None, float | None, str]] = set()
    for page in structure.pages:
        contexts = [line for line in page.text.splitlines() if line.strip()]
        contexts.extend(
            " ".join(cell for cell in row if cell)
            for table in page.tables
            for row in table.rows
        )
        for context in contexts:
            candidate = _candidate(context)
            if candidate is None:
                continue
            key = (
                candidate.kind,
                candidate.minimum,
                candidate.maximum,
                candidate.unit,
            )
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
    return tuple(candidates)


def _candidate(context: str) -> ElectricalCandidate | None:
    kind = _kind(context)
    if kind is None:
        return None
    unit_match = _UNIT.search(context)
    if unit_match is None:
        return None
    values = tuple(float(match.group()) for match in _NUMBER.finditer(context))
    if not values:
        return None
    minimum: float | None
    maximum: float | None
    lowered = context.casefold()
    if len(values) >= 2:
        minimum, maximum = values[-2:]
    elif any(token in lowered for token in ("maximum", "max", "up to", "<=")):
        minimum, maximum = None, values[0]
    elif any(token in lowered for token in ("minimum", "min", "at least", ">=")):
        minimum, maximum = values[0], None
    else:
        return None
    unit, scale = _normalized_unit(kind, unit_match.group())
    return ElectricalCandidate(
        semantics="candidate",
        kind=kind,
        minimum=None if minimum is None else minimum * scale,
        maximum=None if maximum is None else maximum * scale,
        unit=unit,
    )


def _kind(context: str) -> ElectricalKind | None:
    lowered = context.casefold()
    if "voltage" in lowered and any(
        token in lowered for token in ("range", "operating", "supply")
    ):
        return "voltage_range"
    if "temperature" in lowered and "operating" in lowered:
        return "operating_temperature"
    if "current" in lowered and any(
        token in lowered for token in ("range", "operating", "supply")
    ):
        return "current_range"
    return None


def _normalized_unit(
    kind: ElectricalKind,
    raw_unit: str,
) -> tuple[str, float]:
    normalized = raw_unit.casefold()
    if kind == "voltage_range":
        return "V", 0.001 if normalized == "mv" else 1.0
    if kind == "current_range":
        if normalized == "ma":
            return "A", 0.001
        if normalized == "ua":
            return "A", 0.000001
        return "A", 1.0
    return "degC", 1.0
