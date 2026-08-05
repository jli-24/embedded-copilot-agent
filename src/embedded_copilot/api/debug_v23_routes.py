from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import embedded_copilot.debug_analysis.contracts as debug_contracts

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


@router.get(
    "/api/debug/v23/{project_id}", response_model=debug_contracts.DebugAnalysisSnapshot
)
async def get_debug_analysis(
    project_id: str, request: Request
) -> debug_contracts.DebugAnalysisSnapshot | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("DEBUG_REJECTED", 422)
    port = getattr(request.app.state, "debug_analysis_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("DEBUG_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("DEBUG_UNAVAILABLE", 503)
    if result is None:
        return _error("DEBUG_NOT_FOUND", 404)
    try:
        checked = debug_contracts.validate_analysis_snapshot(result)
        if checked.project_id != project_id:
            return _error("DEBUG_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("DEBUG_REJECTED", 422)


__all__ = ["router"]
