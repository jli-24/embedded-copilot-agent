from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

import embedded_copilot.debug_analysis.contracts as debug_contracts
import embedded_copilot.firmware_engineering.contracts as firmware_contracts
import embedded_copilot.firmware_engineering.models as firmware_models

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class FirmwareBuildHttpRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    project_id: str
    firmware_reference: str
    build_profile: str
    approval_reference: str | None = None

    @field_validator("project_id", "firmware_reference", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return firmware_models.identifier(value, field=info.field_name)

    @field_validator("build_profile", mode="before")
    @classmethod
    def validate_profile(cls, value: object) -> str:
        return firmware_models.safe_text(value, field="build_profile", maximum=128)

    @field_validator("approval_reference", mode="before")
    @classmethod
    def validate_approval(cls, value: object) -> str | None:
        return None if value is None else firmware_models.identifier(value, field="approval_reference")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


def _valid_project(value: str) -> bool:
    return bool(_PROJECT.fullmatch(value))


def _result_matches_project(result: firmware_contracts.FirmwareBuildResult, project_id: str) -> bool:
    reference = result.artifact_reference
    return reference == f"firmware:{project_id}" or reference.endswith(f":{project_id}")


@router.get(
    "/api/firmware/v24/{project_id}", response_model=firmware_contracts.FirmwareProjectSnapshot
)
async def get_firmware_snapshot(
    project_id: str, request: Request
) -> firmware_contracts.FirmwareProjectSnapshot | JSONResponse:
    if not _valid_project(project_id):
        return _error("FIRMWARE_REJECTED", 422)
    port = getattr(request.app.state, "firmware_engineering_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("FIRMWARE_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("FIRMWARE_UNAVAILABLE", 503)
    if result is None:
        return _error("FIRMWARE_NOT_FOUND", 404)
    try:
        checked = firmware_contracts.validate_project_snapshot(result)
        if checked.project_id != project_id:
            return _error("FIRMWARE_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("FIRMWARE_REJECTED", 422)


@router.post(
    "/api/firmware/v24/build", response_model=firmware_contracts.FirmwareBuildResult
)
async def build_firmware(
    body: FirmwareBuildHttpRequest, request: Request
) -> firmware_contracts.FirmwareBuildResult | JSONResponse:
    try:
        checked_body = FirmwareBuildHttpRequest.model_validate(
            body.model_dump(mode="python")
        )
        checked = firmware_contracts.FirmwareBuildRequest.create(
            project_id=checked_body.project_id,
            firmware_reference=checked_body.firmware_reference,
            build_profile=checked_body.build_profile,
            approval_reference=checked_body.approval_reference,
        )
    except (ValidationError, TypeError, ValueError):
        return _error("FIRMWARE_REJECTED", 422)
    if checked.approval_reference is None:
        return _error("BUILD_APPROVAL_REQUIRED", 422)
    port = getattr(request.app.state, "firmware_build_port", None)
    method = getattr(port, "build", None) if port is not None else None
    if port is None or not callable(method):
        return _error("BUILD_UNAVAILABLE", 503)
    try:
        result = await _call(method(checked))
        checked_result = firmware_contracts.validate_build_result(result)
    except Exception:
        return _error("BUILD_FAILED", 422)
    if not _result_matches_project(checked_result, checked.project_id):
        return _error("BUILD_FAILED", 422)
    if checked_result.build_status.value == "UNAVAILABLE":
        return _error("BUILD_UNAVAILABLE", 503)
    if checked_result.build_status.value == "FAILED":
        return _error("BUILD_FAILED", 422)
    return checked_result


@router.get(
    "/api/firmware/v24/build/{project_id}", response_model=firmware_contracts.FirmwareBuildResult
)
async def get_firmware_build(
    project_id: str, request: Request
) -> firmware_contracts.FirmwareBuildResult | JSONResponse:
    if not _valid_project(project_id):
        return _error("FIRMWARE_REJECTED", 422)
    port = getattr(request.app.state, "firmware_build_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("BUILD_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("BUILD_UNAVAILABLE", 503)
    if result is None:
        return _error("FIRMWARE_NOT_FOUND", 404)
    try:
        checked = firmware_contracts.validate_build_result(result)
        if not _result_matches_project(checked, project_id):
            return _error("FIRMWARE_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("FIRMWARE_REJECTED", 422)


@router.get(
    "/api/firmware/v24/debug/{project_id}", response_model=debug_contracts.DebugAnalysisSnapshot
)
async def get_firmware_debug(
    project_id: str, request: Request
) -> debug_contracts.DebugAnalysisSnapshot | JSONResponse:
    if not _valid_project(project_id):
        return _error("FIRMWARE_REJECTED", 422)
    port = getattr(request.app.state, "firmware_debug_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("FIRMWARE_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("FIRMWARE_UNAVAILABLE", 503)
    if result is None:
        return _error("FIRMWARE_NOT_FOUND", 404)
    try:
        checked = debug_contracts.validate_analysis_snapshot(result)
        if checked.project_id != project_id:
            return _error("FIRMWARE_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("FIRMWARE_REJECTED", 422)


__all__ = ["FirmwareBuildHttpRequest", "router"]
