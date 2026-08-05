from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import embedded_copilot.hardware_design.contracts as design_contracts
import embedded_copilot.hardware_review.contracts as review_contracts

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    result = value
    if inspect.isawaitable(result):
        result = await result
    return result


@router.get(
    "/api/hardware/v22/design/{project_id}",
    response_model=design_contracts.UnifiedHardwareModel,
)
async def get_hardware_design(
    project_id: str, request: Request
) -> design_contracts.UnifiedHardwareModel | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("DESIGN_REJECTED", 422)
    port = getattr(request.app.state, "hardware_design_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("HARDWARE_UNAVAILABLE", 503)
    try:
        result = await _call(port.get_snapshot(project_id))
    except Exception:
        return _error("HARDWARE_UNAVAILABLE", 503)
    if result is None:
        return _error("DESIGN_NOT_FOUND", 404)
    try:
        checked = design_contracts.validate_unified_hardware_model(result)
        if checked.project_id != project_id:
            return _error("DESIGN_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("DESIGN_REJECTED", 422)


@router.get(
    "/api/hardware/v22/review/{project_id}",
    response_model=tuple[review_contracts.HardwareReviewProposal, ...],
)
async def get_hardware_review(
    project_id: str, request: Request
) -> tuple[review_contracts.HardwareReviewProposal, ...] | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("REVIEW_UNAVAILABLE", 503)
    port = getattr(request.app.state, "hardware_review_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("REVIEW_UNAVAILABLE", 503)
    try:
        result = await _call(port.get_snapshot(project_id))
    except Exception:
        return _error("REVIEW_UNAVAILABLE", 503)
    if result is None:
        return _error("REVIEW_UNAVAILABLE", 503)
    try:
        checked = review_contracts.validate_review_proposals(result)
        if any(item.project_id != project_id for item in checked):
            return _error("REVIEW_UNAVAILABLE", 503)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("REVIEW_UNAVAILABLE", 503)


__all__ = ["router"]
