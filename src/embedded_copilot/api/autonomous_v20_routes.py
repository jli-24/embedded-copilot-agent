from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from embedded_copilot.approval_gate.contracts import ApprovalDecision
from embedded_copilot.approval_gate.exceptions import ApprovalExpired, ApprovalRejected
from embedded_copilot.autonomous_loop.contracts import (
    AutonomousLoopSnapshot,
    validate_snapshot,
)
from embedded_copilot.autonomous_loop.exceptions import (
    ActionApprovalRequired,
    InvalidTransition,
    LoopNotFound,
    LoopRejected,
)

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


class ResumeRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    snapshot_fingerprint: str | None = None


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", hide_input_in_errors=True)
    action_id: str | None = None
    action_fingerprint: str
    reviewer: str
    decided_at: object

    @field_validator("action_fingerprint", "reviewer", mode="before")
    @classmethod
    def validate_strings(cls, value: object, info) -> object:
        if (
            not isinstance(value, str)
            or not value.strip()
            or "\n" in value
            or "\r" in value
        ):
            raise ValueError(f"{info.field_name} is invalid")
        return value


def _project_id(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", value) is not None


async def _call(value):
    result = value
    if inspect.isawaitable(result):
        result = await result
    return result


def _map_exception(error: Exception) -> JSONResponse:
    if isinstance(error, LoopNotFound):
        return _error("LOOP_NOT_FOUND", 404)
    if isinstance(error, ActionApprovalRequired):
        return _error("ACTION_APPROVAL_REQUIRED", 422)
    if isinstance(error, InvalidTransition):
        return _error("INVALID_TRANSITION", 422)
    if isinstance(error, LoopRejected):
        return _error("LOOP_REJECTED", 422)
    if isinstance(error, ApprovalExpired):
        return _error("APPROVAL_EXPIRED", 422)
    if isinstance(error, ApprovalRejected):
        return _error("LOOP_REJECTED", 422)
    return _error("AUTONOMOUS_UNAVAILABLE", 503)


@router.get(
    "/api/v2/autonomous/loop/{project_id}", response_model=AutonomousLoopSnapshot
)
async def get_v20_loop(
    project_id: str, request: Request
) -> AutonomousLoopSnapshot | JSONResponse:
    if not _project_id(project_id):
        return _error("AUTONOMOUS_SNAPSHOT_REJECTED", 422)
    port = getattr(request.app.state, "loop_coordinator_port", None)
    if port is None or not callable(getattr(port, "get_snapshot", None)):
        return _error("AUTONOMOUS_UNAVAILABLE", 503)
    try:
        result = await _call(port.get_snapshot(project_id))
    except Exception:
        return _error("AUTONOMOUS_UNAVAILABLE", 503)
    if result is None:
        return _error("LOOP_NOT_FOUND", 404)
    try:
        checked = validate_snapshot(result)
        if checked.project_id != project_id:
            return _error("AUTONOMOUS_SNAPSHOT_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("AUTONOMOUS_SNAPSHOT_REJECTED", 422)


@router.post(
    "/api/autonomous/loop/{project_id}/resume", response_model=AutonomousLoopSnapshot
)
async def resume_loop(
    project_id: str,
    request: Request,
    body: ResumeRequest | None = Body(default=None),
) -> AutonomousLoopSnapshot | JSONResponse:
    if not _project_id(project_id):
        return _error("AUTONOMOUS_SNAPSHOT_REJECTED", 422)
    port = getattr(request.app.state, "loop_coordinator_port", None)
    if port is None or not callable(getattr(port, "resume", None)):
        return _error("AUTONOMOUS_UNAVAILABLE", 503)
    try:
        result = await _call(
            port.resume(project_id, body.snapshot_fingerprint if body else None)
        )
        return validate_snapshot(result)
    except Exception as error:
        return _map_exception(error)


async def _decide(
    action_id: str, request: Request, body: ApprovalRequest | None, *, rejected: bool
):
    port = getattr(request.app.state, "loop_coordinator_port", None)
    method = "reject" if rejected else "approve"
    if port is None or not callable(getattr(port, method, None)):
        return _error("AUTONOMOUS_UNAVAILABLE", 503)
    if body is None:
        return _error("ACTION_APPROVAL_REQUIRED", 422)
    if body.action_id is not None and body.action_id != action_id:
        return _error("ACTION_APPROVAL_REQUIRED", 422)
    try:
        decision = ApprovalDecision(
            action_id=body.action_id or action_id,
            action_fingerprint=body.action_fingerprint,
            reviewer=body.reviewer,
            decided_at=body.decided_at,
        )
        result = await _call(getattr(port, method)(action_id, decision))
        return validate_snapshot(result)
    except Exception as error:
        return _map_exception(error)


@router.post(
    "/api/autonomous/action/{action_id}/approve", response_model=AutonomousLoopSnapshot
)
async def approve_action(
    action_id: str,
    request: Request,
    body: ApprovalRequest | None = Body(default=None),
) -> AutonomousLoopSnapshot | JSONResponse:
    return await _decide(action_id, request, body, rejected=False)


@router.post(
    "/api/autonomous/action/{action_id}/reject", response_model=AutonomousLoopSnapshot
)
async def reject_action(
    action_id: str,
    request: Request,
    body: ApprovalRequest | None = Body(default=None),
) -> AutonomousLoopSnapshot | JSONResponse:
    return await _decide(action_id, request, body, rejected=True)
