from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

import embedded_copilot.hardware_observation.contracts as observation_contracts
from embedded_copilot.tool_adapter.contracts import (
    ToolCapabilitySnapshot,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolType,
    validate_capability_snapshot,
    validate_execution_result,
)
from embedded_copilot.tool_adapter.exceptions import (
    BuildApprovalRequired,
    FlashApprovalRequired,
    FlashFailed,
    FlashUnavailable,
    ObservationUnavailable,
    ToolUnavailable,
)

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


class _ExecutionBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)

    @staticmethod
    def _reference(value: object, field: str) -> str:
        if not isinstance(value, str) or not _REFERENCE.fullmatch(value):
            raise ValueError(f"{field} is invalid")
        return value


class BuildBody(_ExecutionBody):
    artifact_reference: str
    workspace_reference: str
    approval_reference: str | None = None

    @field_validator("artifact_reference", "workspace_reference", mode="before")
    @classmethod
    def validate_required(cls, value: object, info) -> str:
        return cls._reference(value, info.field_name)

    @field_validator("approval_reference", mode="before")
    @classmethod
    def validate_approval(cls, value: object) -> str | None:
        return None if value is None else cls._reference(value, "approval_reference")


class FlashBody(_ExecutionBody):
    firmware_reference: str
    device_reference: str
    approval_reference: str | None = None

    @field_validator("firmware_reference", "device_reference", mode="before")
    @classmethod
    def validate_required(cls, value: object, info) -> str:
        return cls._reference(value, info.field_name)

    @field_validator("approval_reference", mode="before")
    @classmethod
    def validate_approval(cls, value: object) -> str | None:
        return None if value is None else cls._reference(value, "approval_reference")


async def _call(value):
    result = value
    if inspect.isawaitable(result):
        result = await result
    return result


@router.get(
    "/api/toolchain/v21/status/{project_id}", response_model=ToolCapabilitySnapshot
)
async def get_tool_status(
    project_id: str, request: Request
) -> ToolCapabilitySnapshot | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("TOOL_STATUS_REJECTED", 422)
    port = getattr(request.app.state, "tool_adapter_status_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "get_capabilities", None)
    if port is None or not callable(method):
        return _error("TOOL_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("TOOL_UNAVAILABLE", 503)
    if result is None:
        return _error("TOOL_STATUS_NOT_FOUND", 404)
    try:
        return validate_capability_snapshot(result)
    except (ValidationError, TypeError, ValueError):
        return _error("TOOL_STATUS_REJECTED", 422)


@router.post("/api/toolchain/v21/build", response_model=ToolExecutionResult)
async def build_tool(
    request: Request, body: BuildBody
) -> ToolExecutionResult | JSONResponse:
    try:
        execution = ToolExecutionRequest.create(
            tool_type=ToolType.ESP_IDF,
            operation="build",
            workspace_reference=body.workspace_reference,
            artifact_reference=body.artifact_reference,
            approval_reference=body.approval_reference,
        )
    except (ValidationError, TypeError, ValueError):
        return _error("TOOL_EXECUTION_REJECTED", 422)
    if execution.approval_reference is None:
        return _error("BUILD_APPROVAL_REQUIRED", 422)
    port = getattr(request.app.state, "tool_adapter_build_port", None)
    method = getattr(port, "build", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "execute", None)
    if port is None or not callable(method):
        return _error("TOOL_UNAVAILABLE", 503)
    try:
        result = await _call(method(execution))
    except BuildApprovalRequired:
        return _error("BUILD_APPROVAL_REQUIRED", 422)
    except ToolUnavailable:
        return _error("TOOL_UNAVAILABLE", 503)
    except Exception:
        return _error("TOOL_EXECUTION_FAILED", 422)
    try:
        checked = validate_execution_result(result)
        if checked.status.value == "UNAVAILABLE":
            return _error("TOOL_UNAVAILABLE", 503)
        if checked.status.value == "FAILED":
            return _error("TOOL_EXECUTION_FAILED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("TOOL_EXECUTION_REJECTED", 422)


@router.post("/api/toolchain/v21/flash", response_model=ToolExecutionResult)
async def flash_tool(
    request: Request, body: FlashBody
) -> ToolExecutionResult | JSONResponse:
    try:
        execution = ToolExecutionRequest.create(
            tool_type=ToolType.OPENOCD,
            operation="flash",
            artifact_reference=body.firmware_reference,
            workspace_reference=body.device_reference,
            approval_reference=body.approval_reference,
        )
    except (ValidationError, TypeError, ValueError):
        return _error("TOOL_EXECUTION_REJECTED", 422)
    if execution.approval_reference is None:
        return _error("FLASH_APPROVAL_REQUIRED", 422)
    port = getattr(request.app.state, "tool_adapter_flash_port", None)
    method = getattr(port, "flash", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "execute", None)
    if port is None or not callable(method):
        return _error("FLASH_UNAVAILABLE", 503)
    try:
        result = await _call(method(execution))
    except FlashApprovalRequired:
        return _error("FLASH_APPROVAL_REQUIRED", 422)
    except FlashUnavailable:
        return _error("FLASH_UNAVAILABLE", 503)
    except FlashFailed:
        return _error("FLASH_FAILED", 422)
    except Exception:
        return _error("FLASH_FAILED", 422)
    try:
        checked = validate_execution_result(result)
        if checked.status.value == "UNAVAILABLE":
            return _error("FLASH_UNAVAILABLE", 503)
        if checked.status.value == "FAILED":
            return _error("FLASH_FAILED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("FLASH_FAILED", 422)


@router.get(
    "/api/toolchain/v21/device/{project_id}",
    response_model=observation_contracts.ObservationSnapshot,
)
async def get_tool_device(
    project_id: str, request: Request
) -> observation_contracts.ObservationSnapshot | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("OBSERVATION_REJECTED", 422)
    port = getattr(request.app.state, "tool_adapter_device_port", None)
    method = getattr(port, "get_device", None) if port is not None else None
    if method is None and port is not None:
        method = getattr(port, "get_snapshot", None)
    if port is None or not callable(method):
        return _error("OBSERVATION_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except ObservationUnavailable:
        return _error("OBSERVATION_UNAVAILABLE", 503)
    except Exception:
        return _error("OBSERVATION_UNAVAILABLE", 503)
    if result is None:
        return _error("OBSERVATION_NOT_FOUND", 404)
    try:
        checked = observation_contracts.validate_observation_snapshot(result)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("OBSERVATION_REJECTED", 422)


__all__ = ["router"]
