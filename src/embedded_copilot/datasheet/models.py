from __future__ import annotations

import copy
import math
import re
from collections.abc import Iterator, Mapping
from typing import TypeAlias

from pydantic import (
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from embedded_copilot.schemas.result import ContractModel


DatasheetMetadataScalar: TypeAlias = str | int | float | bool | None
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/|file://)", re.IGNORECASE)
_EMBEDDED_ABSOLUTE_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|\\\\|file://)",
    re.IGNORECASE,
)
_SENSITIVE_METADATA_TOKENS = frozenset({"body", "content", "path"})
_PROTOCOLS = {
    "uart": "UART",
    "spi": "SPI",
    "i2c": "I2C",
    "usb": "USB",
    "can": "CAN",
    "camera": "Camera",
}


class _FrozenDatasheetMetadata(Mapping[str, DatasheetMetadataScalar]):
    __slots__ = ("_items",)

    def __init__(
        self,
        items: Iterator[tuple[str, DatasheetMetadataScalar]],
    ) -> None:
        self._items = tuple(items)

    def __getitem__(self, key: str) -> DatasheetMetadataScalar:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __deepcopy__(
        self,
        memo: dict[int, object],
    ) -> "_FrozenDatasheetMetadata":
        return self


def _isolate_tuple(value: object) -> object:
    return tuple(copy.deepcopy(value)) if isinstance(value, (list, tuple)) else value


def _normalize_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    if _ABSOLUTE_PATH.match(normalized) or _EMBEDDED_ABSOLUTE_PATH.search(normalized):
        raise ValueError("Datasheet values must not contain absolute paths")
    return normalized


def _validate_metadata(value: object) -> dict[str, DatasheetMetadataScalar]:
    copied = copy.deepcopy(value)
    if not isinstance(copied, Mapping):
        raise ValueError("Datasheet metadata must be a mapping")
    result: dict[str, DatasheetMetadataScalar] = {}
    for raw_key, raw_value in copied.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError("Datasheet metadata keys must be non-empty strings")
        key = raw_key.strip()
        tokens = set(re.findall(r"[a-z0-9]+", key.casefold()))
        if tokens & _SENSITIVE_METADATA_TOKENS:
            raise ValueError("Datasheet metadata contains a forbidden key")
        if raw_value is not None and not isinstance(
            raw_value,
            (str, int, float, bool),
        ):
            raise ValueError("Datasheet metadata values must be scalar")
        normalized: DatasheetMetadataScalar = raw_value
        if isinstance(normalized, str):
            normalized = normalized.strip()
            if (
                not normalized
                or _ABSOLUTE_PATH.match(normalized)
                or _EMBEDDED_ABSOLUTE_PATH.search(normalized)
            ):
                raise ValueError("Datasheet metadata contains an invalid string")
        if isinstance(normalized, float) and not math.isfinite(normalized):
            raise ValueError("Datasheet metadata numbers must be finite")
        result[key] = normalized
    return dict(sorted(result.items()))


class _DatasheetModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
    )


class DatasheetComponent(_DatasheetModel):
    manufacturer: str = Field(min_length=1, max_length=256)
    part_number: str = Field(min_length=1, max_length=256)
    category: str = Field(min_length=1, max_length=128)
    package: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=1024)

    @field_validator(
        "manufacturer",
        "part_number",
        "category",
        "package",
        "description",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        return _normalize_text(value)


class DatasheetPin(_DatasheetModel):
    number: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1024)

    @field_validator("number", "name", "type", "description", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        return _normalize_text(value)


class DatasheetInterface(_DatasheetModel):
    name: str = Field(min_length=1, max_length=128)
    protocol: str = Field(min_length=1, max_length=32)
    pins: tuple[str, ...] = ()

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return _normalize_text(value)

    @field_validator("protocol", mode="before")
    @classmethod
    def normalize_protocol(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        try:
            return _PROTOCOLS[value.strip().casefold()]
        except KeyError:
            raise ValueError("Datasheet interface protocol is unsupported") from None

    @field_validator("pins", mode="before")
    @classmethod
    def isolate_pins(cls, value: object) -> object:
        return _isolate_tuple(value)

    @model_validator(mode="after")
    def validate_pins(self) -> "DatasheetInterface":
        normalized = [pin.strip() for pin in self.pins]
        if any(not pin or _ABSOLUTE_PATH.match(pin) for pin in normalized):
            raise ValueError("Datasheet interface pins are invalid")
        if len({pin.casefold() for pin in normalized}) != len(normalized):
            raise ValueError("Datasheet interface pins must be unique")
        if tuple(normalized) != self.pins:
            object.__setattr__(self, "pins", tuple(normalized))
        return self


class DatasheetElectricalSpec(_DatasheetModel):
    parameter: str = Field(min_length=1, max_length=256)
    min_value: float | None = None
    typical_value: float | None = None
    max_value: float | None = None
    unit: str = Field(min_length=1, max_length=32)

    @field_validator("parameter", "unit", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object:
        return _normalize_text(value)

    @field_validator("unit")
    @classmethod
    def validate_canonical_unit(cls, value: str) -> str:
        if value not in {"V", "A"}:
            raise ValueError("Datasheet electrical unit is not canonical")
        return value

    @field_validator("min_value", "typical_value", "max_value", mode="before")
    @classmethod
    def reject_boolean_values(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Datasheet electrical values must be numeric")
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "DatasheetElectricalSpec":
        values = [
            value
            for value in (self.min_value, self.typical_value, self.max_value)
            if value is not None
        ]
        if not values:
            raise ValueError("Datasheet electrical specification is empty")
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Datasheet electrical values must be finite")
        if values != sorted(values):
            raise ValueError("Datasheet electrical range is invalid")
        return self


class UnifiedDatasheetModel(_DatasheetModel):
    component: DatasheetComponent
    pins: tuple[DatasheetPin, ...] = ()
    interfaces: tuple[DatasheetInterface, ...] = ()
    electrical_specs: tuple[DatasheetElectricalSpec, ...] = ()
    power_requirements: tuple[DatasheetElectricalSpec, ...] = ()
    metadata: Mapping[str, DatasheetMetadataScalar] = Field(
        default_factory=lambda: _FrozenDatasheetMetadata(iter(()))
    )

    @field_validator("component", mode="before")
    @classmethod
    def isolate_component(cls, value: object) -> object:
        return copy.deepcopy(value)

    @field_validator(
        "pins",
        "interfaces",
        "electrical_specs",
        "power_requirements",
        mode="before",
    )
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        return _isolate_tuple(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def validate_metadata(cls, value: object) -> object:
        return _validate_metadata(value)

    @field_validator("metadata", mode="after")
    @classmethod
    def freeze_metadata(
        cls,
        value: Mapping[str, DatasheetMetadataScalar],
    ) -> Mapping[str, DatasheetMetadataScalar]:
        return _FrozenDatasheetMetadata(iter(value.items()))

    @field_serializer("metadata")
    def serialize_metadata(
        self,
        value: Mapping[str, DatasheetMetadataScalar],
    ) -> dict[str, DatasheetMetadataScalar]:
        return dict(value)

    @model_validator(mode="after")
    def validate_relations(self) -> "UnifiedDatasheetModel":
        pin_numbers = [pin.number.casefold() for pin in self.pins]
        if len(pin_numbers) != len(set(pin_numbers)):
            raise ValueError("Datasheet pin numbers must be unique")
        known_pins = set(pin_numbers)
        interface_names = [item.name.casefold() for item in self.interfaces]
        if len(interface_names) != len(set(interface_names)):
            raise ValueError("Datasheet interface names must be unique")
        if any(
            pin.casefold() not in known_pins
            for interface in self.interfaces
            for pin in interface.pins
        ):
            raise ValueError("Datasheet interface references an unknown pin")
        if not (self.pins or self.interfaces or self.electrical_specs):
            raise ValueError("Datasheet engineering evidence is empty")
        electrical_parameters = [
            specification.parameter.casefold()
            for specification in self.electrical_specs
        ]
        if len(electrical_parameters) != len(set(electrical_parameters)):
            raise ValueError("Datasheet electrical parameters must be unique")
        power_parameters = [
            requirement.parameter.casefold()
            for requirement in self.power_requirements
        ]
        if len(power_parameters) != len(set(power_parameters)):
            raise ValueError("Datasheet power parameters must be unique")
        electrical = {
            _electrical_key(specification) for specification in self.electrical_specs
        }
        if any(
            _electrical_key(requirement) not in electrical
            for requirement in self.power_requirements
        ):
            raise ValueError("Datasheet power requirements must be electrical specs")
        return self


def _electrical_key(
    specification: DatasheetElectricalSpec,
) -> tuple[str, float | None, float | None, float | None, str]:
    return (
        specification.parameter.casefold(),
        specification.min_value,
        specification.typical_value,
        specification.max_value,
        specification.unit.casefold(),
    )
