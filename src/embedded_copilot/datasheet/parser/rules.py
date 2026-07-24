from __future__ import annotations

import math
import re

from embedded_copilot.datasheet.models import (
    DatasheetComponent,
    DatasheetElectricalSpec,
    DatasheetInterface,
    DatasheetPin,
    UnifiedDatasheetModel,
)


_COMPONENT_LABELS = {
    "manufacturer": "manufacturer",
    "part number": "part_number",
    "category": "category",
    "package": "package",
    "description": "description",
}
_SECTIONS = {
    "pins": "pins",
    "interfaces": "interfaces",
    "electrical specs": "electrical",
    "electrical specifications": "electrical",
}
_PACKAGE = re.compile(r"(?:QFN|BGA|LQFP)(?:[-_ ]?[A-Za-z0-9]+)*", re.IGNORECASE)
_TABLE_SEPARATOR = re.compile(r"^:?-{3,}:?$")


def extract_datasheet_model(text: str, *, source_format: str) -> UnifiedDatasheetModel:
    component_values: dict[str, str] = {}
    pins: list[DatasheetPin] = []
    interfaces: list[DatasheetInterface] = []
    electrical_specs: list[DatasheetElectricalSpec] = []
    section: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip().casefold()
            section = _SECTIONS.get(heading)
            continue

        identity_match = re.match(
            r"^(Manufacturer|Part Number|Category|Package|Description)\s*:\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if identity_match:
            label = _COMPONENT_LABELS[identity_match.group(1).casefold()]
            value = identity_match.group(2).strip()
            if not value or label in component_values:
                raise ValueError("component field is invalid")
            component_values[label] = value
            continue

        record_match = re.match(
            r"^(Pin|Interface|Voltage|Current)\s*:\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if record_match:
            label = record_match.group(1).casefold()
            values = _split_record(record_match.group(2))
            if label == "pin":
                pins.append(_parse_pin(values))
            elif label == "interface":
                interfaces.append(_parse_interface(values))
            else:
                electrical_specs.append(_parse_electrical(values, kind=label))
            continue

        if line.startswith("|") and line.endswith("|") and section is not None:
            values = [item.strip() for item in line.strip("|").split("|")]
            if _is_table_header(section, values) or _is_table_separator(values):
                continue
            if section == "pins":
                pins.append(_parse_pin(values))
            elif section == "interfaces":
                interfaces.append(_parse_interface(values))
            else:
                electrical_specs.append(_parse_electrical(values))

    if set(component_values) != set(_COMPONENT_LABELS.values()):
        raise ValueError("component identity is incomplete")
    if not _PACKAGE.fullmatch(component_values["package"]):
        raise ValueError("component package is unsupported")

    component = DatasheetComponent(**component_values)
    power_requirements = tuple(
        specification
        for specification in electrical_specs
        if _is_power_parameter(specification.parameter)
    )
    return UnifiedDatasheetModel(
        component=component,
        pins=tuple(pins),
        interfaces=tuple(interfaces),
        electrical_specs=tuple(electrical_specs),
        power_requirements=power_requirements,
        metadata={
            "format": source_format,
            "record_count": len(pins) + len(interfaces) + len(electrical_specs),
        },
    )


def _split_record(value: str) -> list[str]:
    if not value.strip():
        raise ValueError("record is empty")
    return [item.strip() for item in value.split("|")]


def _parse_pin(values: list[str]) -> DatasheetPin:
    if len(values) != 4 or any(not item for item in values):
        raise ValueError("pin record is invalid")
    return DatasheetPin(
        number=values[0],
        name=values[1],
        type=values[2],
        description=values[3],
    )


def _parse_interface(values: list[str]) -> DatasheetInterface:
    if len(values) != 3 or not values[0] or not values[1]:
        raise ValueError("interface record is invalid")
    pins = tuple(item.strip() for item in values[2].split(",") if item.strip())
    return DatasheetInterface(name=values[0], protocol=values[1], pins=pins)


def _parse_electrical(
    values: list[str],
    *,
    kind: str | None = None,
) -> DatasheetElectricalSpec:
    if len(values) != 5 or not values[0] or not values[4]:
        raise ValueError("electrical record is invalid")
    parameter = values[0]
    if kind == "voltage" and not re.search(r"voltage|supply|\bV\b", parameter, re.I):
        parameter = f"{parameter} voltage"
    if kind == "current" and not re.search(r"current", parameter, re.I):
        parameter = f"{parameter} current"
    unit = values[4].casefold()
    if unit == "v":
        normalized_unit = "V"
        multiplier = 1.0
    elif unit == "a":
        normalized_unit = "A"
        multiplier = 1.0
    elif unit == "ma":
        normalized_unit = "A"
        multiplier = 0.001
    else:
        raise ValueError("electrical unit is unsupported")
    converted = [
        None if value in {"", "-"} else _finite_float(value) * multiplier
        for value in values[1:4]
    ]
    return DatasheetElectricalSpec(
        parameter=parameter,
        min_value=converted[0],
        typical_value=converted[1],
        max_value=converted[2],
        unit=normalized_unit,
    )


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("electrical value is not finite")
    return number


def _is_power_parameter(parameter: str) -> bool:
    return bool(re.search(r"voltage|supply|current", parameter, re.IGNORECASE))


def _is_table_header(section: str, values: list[str]) -> bool:
    normalized = [value.casefold() for value in values]
    expected = {
        "pins": ["pin number", "pin name", "type", "description"],
        "interfaces": ["name", "protocol", "pins"],
        "electrical": ["parameter", "min", "typical", "max", "unit"],
    }
    return normalized == expected[section]


def _is_table_separator(values: list[str]) -> bool:
    return bool(values) and all(_TABLE_SEPARATOR.fullmatch(value) for value in values)
