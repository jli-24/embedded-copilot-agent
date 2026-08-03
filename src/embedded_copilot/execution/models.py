"""Immutable contracts for controlled ESP-IDF build delegation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.firmware_agent import FirmwarePlatform, FirmwareProposal

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")


def _identifier(value: object) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("identifier is invalid")
    return value


def _fingerprint_value(value: object) -> str:
    if type(value) is not str or _FP.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class BuildApprovalStatus(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BuildStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"


class BuildApproval(_Contract):
    build_id: str
    proposal_fingerprint: str
    status: BuildApprovalStatus
    reviewer: str
    reviewed_at: datetime
    fingerprint: str

    _identifiers = field_validator("build_id", "reviewer", mode="before")(
        _identifier
    )
    _fingerprints = field_validator(
        "proposal_fingerprint", "fingerprint", mode="before"
    )(_fingerprint_value)

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: datetime) -> datetime:
        return _utc(value, "reviewed_at")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> BuildApproval:
        _check_fingerprint(self)
        return self


class BuildExecutionRequest(_Contract):
    build_id: str
    proposal: FirmwareProposal
    approval: BuildApproval
    requested_at: datetime
    fingerprint: str

    _build_id = field_validator("build_id", mode="before")(_identifier)
    _fingerprint = field_validator("fingerprint", mode="before")(
        _fingerprint_value
    )

    @field_validator("proposal", mode="before")
    @classmethod
    def validate_proposal_type(cls, value: object) -> object:
        if type(value) is not FirmwareProposal:
            raise ValueError("typed firmware proposal is required")
        return value

    @field_validator("approval", mode="before")
    @classmethod
    def validate_approval_type(cls, value: object) -> object:
        if type(value) is not BuildApproval:
            raise ValueError("typed build approval is required")
        return value

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value, "requested_at")

    @model_validator(mode="after")
    def validate_bindings(self) -> BuildExecutionRequest:
        if (
            self.approval.build_id != self.build_id
            or self.approval.proposal_fingerprint != self.proposal.fingerprint
        ):
            raise ValueError("approval binding mismatch")
        _check_fingerprint(self)
        return self


class ESPIdfBuildInvocation(_Contract):
    build_id: str
    project_id: str
    proposal_fingerprint: str
    source_file_fingerprints: tuple[str, ...]
    platform: FirmwarePlatform
    requested_at: datetime
    fingerprint: str

    _ids = field_validator("build_id", "project_id", mode="before")(
        _identifier
    )
    _fingerprints = field_validator(
        "proposal_fingerprint", "fingerprint", mode="before"
    )(_fingerprint_value)

    @field_validator("source_file_fingerprints", mode="before")
    @classmethod
    def validate_source_fingerprints(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("source_file_fingerprints must be a tuple")
        fingerprints = tuple(_fingerprint_value(item) for item in value)
        if fingerprints != tuple(sorted(fingerprints)) or len(fingerprints) != len(
            set(fingerprints)
        ):
            raise ValueError("source_file_fingerprints must be sorted and unique")
        return fingerprints

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        return _utc(value, "requested_at")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> ESPIdfBuildInvocation:
        _check_fingerprint(self)
        return self


class HostBuildResult(_Contract):
    status: BuildStatus
    diagnostic_codes: tuple[str, ...]
    symbol_references: tuple[str, ...]
    fingerprint: str

    @field_validator("diagnostic_codes", mode="before")
    @classmethod
    def validate_diagnostic_codes(cls, value: object) -> object:
        return _sorted_tokens(value, "diagnostic_codes", _TOKEN)

    @field_validator("symbol_references", mode="before")
    @classmethod
    def validate_symbol_references(cls, value: object) -> object:
        return _sorted_tokens(value, "symbol_references", _SYMBOL)

    _fingerprint = field_validator("fingerprint", mode="before")(
        _fingerprint_value
    )

    @model_validator(mode="after")
    def validate_contract(self) -> HostBuildResult:
        if self.status in {BuildStatus.UNAVAILABLE, BuildStatus.BLOCKED}:
            raise ValueError("host result status is invalid")
        _check_fingerprint(self)
        return self


class BuildResult(_Contract):
    build_id: str
    project_id: str
    proposal_fingerprint: str
    status: BuildStatus
    diagnostic_codes: tuple[str, ...]
    symbol_references: tuple[str, ...]
    observed_at: datetime
    fingerprint: str

    _ids = field_validator("build_id", "project_id", mode="before")(
        _identifier
    )
    _fingerprints = field_validator(
        "proposal_fingerprint", "fingerprint", mode="before"
    )(_fingerprint_value)

    @field_validator("diagnostic_codes", mode="before")
    @classmethod
    def validate_diagnostic_codes(cls, value: object) -> object:
        return _sorted_tokens(value, "diagnostic_codes", _TOKEN)

    @field_validator("symbol_references", mode="before")
    @classmethod
    def validate_symbol_references(cls, value: object) -> object:
        return _sorted_tokens(value, "symbol_references", _SYMBOL)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value, "observed_at")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> BuildResult:
        _check_fingerprint(self)
        return self


def build_approval_fingerprint(**values: object) -> str:
    return _fingerprint("BuildApproval", **values)


def build_execution_request_fingerprint(**values: object) -> str:
    return _fingerprint("BuildExecutionRequest", **values)


def build_invocation_fingerprint(**values: object) -> str:
    return _fingerprint("ESPIdfBuildInvocation", **values)


def host_build_result_fingerprint(**values: object) -> str:
    return _fingerprint("HostBuildResult", **values)


def build_result_fingerprint(**values: object) -> str:
    return _fingerprint("BuildResult", **values)


def canonical_execution_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _sorted_tokens(value: object, name: str, pattern: re.Pattern[str]) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{name} must be a tuple")
    tokens = tuple(value)
    if any(type(item) is not str or pattern.fullmatch(item) is None for item in tokens):
        raise ValueError(f"{name} is invalid")
    if tokens != tuple(sorted(tokens)) or len(tokens) != len(set(tokens)):
        raise ValueError(f"{name} must be sorted and unique")
    return tokens


def _fingerprint(kind: str, **values: object) -> str:
    payload = canonical_execution_json({"kind": kind, **values}).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _check_fingerprint(model: BaseModel) -> None:
    values = {
        name: getattr(model, name)
        for name in type(model).model_fields
        if name != "fingerprint"
    }
    if model.fingerprint != _fingerprint(type(model).__name__, **values):
        raise ValueError(f"{type(model).__name__} fingerprint mismatch")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
