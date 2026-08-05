from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from embedded_copilot.digital_twin.contracts import (
    DigitalTwinSnapshot,
    validate_snapshot,
)
from embedded_copilot.engineering_optimization.contracts import (
    OptimizationAnalysis,
    OptimizationApprovalRequest,
    OptimizationFinding,
    validate_analysis,
    validate_finding,
)

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_FINDING = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


@router.get("/api/digital-twin/v26/{project_id}", response_model=DigitalTwinSnapshot)
async def get_digital_twin(
    project_id: str, request: Request
) -> DigitalTwinSnapshot | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("DIGITAL_TWIN_REJECTED", 422)
    port = getattr(request.app.state, "digital_twin_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("DIGITAL_TWIN_UNAVAILABLE", 503)
    try:
        value = await _call(method(project_id))
    except Exception:  # noqa: BLE001 - external adapter errors are intentionally sanitized
        return _error("DIGITAL_TWIN_UNAVAILABLE", 503)
    if value is None:
        return _error("DIGITAL_TWIN_NOT_FOUND", 404)
    try:
        checked = validate_snapshot(value)
        if checked.project_id != project_id:
            return _error("DIGITAL_TWIN_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("DIGITAL_TWIN_REJECTED", 422)


@router.get("/api/optimization/v26/{project_id}", response_model=OptimizationAnalysis)
async def get_optimization_analysis(
    project_id: str, request: Request
) -> OptimizationAnalysis | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("OPTIMIZATION_REJECTED", 422)
    port = getattr(request.app.state, "optimization_analysis_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("OPTIMIZATION_UNAVAILABLE", 503)
    try:
        value = await _call(method(project_id))
    except Exception:  # noqa: BLE001 - external adapter errors are intentionally sanitized
        return _error("OPTIMIZATION_UNAVAILABLE", 503)
    if value is None:
        return _error("FINDING_NOT_FOUND", 404)
    try:
        checked = validate_analysis(value)
        if checked.project_id != project_id:
            return _error("OPTIMIZATION_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("OPTIMIZATION_REJECTED", 422)


async def _decide(
    finding_id: str,
    request: OptimizationApprovalRequest,
    app_request: Request,
    operation: str,
) -> OptimizationFinding | JSONResponse:
    if not _FINDING.fullmatch(finding_id):
        return _error("OPTIMIZATION_REJECTED", 422)
    if request.finding_id != finding_id:
        return _error("OPTIMIZATION_REJECTED", 422)
    port = getattr(app_request.app.state, "optimization_approval_port", None)
    method = getattr(port, operation, None) if port is not None else None
    if port is None or not callable(method):
        return _error("APPROVAL_REQUIRED", 422)
    try:
        value = await _call(method(request))
        checked = validate_finding(value)
        if (
            checked.finding_id != finding_id
            or checked.fingerprint == request.finding_fingerprint
        ):
            if checked.finding_id != finding_id:
                return _error("OPTIMIZATION_REJECTED", 422)
            return checked
        return _error("OPTIMIZATION_REJECTED", 422)
    except (ValidationError, TypeError, ValueError):
        return _error("OPTIMIZATION_REJECTED", 422)
    except Exception:  # noqa: BLE001 - external adapter errors are intentionally sanitized
        return _error("OPTIMIZATION_REJECTED", 422)


@router.post(
    "/api/optimization/v26/{finding_id}/approve", response_model=OptimizationFinding
)
async def approve_optimization(
    finding_id: str, body: OptimizationApprovalRequest, request: Request
) -> OptimizationFinding | JSONResponse:
    return await _decide(finding_id, body, request, "approve")


@router.post(
    "/api/optimization/v26/{finding_id}/reject", response_model=OptimizationFinding
)
async def reject_optimization(
    finding_id: str, body: OptimizationApprovalRequest, request: Request
) -> OptimizationFinding | JSONResponse:
    return await _decide(finding_id, body, request, "reject")


__all__ = ["router"]
