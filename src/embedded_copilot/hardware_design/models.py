from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator

from embedded_copilot.hardware_design._validation import (
    HardwareDesignModel,
    safe_text,
    source_ids,
    tuple_values,
)


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
