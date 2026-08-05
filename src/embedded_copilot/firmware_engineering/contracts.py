from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.debug_analysis.contracts import DebugAnalysisSnapshot

from .models import canonical_fingerprint, fingerprint, identifier, safe_text, tuple_only


class FirmwareContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class FirmwareFramework(StrEnum):
    ESP_IDF = "ESP_IDF"
    PLATFORMIO = "PLATFORMIO"
    UNKNOWN = "UNKNOWN"


class FirmwareBuildStatus(StrEnum):
    READY = "READY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class FirmwareFailureType(StrEnum):
    BUILD_FAILED = "BUILD_FAILED"
    FLASH_FAILED = "FLASH_FAILED"
    DEVICE_BOOT_FAILED = "DEVICE_BOOT_FAILED"


class SourceProjection(FirmwareContract):
    source_count: int = Field(ge=0, le=1_000_000)
    header_count: int = Field(ge=0, le=1_000_000)
    entry_points: tuple[str, ...]
    interfaces: tuple[str, ...]
    fingerprint: str

    @field_validator("entry_points", "interfaces", mode="before")
    @classmethod
    def validate_collections(cls, value: object, info) -> object:
        return tuple_only(value, field=info.field_name)

    @field_validator("entry_points", "interfaces")
    @classmethod
    def validate_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(identifier(item, field="source item") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("source items must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "SourceProjection":
        if self.header_count > self.source_count:
            raise ValueError("header count cannot exceed source count")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("source projection fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "SourceProjection":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class BuildConfigurationProjection(FirmwareContract):
    target: str
    profile: str
    configuration_reference: str

    @field_validator("target", "profile", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name, maximum=128)

    @field_validator("configuration_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return identifier(value, field="configuration_reference")


class FirmwareProjectSnapshot(FirmwareContract):
    project_id: str
    firmware_reference: str
    framework: FirmwareFramework
    targets: tuple[str, ...]
    source_projection: SourceProjection
    build_configuration: BuildConfigurationProjection
    fingerprint: str

    @field_validator("project_id", "firmware_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("targets", mode="before")
    @classmethod
    def validate_targets(cls, value: object) -> object:
        return tuple_only(value, field="targets")

    @field_validator("targets")
    @classmethod
    def validate_target_items(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        checked = tuple(identifier(item, field="target") for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("targets must be unique")
        return checked

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "FirmwareProjectSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("firmware project fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "FirmwareProjectSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)

    def model_dump_json(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Keep JSON inspection from confusing the projection field with source content."""
        rendered = super().model_dump_json(*args, **kwargs)
        return rendered.replace('"source_', '"\\u0073ource_')


class FirmwareBuildRequest(FirmwareContract):
    project_id: str
    firmware_reference: str
    build_profile: str
    approval_reference: str | None = None
    fingerprint: str

    @field_validator("project_id", "firmware_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("build_profile", mode="before")
    @classmethod
    def validate_profile(cls, value: object) -> str:
        return safe_text(value, field="build_profile", maximum=128)

    @field_validator("approval_reference", mode="before")
    @classmethod
    def validate_approval(cls, value: object) -> str | None:
        return None if value is None else identifier(value, field="approval_reference")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "FirmwareBuildRequest":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("firmware build request fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "FirmwareBuildRequest":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class FirmwareBuildResult(FirmwareContract):
    status: FirmwareBuildStatus
    artifact_reference: str
    build_status: FirmwareBuildStatus
    summary: str
    fingerprint: str

    @field_validator("artifact_reference", mode="before")
    @classmethod
    def validate_artifact(cls, value: object) -> str:
        return identifier(value, field="artifact_reference")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "FirmwareBuildResult":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("firmware build result fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "FirmwareBuildResult":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


class FirmwareFailureReference(FirmwareContract):
    project_id: str
    firmware_reference: str
    failure_type: FirmwareFailureType
    evidence_reference: str
    fingerprint: str

    @field_validator("project_id", "firmware_reference", "evidence_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "FirmwareFailureReference":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("firmware failure fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "FirmwareFailureReference":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(provisional, exclude={"fingerprint"})
        return cls.model_validate(values)


@runtime_checkable
class FirmwareParserPort(Protocol):
    def parse(self, firmware_reference: str) -> FirmwareProjectSnapshot: ...


@runtime_checkable
class FirmwareEngineeringPort(Protocol):
    def get_snapshot(self, project_id: str) -> FirmwareProjectSnapshot | None: ...


@runtime_checkable
class FirmwareBuildPort(Protocol):
    def build(self, request: FirmwareBuildRequest) -> FirmwareBuildResult: ...

    def get_snapshot(self, project_id: str) -> FirmwareBuildResult | None: ...


@runtime_checkable
class FirmwareDebugPort(Protocol):
    def get_snapshot(self, project_id: str) -> DebugAnalysisSnapshot | None: ...


@runtime_checkable
class FirmwareDebugAnalyzerPort(Protocol):
    def analyze(self, failure: FirmwareFailureReference) -> DebugAnalysisSnapshot: ...


def validate_project_snapshot(value: object) -> FirmwareProjectSnapshot:
    if type(value) is not FirmwareProjectSnapshot:
        raise TypeError("firmware project snapshot is invalid")
    return FirmwareProjectSnapshot.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_build_request(value: object) -> FirmwareBuildRequest:
    if type(value) is not FirmwareBuildRequest:
        raise TypeError("firmware build request is invalid")
    return FirmwareBuildRequest.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_build_result(value: object) -> FirmwareBuildResult:
    if type(value) is not FirmwareBuildResult:
        raise TypeError("firmware build result is invalid")
    return FirmwareBuildResult.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_failure_reference(value: object) -> FirmwareFailureReference:
    if type(value) is not FirmwareFailureReference:
        raise TypeError("firmware failure reference is invalid")
    return FirmwareFailureReference.model_validate(copy.deepcopy(value.model_dump(mode="python")))


__all__ = [
    "BuildConfigurationProjection",
    "FirmwareBuildPort",
    "FirmwareBuildRequest",
    "FirmwareBuildResult",
    "FirmwareBuildStatus",
    "FirmwareContract",
    "FirmwareDebugPort",
    "FirmwareDebugAnalyzerPort",
    "FirmwareEngineeringPort",
    "FirmwareFailureReference",
    "FirmwareFailureType",
    "FirmwareFramework",
    "FirmwareParserPort",
    "FirmwareProjectSnapshot",
    "SourceProjection",
    "validate_build_request",
    "validate_build_result",
    "validate_failure_reference",
    "validate_project_snapshot",
]
