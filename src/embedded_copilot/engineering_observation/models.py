"""Safe, immutable projections derived from controlled build results."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
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


class EngineeringObservationType(StrEnum):
    BUILD_SUCCESS = "BUILD_SUCCESS"
    BUILD_FAILED = "BUILD_FAILED"
    COMPILER_ERROR = "COMPILER_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"


class DebugCategory(StrEnum):
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    COMPILER_ERROR = "COMPILER_ERROR"
    UNKNOWN = "UNKNOWN"


class EngineeringObservation(_Contract):
    build_id: str
    project_id: str
    source_result_fingerprint: str
    observation_type: EngineeringObservationType
    diagnostic_codes: tuple[str, ...]
    fingerprint: str

    _ids = field_validator("build_id", "project_id", mode="before")(
        _identifier
    )
    _fps = field_validator(
        "source_result_fingerprint", "fingerprint", mode="before"
    )(_fingerprint_value)

    @field_validator("diagnostic_codes", mode="before")
    @classmethod
    def validate_codes(cls, value: object) -> object:
        return _tokens(value, "diagnostic_codes")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringObservation:
        _check_fingerprint(self)
        return self


class RepairProposal(_Contract):
    source_result_fingerprint: str
    category: DebugCategory
    suggestion_codes: tuple[str, ...]
    apply_available: Literal[False] = False
    fingerprint: str

    _fps = field_validator(
        "source_result_fingerprint", "fingerprint", mode="before"
    )(_fingerprint_value)

    @field_validator("suggestion_codes", mode="before")
    @classmethod
    def validate_codes(cls, value: object) -> object:
        return _tokens(value, "suggestion_codes")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> RepairProposal:
        _check_fingerprint(self)
        return self


class BuildObservationProjection(_Contract):
    observation: EngineeringObservation
    repair: RepairProposal
    fingerprint: str

    _fingerprint = field_validator("fingerprint", mode="before")(
        _fingerprint_value
    )

    @model_validator(mode="after")
    def validate_bindings(self) -> BuildObservationProjection:
        if (
            self.observation.source_result_fingerprint
            != self.repair.source_result_fingerprint
        ):
            raise ValueError("observation binding mismatch")
        _check_fingerprint(self)
        return self


def engineering_observation_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringObservation", **values)


def repair_proposal_fingerprint(**values: object) -> str:
    return _fingerprint("RepairProposal", **values)


def build_observation_projection_fingerprint(**values: object) -> str:
    return _fingerprint("BuildObservationProjection", **values)


def canonical_observation_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _tokens(value: object, name: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{name} must be a tuple")
    tokens = tuple(value)
    if any(type(item) is not str or _TOKEN.fullmatch(item) is None for item in tokens):
        raise ValueError(f"{name} is invalid")
    if tokens != tuple(sorted(tokens)) or len(tokens) != len(set(tokens)):
        raise ValueError(f"{name} must be sorted and unique")
    return tokens


def _fingerprint(kind: str, **values: object) -> str:
    payload = canonical_observation_json({"kind": kind, **values}).encode("utf-8")
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
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
