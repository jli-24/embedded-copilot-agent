from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator
from pydantic import field_validator

from embedded_copilot.hardware_design._validation import (
    HardwareDesignModel,
    safe_text,
    source_ids,
    tuple_values,
)

_V22_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_V22_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_V22_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file://|(?:^|\s)/)", re.I)
_V22_SENSITIVE = re.compile(
    r"(?:password|credential|secret|token|api[_ -]?key|provider)\s*[:=]",
    re.I,
)


def _v22_id(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not candidate or not _V22_ID.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _v22_text(
    value: object, *, field: str, maximum: int = 512, allow_empty: bool = False
) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        (not allow_empty and not candidate)
        or len(candidate) > maximum
        or any(char in candidate for char in ("\x00", "\r", "\n"))
        or _V22_PATH.search(candidate)
        or _V22_SENSITIVE.search(candidate)
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _v22_optional_text(value: object, *, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _v22_text(value, field=field, maximum=maximum)


def _v22_tuple(
    value: object, *, field: str, identifiers: bool = False
) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    validator = _v22_id if identifiers else _v22_text
    return tuple(validator(item, field=field) for item in value)


def _v22_fingerprint(value: object) -> str:
    if not isinstance(value, str) or not _V22_FP.fullmatch(value):
        raise ValueError("fingerprint is invalid")
    return value


def _v22_canonical(value: BaseModel, *, exclude: set[str]) -> str:
    encoded = json.dumps(
        value.model_dump(mode="json", exclude=exclude),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class V22Contract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class DesignSourceType(StrEnum):
    KICAD = "KICAD"
    ALTIUM = "ALTIUM"
    EASYEDA = "EASYEDA"
    UNKNOWN = "UNKNOWN"


class ProjectionStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PROJECTED = "PROJECTED"
    UNVERIFIED = "UNVERIFIED"


class ComponentProjection(V22Contract):
    reference: str
    value: str | None = None
    footprint: str | None = None
    manufacturer: str | None = None
    part_number: str | None = None
    status: ProjectionStatus

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _v22_id(value, field="reference")

    @field_validator("value", "footprint", "manufacturer", "part_number", mode="before")
    @classmethod
    def validate_optional_fields(cls, value: object, info) -> str | None:
        return _v22_optional_text(value, field=info.field_name)


class NetProjection(V22Contract):
    name: str
    connections: tuple[str, ...]
    signal_type: str

    @field_validator("name", "signal_type", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _v22_text(value, field=info.field_name)

    @field_validator("connections", mode="before")
    @classmethod
    def validate_connections(cls, value: object) -> tuple[str, ...]:
        return _v22_tuple(value, field="connections", identifiers=True)


class LayerProjection(V22Contract):
    name: str
    layer_type: str

    @field_validator("name", "layer_type", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _v22_text(value, field=info.field_name)


class InterfaceProjection(V22Contract):
    name: str
    protocol: str
    signals: tuple[str, ...]

    @field_validator("name", "protocol", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return _v22_text(value, field=info.field_name)

    @field_validator("signals", mode="before")
    @classmethod
    def validate_signals(cls, value: object) -> tuple[str, ...]:
        return _v22_tuple(value, field="signals", identifiers=True)


class UnifiedHardwareModel(V22Contract):
    project_id: str
    design_id: str
    design_source_type: DesignSourceType
    components: tuple[ComponentProjection, ...]
    nets: tuple[NetProjection, ...]
    layers: tuple[LayerProjection, ...]
    interfaces: tuple[InterfaceProjection, ...]
    constraints: tuple[str, ...]
    references: tuple[str, ...]
    fingerprint: str

    @field_validator("project_id", "design_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _v22_id(value, field=info.field_name)

    @field_validator("constraints", mode="before")
    @classmethod
    def validate_constraints(cls, value: object) -> tuple[str, ...]:
        return _v22_tuple(value, field="constraints")

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> tuple[str, ...]:
        return _v22_tuple(value, field="references", identifiers=True)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return _v22_fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "UnifiedHardwareModel":
        if self.fingerprint != _v22_canonical(self, exclude={"fingerprint"}):
            raise ValueError("unified hardware model fingerprint mismatch")
        component_ids = tuple(item.reference for item in self.components)
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component references must be unique")
        net_names = tuple(item.name for item in self.nets)
        layer_names = tuple(item.name for item in self.layers)
        interface_names = tuple(item.name for item in self.interfaces)
        if len(net_names) != len(set(net_names)):
            raise ValueError("net names must be unique")
        if len(layer_names) != len(set(layer_names)):
            raise ValueError("layer names must be unique")
        if len(interface_names) != len(set(interface_names)):
            raise ValueError("interface names must be unique")
        return self

    @classmethod
    def create(cls, **values: object) -> "UnifiedHardwareModel":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = _v22_canonical(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class HardwareCapabilitySnapshot(V22Contract):
    project_id: str
    parser_available: bool
    review_available: bool
    source_type: DesignSourceType
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project_id(cls, value: object) -> str:
        return _v22_id(value, field="project_id")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return _v22_fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "HardwareCapabilitySnapshot":
        if self.fingerprint != _v22_canonical(self, exclude={"fingerprint"}):
            raise ValueError("hardware capability fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "HardwareCapabilitySnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = _v22_canonical(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class GPIOAssignmentStatus(StrEnum):
    ASSIGNED = "assigned"
    CONFLICT = "conflict"
    UNRESOLVED = "unresolved"


class DesignModule(HardwareDesignModel):
    name: str
    description: str
    source_ids: tuple[str, ...] = ()

    @field_validator("name", "description", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return source_ids(value)


class DesignComponent(HardwareDesignModel):
    name: str
    category: str
    purpose: str
    source_ids: tuple[str, ...] = ()

    @field_validator("name", "category", "purpose", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return source_ids(value)


class DesignConnection(HardwareDesignModel):
    from_component: str
    to_component: str
    interface: str
    description: str
    source_ids: tuple[str, ...] = ()

    @field_validator(
        "from_component",
        "to_component",
        "interface",
        "description",
        mode="before",
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return source_ids(value)


class GPIOAssignment(HardwareDesignModel):
    function: str
    gpio: str
    interface: str
    reason: str
    status: GPIOAssignmentStatus
    source_ids: tuple[str, ...] = ()

    @field_validator("function", "gpio", "interface", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return source_ids(value)


class PowerTree(HardwareDesignModel):
    input: str
    stages: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @field_validator("input", mode="before")
    @classmethod
    def validate_input(cls, value: object) -> str:
        return safe_text(value, field="input")

    @field_validator("stages", "consumers", "limitations", mode="before")
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        return tuple_values(value)

    @field_validator("stages", "consumers", "limitations")
    @classmethod
    def validate_collections(cls, value: tuple[str, ...], info) -> tuple[str, ...]:
        return tuple(safe_text(item, field=info.field_name) for item in value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return source_ids(value)


class HardwareDesignBlueprint(HardwareDesignModel):
    project_name: str
    target_platform: str
    modules: tuple[DesignModule, ...] = ()
    components: tuple[DesignComponent, ...] = ()
    connections: tuple[DesignConnection, ...] = ()
    gpio_assignments: tuple[GPIOAssignment, ...] = ()
    power_tree: PowerTree
    constraints: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @field_validator("project_name", "target_platform", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator(
        "modules",
        "components",
        "connections",
        "gpio_assignments",
        "constraints",
        "limitations",
        mode="before",
    )
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        return tuple_values(value)

    @field_validator("constraints", "limitations")
    @classmethod
    def validate_text_collections(
        cls,
        value: tuple[str, ...],
        info,
    ) -> tuple[str, ...]:
        return tuple(safe_text(item, field=info.field_name) for item in value)

    @field_validator("source_ids", mode="before")
    @classmethod
    def validate_sources(cls, value: object) -> object:
        return source_ids(value)
