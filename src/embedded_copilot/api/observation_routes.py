from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import embedded_copilot.hardware_observation.contracts as observation_contracts

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@router.get(
    "/api/validation/observation/{project_id}",
    response_model=observation_contracts.ObservationSnapshot,
)
async def get_observation(
    project_id: str, request: Request
) -> observation_contracts.ObservationSnapshot | JSONResponse:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", project_id):
        return _error("OBSERVATION_SNAPSHOT_REJECTED", 422)
    port = getattr(request.app.state, "observation_snapshot_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("OBSERVATION_UNAVAILABLE", 503)
    try:
        result = port.get_snapshot(project_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return _error("OBSERVATION_UNAVAILABLE", 503)
    if result is None:
        return _error("OBSERVATION_NOT_FOUND", 404)
    try:
        return observation_contracts.validate_observation_snapshot(result)
    except (ValidationError, TypeError, ValueError):
        return _error("OBSERVATION_SNAPSHOT_REJECTED", 422)
