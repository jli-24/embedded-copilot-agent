from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from embedded_copilot.device_runtime.contracts import (
    DeviceSnapshot,
    validate_device_snapshot,
)

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@router.get("/api/device/{project_id}", response_model=DeviceSnapshot)
async def get_device(
    project_id: str, request: Request
) -> DeviceSnapshot | JSONResponse:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", project_id):
        return _error("DEVICE_SNAPSHOT_REJECTED", 422)
    port = getattr(request.app.state, "device_snapshot_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("DEVICE_UNAVAILABLE", 503)
    try:
        result = port.get_snapshot(project_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return _error("DEVICE_UNAVAILABLE", 503)
    if result is None:
        return _error("DEVICE_NOT_FOUND", 404)
    try:
        checked = validate_device_snapshot(result)
        if checked.project_id != project_id:
            return _error("DEVICE_SNAPSHOT_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("DEVICE_SNAPSHOT_REJECTED", 422)
