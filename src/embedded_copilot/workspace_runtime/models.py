from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SENSITIVE_PATH = re.compile(
    r"(?:^|[._-])(?:secrets?|credentials?|passwords?|tokens?|api[_-]?keys?)"
    r"(?:[._-]|$)",
    re.IGNORECASE,
)
_WINDOWS_DEVICE_NAMES = {
    "aux",
    "clock$",
    "con",
    "nul",
    "prn",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value.strip()):
        raise ValueError(f"{field} is invalid")
    return value.strip()


def safe_relative_path(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("relative path is invalid")
    path = value.replace("\\", "/")
    parts = tuple(path.split("/"))
    filename = parts[-1].casefold() if parts else ""
    if (
        not path
        or len(path) > 255
        or "\x00" in path
        or value != value.strip()
        or path.startswith("/")
        or re.match(r"^[A-Za-z]:", path) is not None
        or any(part in {"", ".", ".."} for part in parts)
        or any(
            part != part.strip()
            or part.endswith(".")
            or ":" in part
            or any(ord(character) < 32 for character in part)
            or part.split(".", 1)[0].casefold() in _WINDOWS_DEVICE_NAMES
            for part in parts
        )
        or any(part.casefold() == ".git" for part in parts)
        or filename == ".env"
        or filename.startswith(".env.")
        or _SENSITIVE_PATH.search(filename) is not None
    ):
        raise ValueError("relative path is invalid")
    return path


class _WorkspaceContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class WorkspaceLanguage(StrEnum):
    C = "C"
    CPP = "CPP"
    PYTHON = "PYTHON"
    TEXT = "TEXT"
    UNKNOWN = "UNKNOWN"


class ChangeOperation(StrEnum):
    MODIFY = "MODIFY"


class ApprovalStatus(StrEnum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"


class ValidationStatus(StrEnum):
    WAITING_APPROVAL = "WAITING_APPROVAL"
    WORKSPACE_CHANGED = "WORKSPACE_CHANGED"
    REJECTED = "REJECTED"


class ApplyStatus(StrEnum):
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class WorkspaceInspectionRequest(_WorkspaceContract):
    workspace_id: str
    relative_paths: tuple[str, ...] = Field(min_length=1, max_length=128)

    @field_validator("workspace_id", mode="before")
    @classmethod
    def validate_workspace_id(cls, value: object) -> str:
        return _identifier(value, field="workspace_id")

    @field_validator("relative_paths", mode="before")
    @classmethod
    def validate_paths(cls, value: object) -> object:
        if not isinstance(value, (tuple, list)):
            return value
        paths = tuple(safe_relative_path(item) for item in copy.deepcopy(value))
        if len({item.casefold() for item in paths}) != len(paths):
            raise ValueError("relative paths must be unique")
        return paths


class WorkspaceFileSummary(_WorkspaceContract):
    relative_path: str
    sha256: str
    size: int = Field(ge=0, le=1024 * 1024)
    language: WorkspaceLanguage

    @field_validator("relative_path", mode="before")
    @classmethod
    def validate_path(cls, value: object) -> str:
        return safe_relative_path(value)

    @field_validator("sha256", mode="before")
    @classmethod
    def validate_sha256(cls, value: object) -> str:
        if not isinstance(value, str) or not _SHA256.fullmatch(value.strip()):
            raise ValueError("sha256 is invalid")
        return value.strip()


class FrozenWorkspaceSnapshot(_WorkspaceContract):
    schema_version: Literal["1.0"] = "1.0"
    workspace_id: str
    files: tuple[WorkspaceFileSummary, ...] = Field(min_length=1, max_length=128)
    snapshot_fingerprint: str

    @field_validator("workspace_id", mode="before")
    @classmethod
    def validate_workspace_id(cls, value: object) -> str:
        return _identifier(value, field="workspace_id")

    @field_validator("snapshot_fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
            raise ValueError("snapshot_fingerprint is invalid")
        return value.strip()

    @model_validator(mode="after")
    def validate_snapshot(self) -> "FrozenWorkspaceSnapshot":
        paths = tuple(item.relative_path.casefold() for item in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("snapshot files must be sorted and unique")
        from embedded_copilot.workspace_runtime.snapshot import snapshot_fingerprint

        expected = snapshot_fingerprint(
            schema_version=self.schema_version,
            workspace_id=self.workspace_id,
            files=self.files,
        )
        if self.snapshot_fingerprint != expected:
            raise ValueError("snapshot_fingerprint does not match snapshot")
        return self


class ChangeProposal(_WorkspaceContract):
    proposal_id: str
    workspace_snapshot_id: str
    target_files: tuple[str, ...] = Field(min_length=1, max_length=32)
    operation_type: Literal[ChangeOperation.MODIFY] = ChangeOperation.MODIFY
    diff: str = Field(min_length=1, max_length=1024 * 1024)
    reason: str = Field(min_length=1, max_length=512)
    created_by: str

    @field_validator("proposal_id", "created_by", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("workspace_snapshot_id", mode="before")
    @classmethod
    def validate_snapshot_id(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
            raise ValueError("workspace_snapshot_id is invalid")
        return value.strip()

    @field_validator("target_files", mode="before")
    @classmethod
    def validate_targets(cls, value: object) -> object:
        if not isinstance(value, (tuple, list)):
            return value
        paths = tuple(safe_relative_path(item) for item in copy.deepcopy(value))
        if len({item.casefold() for item in paths}) != len(paths):
            raise ValueError("target files must be unique")
        return paths

    @field_validator("diff", "reason", mode="before")
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        if not isinstance(value, str) or "\x00" in value or not value.strip():
            raise ValueError(f"{info.field_name} is invalid")
        return copy.deepcopy(value)


class ValidationResult(_WorkspaceContract):
    status: ValidationStatus
    proposal_id: str
    workspace_id: str
    workspace_snapshot_id: str
    target_files: tuple[str, ...]
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ValidationResult":
        if self.status is ValidationStatus.WAITING_APPROVAL:
            if self.error_code is not None:
                raise ValueError("waiting validation cannot contain an error")
        elif self.error_code is None:
            raise ValueError("rejected validation requires an error")
        return self


class ApprovalContext(_WorkspaceContract):
    proposal_id: str
    workspace_id: str
    workspace_snapshot_id: str
    target_files: tuple[str, ...] = Field(min_length=1, max_length=32)
    status: ApprovalStatus
    approved_by: str
    approved_at: datetime

    @field_validator("proposal_id", "workspace_id", "approved_by", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("workspace_snapshot_id", mode="before")
    @classmethod
    def validate_snapshot_id(cls, value: object) -> str:
        return ChangeProposal.validate_snapshot_id(value)

    @field_validator("target_files", mode="before")
    @classmethod
    def validate_targets(cls, value: object) -> object:
        return ChangeProposal.validate_targets(value)

    @field_validator("approved_at")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at must be timezone aware")
        return value.astimezone(timezone.utc)


class WorkspaceAuditEvent(_WorkspaceContract):
    event_type: Literal["APPLIED"] = "APPLIED"
    proposal_id: str
    workspace_id: str
    files: tuple[str, ...] = Field(min_length=1, max_length=32)
    approved_by: str
    timestamp: datetime


class ApplyResult(_WorkspaceContract):
    status: ApplyStatus
    proposal_id: str
    workspace_id: str
    target_files: tuple[str, ...]
    audit_event: WorkspaceAuditEvent | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "ApplyResult":
        if self.status is ApplyStatus.APPLIED:
            if self.audit_event is None or self.error_code is not None:
                raise ValueError("applied result requires only an audit event")
        elif self.audit_event is not None or self.error_code is None:
            raise ValueError("rejected result requires only an error")
        return self
