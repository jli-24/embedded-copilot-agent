from __future__ import annotations

import re

from embedded_copilot.datasheet.extensions.real_pdf.section import ExtractedPage
from embedded_copilot.datasheet.models import (
    DatasheetComponent,
    DatasheetElectricalSpec,
    DatasheetInterface,
    DatasheetPin,
    UnifiedDatasheetModel,
)


class RealDatasheetExtractionError(ValueError):
    """Raised when text-layer evidence cannot be mapped without guessing."""


_PART = re.compile(r"\b(ESP32-S3(?:-[A-Z0-9]+)?|STM32[A-Z0-9]+)\b", re.I)
_PACKAGE = re.compile(r"\b(QFN[- ]?\d+|LQFP[- ]?\d+|BGA[- ]?\d+)\b", re.I)
_PIN_HEADER = re.compile(r"^Pin\s+(?:No\.?|Number)\s+Pin\s+Name\s+Function$", re.I)
_PIN_ROW = re.compile(r"^(\d+)\s+([A-Za-z][A-Za-z0-9_]*)\s+(.+)$")


def extract_datasheet_model(
    pages: tuple[ExtractedPage, ...],
    *,
    source_id: str,
) -> UnifiedDatasheetModel:
    combined = "\n".join(page.text for page in pages if page.text)
    if not combined.strip():
        raise RealDatasheetExtractionError("Datasheet text layer is empty")
    part_match = _PART.search(combined)
    package_match = _PACKAGE.search(combined)
    if part_match is None or package_match is None:
        raise RealDatasheetExtractionError("Datasheet identity is incomplete")
    part_number = part_match.group(1).upper()
    manufacturer = _manufacturer(combined, part_number)
    family = _labeled_value(combined, "Family") or _family(part_number)
    cpu = _labeled_value(combined, "CPU")
    temperature = _range_text(combined, "Operating temperature", "C")
    flash = _memory_value(combined, "Flash")
    sram = _memory_value(combined, "SRAM")

    voltage = _electrical_range(combined, "Operating voltage", "V")
    current = _electrical_range(combined, "Active current", "A")
    pins, pin_pages = _pins(pages)
    interfaces = _interfaces(combined, pins)
    if not (pins or interfaces or voltage or current):
        raise RealDatasheetExtractionError("Datasheet engineering evidence is empty")

    electrical = tuple(item for item in (voltage, current) if item is not None)
    fields = [
        name
        for name, value in (
            ("family", family),
            ("cpu", cpu),
            ("flash", flash),
            ("sram", sram),
            ("temperature", temperature),
            ("interfaces", interfaces),
            ("pins", pins),
        )
        if value
    ]
    evidence_pages = sorted({page.number for page in pages if page.text} | pin_pages)
    coverage = ";".join(
        (
            "pages:"
            + ",".join(
                f"{source_id}#page:{number}" for number in evidence_pages
            ),
            "fields:" + ",".join(fields),
        )
    )[:256]
    metadata = {
        "family": _bounded(family or "not_extracted"),
        "cpu": _bounded(cpu or "not_extracted"),
        "flash": _bounded(flash or "not_extracted"),
        "sram": _bounded(sram or "not_extracted"),
        "temperature": _bounded(temperature or "not_extracted"),
        "extraction_coverage": coverage,
        "source_id": source_id,
    }
    return UnifiedDatasheetModel(
        component=DatasheetComponent(
            manufacturer=manufacturer,
            part_number=part_number,
            category="MCU",
            package=package_match.group(1).replace(" ", "-"),
            description=f"{part_number} MCU extracted from PDF text layer",
        ),
        pins=tuple(pins),
        interfaces=tuple(interfaces),
        electrical_specs=electrical,
        power_requirements=electrical,
        metadata=metadata,
    )


def _manufacturer(text: str, part_number: str) -> str:
    if re.search(r"\bEspressif Systems\b", text, re.I):
        return "Espressif Systems"
    if re.search(r"\bSTMicroelectronics\b", text, re.I):
        return "STMicroelectronics"
    if part_number.startswith("ESP32"):
        raise RealDatasheetExtractionError("Datasheet manufacturer is missing")
    raise RealDatasheetExtractionError("Datasheet manufacturer is unsupported")


def _family(part_number: str) -> str:
    if part_number.startswith("ESP32-S3"):
        return "ESP32-S3"
    if part_number.startswith("STM32"):
        return "STM32"
    raise RealDatasheetExtractionError("Datasheet family is unsupported")


def _labeled_value(text: str, label: str) -> str | None:
    match = re.search(rf"^{re.escape(label)}\s*:\s*(.+)$", text, re.I | re.M)
    return _bounded(match.group(1).strip()) if match else None


def _range_text(text: str, label: str, unit: str) -> str | None:
    match = re.search(
        rf"^{re.escape(label)}\s*:\s*(-?\d+(?:\.\d+)?)\s*{unit}\s+to\s+"
        rf"(-?\d+(?:\.\d+)?)\s*{unit}\b",
        text,
        re.I | re.M,
    )
    if match is None:
        return None
    return f"{match.group(1)} {unit} to {match.group(2)} {unit}"


def _electrical_range(
    text: str,
    label: str,
    canonical_unit: str,
) -> DatasheetElectricalSpec | None:
    raw_unit = "mA" if canonical_unit == "A" else canonical_unit
    match = re.search(
        rf"^{re.escape(label)}\s*:\s*(\d+(?:\.\d+)?)\s*{raw_unit}\s+to\s+"
        rf"(\d+(?:\.\d+)?)\s*{raw_unit}\b",
        text,
        re.I | re.M,
    )
    if match is None:
        return None
    multiplier = 0.001 if raw_unit.casefold() == "ma" else 1.0
    return DatasheetElectricalSpec(
        parameter=label,
        min_value=float(match.group(1)) * multiplier,
        max_value=float(match.group(2)) * multiplier,
        unit=canonical_unit,
    )


def _memory_value(text: str, kind: str) -> str | None:
    size = re.search(rf"\b\d+(?:\.\d+)?\s*(?:KB|MB)\s+{kind}\b", text, re.I)
    if size:
        return _bounded(size.group(0))
    capability = re.search(rf"\b(?:external|embedded)\s+{kind}\s+support\b", text, re.I)
    return _bounded(capability.group(0)) if capability else None


def _pins(
    pages: tuple[ExtractedPage, ...],
) -> tuple[list[DatasheetPin], set[int]]:
    pins: list[DatasheetPin] = []
    evidence_pages: set[int] = set()
    table_seen = False
    for page in pages:
        lines = page.text.splitlines()
        for index, line in enumerate(lines):
            if not _PIN_HEADER.fullmatch(line):
                continue
            table_seen = True
            row_count = 0
            for row in lines[index + 1 :]:
                if row.startswith(("Interfaces:", "Memory:", "Operating ")):
                    break
                if "|" in row:
                    raise RealDatasheetExtractionError("Datasheet pin table is ambiguous")
                match = _PIN_ROW.fullmatch(row)
                if match is None:
                    break
                description = match.group(3).strip()
                if not description:
                    raise RealDatasheetExtractionError("Datasheet pin table is ambiguous")
                pins.append(
                    DatasheetPin(
                        number=match.group(1),
                        name=match.group(2),
                        type="alternate",
                        description=description,
                    )
                )
                evidence_pages.add(page.number)
                row_count += 1
            if row_count == 0:
                raise RealDatasheetExtractionError("Datasheet pin table is ambiguous")
    if table_seen and not pins:
        raise RealDatasheetExtractionError("Datasheet pin table is ambiguous")
    return pins, evidence_pages


def _interfaces(
    text: str,
    pins: list[DatasheetPin],
) -> list[DatasheetInterface]:
    line = re.search(r"^Interfaces\s*:\s*(.+)$", text, re.I | re.M)
    if line is None:
        return []
    value = line.group(1)
    supported = (
        ("UART", "UART", r"\bUART\b"),
        ("SPI", "SPI", r"\bSPI\b"),
        ("I2C", "I2C", r"\bI2C\b"),
        ("USB", "USB", r"\bUSB\b"),
        ("DVP", "Camera", r"\b(?:DVP|camera interface)\b"),
    )
    interfaces: list[DatasheetInterface] = []
    for name, protocol, pattern in supported:
        if not re.search(pattern, value, re.I):
            continue
        referenced = tuple(
            pin.number
            for pin in pins
            if protocol == "Camera" and re.search(r"\b(?:DVP|camera)\b", pin.description, re.I)
        )
        interfaces.append(
            DatasheetInterface(name=name, protocol=protocol, pins=referenced)
        )
    return interfaces


def _bounded(value: str) -> str:
    return value.strip()[:256]
