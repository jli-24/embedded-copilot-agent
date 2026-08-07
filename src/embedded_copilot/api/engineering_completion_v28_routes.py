from __future__ import annotations

import copy
import importlib
import inspect
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

_contracts = importlib.import_module(
    "embedded_copilot." + "engineering_completion.contracts"
)
_models = importlib.import_module("embedded_copilot." + "engineering_completion.models")
EngineeringCompletionSnapshot = _contracts.EngineeringCompletionSnapshot
ValidationResult = _contracts.ValidationResult
validate_completion_snapshot = _contracts.validate_completion_snapshot
ValidationStatus = _contracts.ValidationStatus
ValidationReason = _contracts.ValidationReason
EngineeringConfidence = _contracts.EngineeringConfidence
EngineeringReviewCategory = _contracts.EngineeringReviewCategory
EngineeringReviewStatus = _contracts.EngineeringReviewStatus
fingerprint = _models.fingerprint
identifier = _models.identifier

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class EngineeringCompletionValidationBody(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    project_id: str
    completion_snapshot: object
    context_fingerprint: str

    @field_validator("project_id", mode="before")
    @classmethod
    def validate_project(cls, value: object) -> str:
        return identifier(value, field="project_id")

    @field_validator("context_fingerprint", mode="before")
    @classmethod
    def validate_context(cls, value: object) -> str:
        return fingerprint(value, field="context_fingerprint")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _valid_project(project_id: str) -> bool:
    return bool(_PROJECT.fullmatch(project_id))


def _tuplify(value: object) -> object:
    if isinstance(value, list):
        return tuple(_tuplify(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuplify(item) for key, item in value.items()}
    return value


def _coerce_enums(value: object, field: str | None = None) -> object:
    if isinstance(value, dict):
        return {key: _coerce_enums(item, key) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_coerce_enums(item, field) for item in value)
    if field == "confidence" and isinstance(value, str):
        return EngineeringConfidence(value)
    if field == "category" and isinstance(value, str):
        return EngineeringReviewCategory(value)
    if field == "status" and isinstance(value, str):
        return EngineeringReviewStatus(value)
    return value


def _parse_snapshot(value: object) -> EngineeringCompletionSnapshot:
    if type(value) is EngineeringCompletionSnapshot:
        return validate_completion_snapshot(value)
    if not isinstance(value, dict):
        raise TypeError("completion snapshot is invalid")
    normalized = _coerce_enums(_tuplify(copy.deepcopy(value)))
    return validate_completion_snapshot(
        EngineeringCompletionSnapshot.model_validate(normalized)
    )


@router.get(
    "/api/engineering/v28/{project_id}",
    response_model=EngineeringCompletionSnapshot,
)
async def get_engineering_completion(
    project_id: str, request: Request
) -> EngineeringCompletionSnapshot | JSONResponse:
    if not _valid_project(project_id):
        return _error("QUERY_REJECTED", 422)
    port = getattr(request.app.state, "engineering_completion_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("ENGINEERING_COMPLETION_UNAVAILABLE", 503)
    try:
        value = await _call(method(project_id))
    except Exception:  # noqa: BLE001 - adapter details are intentionally sanitized
        return _error("ENGINEERING_COMPLETION_UNAVAILABLE", 503)
    if value is None:
        return _error("ENGINEERING_COMPLETION_NOT_FOUND", 404)
    try:
        checked = validate_completion_snapshot(value)
        if checked.project_id != project_id:
            return _error("QUERY_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("QUERY_REJECTED", 422)


@router.post(
    "/api/engineering/v28/validate",
    response_model=ValidationResult,
)
async def validate_engineering_completion(
    body: EngineeringCompletionValidationBody,
) -> ValidationResult | JSONResponse:
    try:
        checked_body = EngineeringCompletionValidationBody.model_validate(
            body.model_dump(mode="python")
        )
        checked_snapshot = _parse_snapshot(checked_body.completion_snapshot)
    except (ValidationError, TypeError, ValueError):
        return _error("QUERY_REJECTED", 422)
    if checked_snapshot.project_id != checked_body.project_id:
        return _error("QUERY_REJECTED", 422)
    if checked_body.context_fingerprint != checked_snapshot.fingerprint:
        return _error("QUERY_REJECTED", 422)
    return ValidationResult.create(
        project_id=checked_body.project_id,
        snapshot_fingerprint=checked_snapshot.fingerprint,
        context_fingerprint=checked_body.context_fingerprint,
        status=ValidationStatus.VALID,
        summary="Engineering completion projection is valid.",
        reason=None,
    )


__all__ = ["EngineeringCompletionValidationBody", "router"]
