from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.engineering_generation.contracts import (
    FirmwareArtifact,
    HardwareDesignArtifact,
)

from .models import canonical_fingerprint, filename, fingerprint, identifier


class WorkspaceProjectionContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ProjectionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"


class WorkspaceSnapshotStatus(StrEnum):
    UNAVAILABLE = "UNAVAILABLE"
    PROJECTED = "PROJECTED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"


class WorkspaceArtifactView(WorkspaceProjectionContract):
    artifact_id: str
    artifact_type: str
    status: ProjectionStatus
    filenames: tuple[str, ...]

    @field_validator("artifact_id", "artifact_type", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("filenames", mode="before")
    @classmethod
    def validate_view_filenames(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("filenames must be a tuple")
        return tuple(filename(item) for item in value)


class WorkspaceSnapshot(WorkspaceProjectionContract):
    project_id: str
    artifacts: tuple[WorkspaceArtifactView, ...]
    status: WorkspaceSnapshotStatus
    fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("artifacts", mode="before")
    @classmethod
    def validate_artifacts(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("artifacts must be a tuple")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_snapshot_fp(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify_snapshot(self) -> "WorkspaceSnapshot":
        ids = tuple(item.artifact_id for item in self.artifacts)
        if len(ids) != len(set(ids)):
            raise ValueError("workspace artifact ids must be unique")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("workspace snapshot fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "WorkspaceSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class WorkspaceChangeProposal(WorkspaceProjectionContract):
    proposal_id: str
    project_id: str
    artifact_id: str
    artifact_type: str
    filenames: tuple[str, ...] = Field(max_length=32)
    artifact_fingerprint: str
    status: ProjectionStatus = ProjectionStatus.WAITING_APPROVAL
    requires_approval: bool = True
    fingerprint: str

    @field_validator(
        "proposal_id", "project_id", "artifact_id", "artifact_type", mode="before"
    )
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("filenames", mode="before")
    @classmethod
    def validate_filenames(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("filenames must be a tuple")
        checked = tuple(filename(item) for item in value)
        if len(checked) != len(set(checked)):
            raise ValueError("filenames must be unique")
        return checked

    @field_validator("artifact_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "WorkspaceChangeProposal":
        if not self.requires_approval:
            raise ValueError("workspace projection always requires approval")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("workspace proposal fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "WorkspaceChangeProposal":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


WorkspaceArtifact = FirmwareArtifact | HardwareDesignArtifact


@runtime_checkable
class WorkspaceProjectionPort(Protocol):
    def project(self, artifact: WorkspaceArtifact) -> WorkspaceChangeProposal: ...


def validate_workspace_proposal(value: object) -> WorkspaceChangeProposal:
    if type(value) is not WorkspaceChangeProposal:
        raise TypeError("workspace proposal is invalid")
    return WorkspaceChangeProposal.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


def validate_workspace_snapshot(value: object) -> WorkspaceSnapshot:
    if type(value) is not WorkspaceSnapshot:
        raise TypeError("workspace snapshot is invalid")
    return WorkspaceSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "ProjectionStatus",
    "WorkspaceArtifactView",
    "WorkspaceArtifact",
    "WorkspaceChangeProposal",
    "WorkspaceProjectionPort",
    "WorkspaceSnapshot",
    "WorkspaceSnapshotStatus",
    "validate_workspace_proposal",
    "validate_workspace_snapshot",
]
