from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .models import canonical_fingerprint, fingerprint, identifier, safe_text


class ToolchainContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class BuildStatus(StrEnum):
    PENDING = "PENDING"
    BUILDING = "BUILDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class WorkspaceStatus(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    PROJECTED = "PROJECTED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"


class ToolchainArtifactReference(ToolchainContract):
    reference_id: str
    artifact_type: str

    @field_validator("reference_id", "artifact_type", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)


class BuildResult(ToolchainContract):
    status: BuildStatus
    artifact_reference: ToolchainArtifactReference | None = None
    summary: str
    fingerprint: str

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_text(value, field="summary", maximum=1024)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def validate_result(self) -> "BuildResult":
        if self.status is BuildStatus.SUCCESS and self.artifact_reference is None:
            raise ValueError("successful build requires artifact")
        if self.status is BuildStatus.FAILED and self.artifact_reference is not None:
            raise ValueError("failed build cannot expose artifact")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("build result fingerprint mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        status: BuildStatus,
        artifact_reference: ToolchainArtifactReference | None,
        summary: str,
    ) -> "BuildResult":
        provisional = cls.model_construct(
            status=status,
            artifact_reference=artifact_reference,
            summary=summary,
            fingerprint="sha256:" + "0" * 64,
        )
        return cls.model_validate(
            {
                **provisional.model_dump(mode="python"),
                "fingerprint": canonical_fingerprint(
                    provisional, exclude={"fingerprint"}
                ),
            }
        )


class ToolchainSnapshot(ToolchainContract):
    build_status: BuildStatus
    artifact: ToolchainArtifactReference | None
    workspace_status: WorkspaceStatus
    fingerprint: str

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_snapshot_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_fingerprint(self) -> "ToolchainSnapshot":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("toolchain snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "ToolchainSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class BuildPort(Protocol):
    def build(self, workspace_reference: str) -> BuildResult: ...


@runtime_checkable
class ToolchainSnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> ToolchainSnapshot | None: ...


class FlashPort:
    def flash(self, workspace_reference: str) -> None:
        from .exceptions import FlashUnavailable

        raise FlashUnavailable()


class RunPort:
    def run(self, workspace_reference: str) -> None:
        from .exceptions import RunUnavailable

        raise RunUnavailable()


def build_result_fingerprint(value: BuildResult) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def toolchain_snapshot_fingerprint(value: ToolchainSnapshot) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_build_result(value: object) -> BuildResult:
    if type(value) is not BuildResult:
        raise TypeError("build result is invalid")
    return BuildResult.model_validate(copy.deepcopy(value.model_dump(mode="python")))


def validate_toolchain_snapshot(value: object) -> ToolchainSnapshot:
    if type(value) is not ToolchainSnapshot:
        raise TypeError("toolchain snapshot is invalid")
    return ToolchainSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "BuildPort",
    "BuildResult",
    "BuildStatus",
    "FlashPort",
    "RunPort",
    "ToolchainArtifactReference",
    "ToolchainSnapshot",
    "ToolchainSnapshotPort",
    "WorkspaceStatus",
    "build_result_fingerprint",
    "toolchain_snapshot_fingerprint",
    "validate_build_result",
    "validate_toolchain_snapshot",
]
