from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from embedded_copilot.hil_validation.contracts import (
    DeviceObservationSnapshot,
    HILValidationRequest,
    HILValidationResult,
    HardwareCapabilitySnapshot,
    validate_capability_snapshot,
    validate_observation_snapshot,
    validate_result,
)
from embedded_copilot.hil_validation.exceptions import (
    DeviceUnavailable,
    HILApprovalRequired,
    HILRejected,
    HILUnavailable,
    ObservationUnavailable,
)
from embedded_copilot.hil_validation.models import identifier

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class HILValidationBody(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    project_id: str
    device_reference: str
    firmware_reference: str
    approval_reference: str | None = None

    @field_validator(
        "project_id", "device_reference", "firmware_reference", mode="before"
    )
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("approval_reference", mode="before")
    @classmethod
    def validate_approval(cls, value: object) -> str | None:
        return None if value is None else identifier(value, field="approval_reference")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


def _valid_project(project_id: str) -> bool:
    return bool(_PROJECT.fullmatch(project_id))


@router.get(
    "/api/hil/v25/device/{project_id}", response_model=HardwareCapabilitySnapshot
)
async def get_hardware_capability(
    project_id: str, request: Request
) -> HardwareCapabilitySnapshot | JSONResponse:
    if not _valid_project(project_id):
        return _error("HIL_REJECTED", 422)
    port = getattr(request.app.state, "hardware_capability_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "get_capability", None)
    if port is None or not callable(method):
        return _error("DEVICE_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except DeviceUnavailable:
        return _error("DEVICE_UNAVAILABLE", 503)
    except Exception:
        return _error("DEVICE_UNAVAILABLE", 503)
    if result is None:
        return _error("HIL_RESULT_NOT_FOUND", 404)
    try:
        checked = validate_capability_snapshot(result)
        if checked.project_id != project_id:
            return _error("HIL_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("HIL_REJECTED", 422)


@router.get(
    "/api/hil/v25/observation/{project_id}", response_model=DeviceObservationSnapshot
)
async def get_device_observation(
    project_id: str, request: Request
) -> DeviceObservationSnapshot | JSONResponse:
    if not _valid_project(project_id):
        return _error("HIL_REJECTED", 422)
    port = getattr(request.app.state, "device_observation_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "observe_device", None)
    if port is None or not callable(method):
        return _error("OBSERVATION_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except ObservationUnavailable:
        return _error("OBSERVATION_UNAVAILABLE", 503)
    except Exception:
        return _error("OBSERVATION_UNAVAILABLE", 503)
    if result is None:
        return _error("HIL_RESULT_NOT_FOUND", 404)
    try:
        checked = validate_observation_snapshot(result)
        if checked.project_id != project_id:
            return _error("HIL_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("HIL_REJECTED", 422)


@router.post(
    "/api/hil/v25/validate", response_model=HILValidationResult
)
async def validate_hil(
    body: HILValidationBody, request: Request
) -> HILValidationResult | JSONResponse:
    try:
        checked = HILValidationRequest.create(
            project_id=body.project_id,
            device_reference=body.device_reference,
            firmware_reference=body.firmware_reference,
            approval_reference=body.approval_reference,
        )
    except (ValidationError, TypeError, ValueError):
        return _error("HIL_REJECTED", 422)
    if checked.approval_reference is None:
        return _error("HIL_APPROVAL_REQUIRED", 422)
    port = getattr(request.app.state, "hil_validation_port", None)
    method = getattr(port, "validate", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "validate_firmware", None)
    if port is None or not callable(method):
        return _error("HIL_FAILED", 503)
    try:
        result = await _call(method(checked))
        checked_result = validate_result(result)
        if (
            checked_result.project_id != checked.project_id
            or checked_result.device_reference != checked.device_reference
            or checked_result.firmware_reference != checked.firmware_reference
        ):
            return _error("HIL_REJECTED", 422)
        if checked_result.overall_status.value == "UNAVAILABLE":
            return _error("DEVICE_UNAVAILABLE", 503)
        if checked_result.overall_status.value in {"FAILED", "BLOCKED"}:
            return _error("HIL_FAILED", 422)
        return checked_result
    except HILApprovalRequired:
        return _error("HIL_APPROVAL_REQUIRED", 422)
    except DeviceUnavailable:
        return _error("DEVICE_UNAVAILABLE", 503)
    except HILRejected:
        return _error("HIL_REJECTED", 422)
    except (HILUnavailable, ObservationUnavailable):
        return _error("HIL_FAILED", 503)
    except (ValidationError, TypeError, ValueError):
        return _error("HIL_REJECTED", 422)
    except Exception:
        return _error("HIL_FAILED", 422)


@router.get(
    "/api/hil/v25/result/{project_id}", response_model=HILValidationResult
)
async def get_hil_result(
    project_id: str, request: Request
) -> HILValidationResult | JSONResponse:
    if not _valid_project(project_id):
        return _error("HIL_REJECTED", 422)
    port = getattr(request.app.state, "hil_validation_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("HIL_FAILED", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("HIL_FAILED", 503)
    if result is None:
        return _error("HIL_RESULT_NOT_FOUND", 404)
    try:
        checked = validate_result(result)
        if checked.project_id != project_id:
            return _error("HIL_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("HIL_REJECTED", 422)


__all__ = ["HILValidationBody", "router"]
