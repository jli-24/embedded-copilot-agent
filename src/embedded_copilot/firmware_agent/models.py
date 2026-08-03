"""Immutable contracts for proposal-only ESP-IDF firmware generation."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from embedded_copilot.ai_runtime import (
    EngineeringChatContext,
    KnowledgeEvidenceProjection,
)
from embedded_copilot.engineering_events import EngineeringEvent

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FP = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+|"
    r"(?:password|credential|secret)\s*[:=])",
    re.IGNORECASE,
)
_ALLOWED_PATHS = {
    "CMakeLists.txt",
    "sdkconfig",
    "partitions.csv",
    "main/main.c",
    "main/camera.c",
    "main/wifi.c",
    "main/mqtt.c",
    "main/sensor.c",
}


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


class FirmwarePlatform(StrEnum):
    ESP_IDF = "ESP_IDF"


class FirmwareArtifactType(StrEnum):
    FIRMWARE_SOURCE = "FIRMWARE_SOURCE"
    BUILD_CONFIG = "BUILD_CONFIG"
    PROJECT_STRUCTURE = "PROJECT_STRUCTURE"


class FirmwareSourceFile(_Contract):
    logical_path: str
    purpose: str
    content: str
    fingerprint: str

    @field_validator("logical_path", mode="before")
    @classmethod
    def validate_path(cls, value: object) -> str:
        if type(value) is not str or value not in _ALLOWED_PATHS:
            raise ValueError("logical_path is invalid")
        return value

    @field_validator("purpose", mode="before")
    @classmethod
    def validate_purpose(cls, value: object) -> str:
        if type(value) is not str or _TOKEN.fullmatch(value) is None:
            raise ValueError("purpose is invalid")
        return value

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, value: object) -> str:
        if (
            type(value) is not str
            or not value
            or len(value) > 65_536
            or "\x00" in value
            or _SENSITIVE.search(value)
        ):
            raise ValueError("content is unsafe")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        return _fingerprint_value(value)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> FirmwareSourceFile:
        _check_fingerprint(self)
        return self


class FirmwareArtifactProjection(_Contract):
    artifact_type: FirmwareArtifactType
    reference_ids: tuple[str, ...]
    fingerprint: str

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        if type(value) is not tuple:
            raise ValueError("reference_ids must be a tuple")
        references = tuple(_identifier(item) for item in value)
        if references != tuple(sorted(references)) or len(references) != len(
            set(references)
        ):
            raise ValueError("reference_ids must be sorted and unique")
        return references

    _fingerprint = field_validator("fingerprint", mode="before")(
        _fingerprint_value
    )

    @model_validator(mode="after")
    def validate_fingerprint(self) -> FirmwareArtifactProjection:
        _check_fingerprint(self)
        return self


class FirmwareGenerationRequest(_Contract):
    request_id: str
    context: EngineeringChatContext
    knowledge: tuple[KnowledgeEvidenceProjection, ...]
    platform: FirmwarePlatform
    requested_at: datetime
    fingerprint: str

    _request_id = field_validator("request_id", mode="before")(_identifier)
    _fingerprint = field_validator("fingerprint", mode="before")(
        _fingerprint_value
    )

    @field_validator("context", mode="before")
    @classmethod
    def validate_context_type(cls, value: object) -> object:
        if type(value) is not EngineeringChatContext:
            raise ValueError("typed engineering context is required")
        return value

    @field_validator("knowledge", mode="before")
    @classmethod
    def validate_knowledge(cls, value: object) -> object:
        if type(value) is not tuple or any(
            type(item) is not KnowledgeEvidenceProjection for item in value
        ):
            raise ValueError("knowledge must be a typed tuple")
        keys = tuple(item.evidence_id for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("knowledge must be sorted and unique")
        return value

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> FirmwareGenerationRequest:
        _check_fingerprint(self)
        return self


class FirmwareProposal(_Contract):
    request_id: str
    project_id: str
    platform: FirmwarePlatform
    source_context_fingerprint: str
    source_workspace_fingerprint: str
    knowledge_fingerprints: tuple[str, ...]
    files: tuple[FirmwareSourceFile, ...]
    artifacts: tuple[FirmwareArtifactProjection, ...]
    event: EngineeringEvent
    candidate_semantics: Literal["unverified"] = "unverified"
    review_required: Literal[True] = True
    fingerprint: str

    _request_id = field_validator("request_id", "project_id", mode="before")(
        _identifier
    )

    @field_validator(
        "source_context_fingerprint",
        "source_workspace_fingerprint",
        "fingerprint",
        mode="before",
    )
    @classmethod
    def validate_fingerprints(cls, value: object) -> str:
        return _fingerprint_value(value)

    @field_validator(
        "knowledge_fingerprints", "files", "artifacts", mode="before"
    )
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        if type(value) is not tuple:
            raise ValueError(f"{info.field_name} must be a tuple")
        return value

    @model_validator(mode="after")
    def validate_bindings(self) -> FirmwareProposal:
        file_paths = tuple(item.logical_path for item in self.files)
        if file_paths != tuple(sorted(file_paths)) or len(file_paths) != len(
            set(file_paths)
        ):
            raise ValueError("files must be sorted and unique")
        if not {"CMakeLists.txt", "main/main.c"}.issubset(file_paths):
            raise ValueError("required ESP-IDF proposal files are missing")
        if tuple(item.artifact_type for item in self.artifacts) != tuple(
            FirmwareArtifactType
        ):
            raise ValueError("firmware artifacts are invalid")
        if self.event.reference_id != self.request_id:
            raise ValueError("artifact event binding mismatch")
        _check_fingerprint(self)
        return self


def firmware_source_file_fingerprint(**values: object) -> str:
    return _fingerprint("FirmwareSourceFile", **values)


def firmware_artifact_fingerprint(**values: object) -> str:
    return _fingerprint("FirmwareArtifactProjection", **values)


def firmware_generation_request_fingerprint(**values: object) -> str:
    return _fingerprint("FirmwareGenerationRequest", **values)


def firmware_proposal_fingerprint(**values: object) -> str:
    return _fingerprint("FirmwareProposal", **values)


def canonical_firmware_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _fingerprint(kind: str, **values: object) -> str:
    payload = canonical_firmware_json({"kind": kind, **values}).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _values(model: BaseModel) -> dict[str, object]:
    return {
        name: getattr(model, name)
        for name in type(model).model_fields
        if name != "fingerprint"
    }


def _check_fingerprint(model: BaseModel) -> None:
    expected = _fingerprint(type(model).__name__, **_values(model))
    if model.fingerprint != expected:
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
