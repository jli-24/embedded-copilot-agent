from __future__ import annotations

import copy
import re
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from embedded_copilot.schemas.result import ContractModel


FirmwareSeverity = Literal["low", "medium", "high"]
_SAFE_SOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_SAFE_FILENAME = re.compile(r"^[^/\\\r\n\x00]{1,255}$")


class _ReviewModel(ContractModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    @field_validator("source_id", mode="before", check_fields=False)
    @classmethod
    def validate_source_id(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if not _SAFE_SOURCE_ID.fullmatch(candidate):
                raise ValueError("firmware source identifier is invalid")
            return candidate
        return value

    @field_validator("filename", mode="before", check_fields=False)
    @classmethod
    def validate_display_filename(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if not _SAFE_FILENAME.fullmatch(candidate) or candidate in {".", ".."}:
                raise ValueError("firmware filename is invalid")
            return candidate
        return value

    @field_validator("source_ids", mode="before", check_fields=False)
    @classmethod
    def validate_source_id_collection(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        normalized = tuple(item.strip() if isinstance(item, str) else item for item in value)
        if any(
            not isinstance(item, str) or not _SAFE_SOURCE_ID.fullmatch(item)
            for item in normalized
        ):
            raise ValueError("firmware source identifier is invalid")
        return normalized


class FirmwareSource(_ReviewModel):
    filename: str = Field(min_length=1, max_length=255)
    source_id: str = Field(min_length=1, max_length=160)
    language: Literal["C", "C++", "C Header", "C++ Header"]
    text: str = Field(min_length=1)

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate or "/" in candidate or "\\" in candidate:
                raise ValueError("firmware filename is invalid")
            return candidate
        return value


class FirmwareFunction(_ReviewModel):
    name: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    line: int = Field(ge=1)
    calls: tuple[str, ...] = ()


class FirmwareTaskEvidence(_ReviewModel):
    function: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=160)
    line: int = Field(ge=1)
    infinite_loop: bool = False
    has_blocking_call: bool = False


class FirmwareGPIOAssignment(_ReviewModel):
    pin: str = Field(min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=128)
    source_id: str = Field(min_length=1, max_length=160)
    line: int = Field(ge=1)
    initialized: bool = False


class FirmwareFinding(_ReviewModel):
    rule_id: str = Field(min_length=1, max_length=80)
    severity: FirmwareSeverity
    description: str = Field(min_length=1, max_length=512)
    recommendation: str = Field(min_length=1, max_length=512)
    source_ids: tuple[str, ...]
    filename: str = Field(min_length=1, max_length=255)
    line: int = Field(ge=1)


class FirmwareReviewResult(_ReviewModel):
    files: tuple[str, ...] = ()
    platform: str | None = None
    framework: str | None = None
    entrypoints: tuple[str, ...] = ()
    functions: tuple[FirmwareFunction, ...] = ()
    initialization_flow: tuple[str, ...] = ()
    tasks: tuple[FirmwareTaskEvidence, ...] = ()
    interrupts: tuple[str, ...] = ()
    allocations: tuple[str, ...] = ()
    peripherals: tuple[str, ...] = ()
    gpio_assignments: tuple[FirmwareGPIOAssignment, ...] = ()
    findings: tuple[FirmwareFinding, ...] = ()
    limitations: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @field_validator(
        "files",
        "entrypoints",
        "functions",
        "initialization_flow",
        "tasks",
        "interrupts",
        "allocations",
        "peripherals",
        "gpio_assignments",
        "findings",
        "limitations",
        "source_ids",
        mode="before",
    )
    @classmethod
    def isolate_collections(cls, value: object) -> object:
        return tuple(copy.deepcopy(value)) if isinstance(value, (list, tuple)) else value

    @field_validator("files")
    @classmethod
    def validate_files(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip() for item in value)
        if any(
            not _SAFE_FILENAME.fullmatch(item) or item in {".", ".."}
            for item in normalized
        ):
            raise ValueError("firmware filename is invalid")
        return normalized

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _SAFE_SOURCE_ID.fullmatch(item) for item in value):
            raise ValueError("firmware source identifier is invalid")
        return value
