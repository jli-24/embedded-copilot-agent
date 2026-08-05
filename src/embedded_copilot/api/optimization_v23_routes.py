from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from embedded_copilot.optimization.contracts import (
    OptimizationApprovalRequest,
    OptimizationProposal,
    validate_optimization_proposal,
)

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
_PROPOSAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


@router.get(
    "/api/optimization/v23/{project_id}", response_model=OptimizationProposal
)
async def get_optimization(
    project_id: str, request: Request
) -> OptimizationProposal | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("PROPOSAL_REJECTED", 422)
    port = getattr(request.app.state, "optimization_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("OPTIMIZATION_UNAVAILABLE", 503)
    try:
        result = await _call(method(project_id))
    except Exception:
        return _error("OPTIMIZATION_UNAVAILABLE", 503)
    if result is None:
        return _error("PROPOSAL_NOT_FOUND", 404)
    try:
        checked = validate_optimization_proposal(result)
        if checked.project_id != project_id:
            return _error("PROPOSAL_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("PROPOSAL_REJECTED", 422)


async def _decide(
    proposal_id: str,
    body: OptimizationApprovalRequest,
    request: Request,
    method_name: str,
) -> OptimizationProposal | JSONResponse:
    if not _PROPOSAL.fullmatch(proposal_id):
        return _error("PROPOSAL_REJECTED", 422)
    try:
        decision = OptimizationApprovalRequest.model_validate(body.model_dump(mode="python"))
    except (ValidationError, TypeError, ValueError):
        return _error("PROPOSAL_REJECTED", 422)
    if decision.proposal_id != proposal_id:
        return _error("PROPOSAL_REJECTED", 422)
    port = getattr(request.app.state, "optimization_approval_port", None)
    method = getattr(port, method_name, None) if port is not None else None
    if port is None or not callable(method):
        return _error("APPROVAL_REQUIRED", 422)
    try:
        result = await _call(method(decision))
        return validate_optimization_proposal(result)
    except (ValidationError, TypeError, ValueError):
        return _error("PROPOSAL_REJECTED", 422)
    except Exception:
        return _error("PROPOSAL_REJECTED", 422)


@router.post(
    "/api/optimization/v23/{proposal_id}/approve",
    response_model=OptimizationProposal,
)
async def approve_optimization(
    proposal_id: str, body: OptimizationApprovalRequest, request: Request
) -> OptimizationProposal | JSONResponse:
    return await _decide(proposal_id, body, request, "approve")


@router.post(
    "/api/optimization/v23/{proposal_id}/reject",
    response_model=OptimizationProposal,
)
async def reject_optimization(
    proposal_id: str, body: OptimizationApprovalRequest, request: Request
) -> OptimizationProposal | JSONResponse:
    return await _decide(proposal_id, body, request, "reject")


__all__ = ["router"]
