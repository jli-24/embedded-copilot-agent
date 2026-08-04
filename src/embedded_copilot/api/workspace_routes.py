from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from embedded_copilot.workspace_projection.contracts import (
    WorkspaceSnapshot,
    validate_workspace_snapshot,
)

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@router.get("/api/workspace/{project_id}", response_model=WorkspaceSnapshot)
async def get_workspace(
    project_id: str, request: Request
) -> WorkspaceSnapshot | JSONResponse:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", project_id):
        return _error("WORKSPACE_SNAPSHOT_REJECTED", 422)
    port = getattr(request.app.state, "workspace_snapshot_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("WORKSPACE_UNAVAILABLE", 503)
    try:
        result = port.get_snapshot(project_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return _error("WORKSPACE_UNAVAILABLE", 503)
    if result is None:
        return _error("WORKSPACE_PROJECT_NOT_FOUND", 404)
    try:
        return validate_workspace_snapshot(result)
    except (ValidationError, TypeError, ValueError):
        return _error("WORKSPACE_SNAPSHOT_REJECTED", 422)
