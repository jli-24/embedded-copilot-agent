from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,63}$")
_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://|/(?:[^/\s]+/)+)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|(?:password|credential|secret)\s*[:=]"
    r"|(?:^|\s)sk-[A-Za-z0-9_-]{8,})",
    re.IGNORECASE,
)

ComponentFamily = Literal["STM32", "ESP32", "nRF52", "RP2040"]
InterfaceName = Literal["UART", "SPI", "I2C", "USB", "CAN", "ADC", "PWM", "I2S"]
ElectricalKind = Literal[
    "voltage_range",
    "operating_temperature",
    "current_range",
]
ElectricalUnit = Literal["V", "A", "degC"]
SectionName = Literal[
    "Pin Description",
    "Electrical Characteristics",
    "Absolute Maximum Ratings",
    "Functional Description",
    "Peripheral",
]


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    candidate = value.strip()
    if not _SAFE_IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _instruction(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("instruction_summary must be a string")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > 512
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _ABSOLUTE_PATH.search(candidate)
        or _SENSITIVE_TEXT.search(candidate)
    ):
        raise ValueError("instruction_summary is unsafe")
    return candidate


class _DatasheetContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ComponentCandidate(_DatasheetContract):
    semantics: Literal["candidate"] = "candidate"
    family: ComponentFamily
    model: str | None = None

    @field_validator("model", mode="before")
    @classmethod
    def validate_model(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("model must be a string")
        candidate = value.strip()
        if not _SAFE_MODEL.fullmatch(candidate):
            raise ValueError("model is invalid")
        return candidate


class InterfaceCandidate(_DatasheetContract):
    semantics: Literal["candidate"] = "candidate"
    name: InterfaceName


class ElectricalCandidate(_DatasheetContract):
    semantics: Literal["candidate"] = "candidate"
    kind: ElectricalKind
    minimum: float | None = None
    maximum: float | None = None
    unit: ElectricalUnit

    @field_validator("minimum", "maximum")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("electrical bounds must be finite")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "ElectricalCandidate":
        if self.minimum is None and self.maximum is None:
            raise ValueError("at least one electrical bound is required")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("electrical bounds are reversed")
        expected_unit = {
            "voltage_range": "V",
            "operating_temperature": "degC",
            "current_range": "A",
        }[self.kind]
        if self.unit != expected_unit:
            raise ValueError("electrical unit does not match candidate kind")
        return self


class SectionCandidate(_DatasheetContract):
    semantics: Literal["candidate"] = "candidate"
    name: SectionName


class DatasheetRequest(_DatasheetContract):
    session_id: str
    file_id: str
    instruction_summary: str

    @field_validator("session_id", "file_id", mode="before")
    @classmethod
    def validate_identifier(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("instruction_summary", mode="before")
    @classmethod
    def validate_instruction_summary(cls, value: object) -> str:
        return _instruction(value)


class DatasheetSummary(_DatasheetContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    file_id: str
    component_candidate: ComponentCandidate | None = None
    interface_candidates: tuple[InterfaceCandidate, ...] = ()
    electrical_candidates: tuple[ElectricalCandidate, ...] = ()
    section_candidates: tuple[SectionCandidate, ...] = ()

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return _identifier(value, field="file_id")

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> "DatasheetSummary":
        if len({item.name for item in self.interface_candidates}) != len(
            self.interface_candidates
        ):
            raise ValueError("interface candidates must be unique")
        if len({item.name for item in self.section_candidates}) != len(
            self.section_candidates
        ):
            raise ValueError("section candidates must be unique")
        electrical_keys = {
            (item.kind, item.minimum, item.maximum, item.unit)
            for item in self.electrical_candidates
        }
        if len(electrical_keys) != len(self.electrical_candidates):
            raise ValueError("electrical candidates must be unique")
        return self


class DatasheetResponse(_DatasheetContract):
    output_type: Literal["reasoning_suggestion"] = "reasoning_suggestion"
    summary: DatasheetSummary
    review_required: Literal[True] = True
