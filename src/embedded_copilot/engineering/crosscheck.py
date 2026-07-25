from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field

from embedded_copilot.datasheet.models import UnifiedDatasheetModel
from embedded_copilot.firmware.review.models import FirmwareReviewResult
from embedded_copilot.schemas.result import ContractModel


class EngineeringCrossCheckFinding(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    rule_id: Literal["datasheet-firmware-gpio-conflict"]
    severity: Literal["high"]
    description: str = Field(min_length=1, max_length=512)
    recommendation: str = Field(min_length=1, max_length=512)
    source_ids: tuple[str, str]


def cross_check(
    datasheet: UnifiedDatasheetModel,
    firmware: FirmwareReviewResult,
) -> tuple[EngineeringCrossCheckFinding, ...]:
    if not isinstance(datasheet, UnifiedDatasheetModel) or not isinstance(
        firmware, FirmwareReviewResult
    ):
        raise TypeError("engineering cross-check input is invalid")
    candidates: dict[str, dict[tuple[str, str], str | None]] = {}
    for pin in datasheet.pins:
        restricted_name = (
            pin.name
            if re.search(r"\b(?:flash|reserved|fixed)\b", pin.description, re.I)
            else None
        )
        for alias in _pin_aliases(pin.number, pin.name):
            candidates.setdefault(alias, {})[
                (pin.number, pin.name.casefold())
            ] = restricted_name
    restricted = {
        alias: next(iter(pins.values()))
        for alias, pins in candidates.items()
        if len(pins) == 1 and next(iter(pins.values())) is not None
    }
    datasheet_source = str(
        datasheet.metadata.get("source_id", "attachment:datasheet")
    )
    findings: list[EngineeringCrossCheckFinding] = []
    seen: set[tuple[str, str]] = set()
    for assignment in firmware.gpio_assignments:
        alias = _normalize_pin(assignment.pin)
        pin_name = restricted.get(alias)
        if pin_name is None or assignment.role.casefold() in {"flash", "reserved"}:
            continue
        key = (alias, assignment.role.casefold())
        if key in seen:
            continue
        seen.add(key)
        findings.append(
            EngineeringCrossCheckFinding(
                rule_id="datasheet-firmware-gpio-conflict",
                severity="high",
                description=(
                    f"{pin_name} is documented for a restricted Datasheet function "
                    f"but Firmware assigns the {assignment.role} role."
                ),
                recommendation=(
                    "Select a non-conflicting GPIO or verify an explicitly documented "
                    "pin-multiplexing configuration before implementation."
                ),
                source_ids=(
                    datasheet_source,
                    f"{assignment.source_id}#line:{assignment.line}",
                ),
            )
        )
    return tuple(findings)


def _pin_aliases(number: str, name: str) -> tuple[str, ...]:
    values = {_normalize_pin(name)}
    if re.fullmatch(r"(?:GPIO|IO)[-_ ]?\d+", number, re.I):
        values.add(_normalize_pin(number))
    return tuple(sorted(value for value in values if value))


def _normalize_pin(value: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    match = re.fullmatch(r"(?:GPIO|IO)(\d+)", compact)
    return f"GPIO{int(match.group(1))}" if match else compact
