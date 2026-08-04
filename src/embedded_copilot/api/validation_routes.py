from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from embedded_copilot.toolchain.exceptions import (
    FlashApprovalRequired,
    FlashCapabilityRequired,
    FlashFailed,
    FlashUnavailable,
)
from embedded_copilot.toolchain.flash import (
    FlashRequest,
    FlashResult,
    validate_flash_result,
)
from embedded_copilot.validation_loop.contracts import (
    ValidationSnapshot,
    validate_validation_snapshot,
)

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


class FlashBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    firmware_reference: str
    device_reference: str
    approval_reference: str | None = None
    capability_reference: str | None = None

    @field_validator(
        "firmware_reference",
        "device_reference",
        "approval_reference",
        "capability_reference",
        mode="before",
    )
    @classmethod
    def validate_text(cls, value: object) -> object:
        if value is not None and (
            not isinstance(value, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value)
        ):
            raise ValueError("reference is invalid")
        return value


@router.post("/api/validation/flash", response_model=FlashResult)
async def flash(request: Request, body: FlashBody) -> FlashResult | JSONResponse:
    port = getattr(request.app.state, "flash_port", None)
    if port is None or not callable(getattr(port, "flash", None)):
        return _error("FLASH_UNAVAILABLE", 503)
    try:
        result = port.flash(FlashRequest.model_validate(body.model_dump(mode="python")))
        if inspect.isawaitable(result):
            result = await result
    except FlashCapabilityRequired:
        return _error("FLASH_CAPABILITY_REQUIRED", 422)
    except FlashApprovalRequired:
        return _error("FLASH_APPROVAL_REQUIRED", 422)
    except FlashFailed:
        return _error("FLASH_FAILED", 422)
    except FlashUnavailable:
        return _error("FLASH_UNAVAILABLE", 503)
    except Exception:
        return _error("FLASH_FAILED", 422)
    try:
        return validate_flash_result(result)
    except (ValidationError, TypeError, ValueError):
        return _error("FLASH_FAILED", 422)


@router.get("/api/validation/loop/{project_id}", response_model=ValidationSnapshot)
async def get_validation_loop(
    project_id: str, request: Request
) -> ValidationSnapshot | JSONResponse:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", project_id):
        return _error("VALIDATION_SNAPSHOT_REJECTED", 422)
    port = getattr(request.app.state, "validation_loop_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("VALIDATION_UNAVAILABLE", 503)
    try:
        result = port.get_snapshot(project_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return _error("VALIDATION_UNAVAILABLE", 503)
    if result is None:
        return _error("VALIDATION_PROJECT_NOT_FOUND", 404)
    try:
        return validate_validation_snapshot(result)
    except (ValidationError, TypeError, ValueError):
        return _error("VALIDATION_SNAPSHOT_REJECTED", 422)
