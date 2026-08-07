from __future__ import annotations

import copy

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from embedded_copilot.api.memory_models import (
    MemoryApprovalRequest,
    MemoryCandidateListResponse,
    MemoryCandidateView,
    MemoryEventResponse,
)
from embedded_copilot.memory_automation import MemoryServicePort
from embedded_copilot.memory_automation.contracts import (
    MemoryApprovalProjection,
    MemoryCandidate,
)


router = APIRouter()


def _dependency_error() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "WEB_DEPENDENCY_UNAVAILABLE"},
    )


def _port(request: Request) -> MemoryServicePort | None:
    return getattr(request.app.state, "memory_service", None)


@router.get(
    "/api/memory/candidates",
    response_model=MemoryCandidateListResponse,
)
@router.get(
    "/api/v1/memory/candidates",
    response_model=MemoryCandidateListResponse,
    include_in_schema=False,
)
async def list_memory_candidates(request: Request):
    port = _port(request)
    if port is None:
        return _dependency_error()
    try:
        values = tuple(MemoryCandidate.model_validate(copy.deepcopy(item)) for item in port.list_candidates())
        return MemoryCandidateListResponse(
            candidates=tuple(MemoryCandidateView.from_candidate(item) for item in values)
        )
    except Exception:
        return JSONResponse(status_code=503, content={"error": "WEB_DEPENDENCY_UNAVAILABLE"})


@router.post("/api/memory/approve", response_model=MemoryEventResponse)
@router.post(
    "/api/v1/memory/approve",
    response_model=MemoryEventResponse,
    include_in_schema=False,
)
async def approve_memory(payload: MemoryApprovalRequest, request: Request):
    port = _port(request)
    if port is None:
        return _dependency_error()
    try:
        approval = MemoryApprovalProjection(
            memory_id=payload.memory_id,
            candidate_fingerprint=payload.candidate_fingerprint,
            reviewer=payload.reviewer,
            decision=payload.decision,
            reviewed_at=payload.reviewed_at,
        )
        result = port.approve(payload.memory_id, approval)
        return MemoryEventResponse(
            event_type=result.event_type,
            memory_id=result.memory_id,
            review_status=result.review_status,
        )
    except Exception:
        return JSONResponse(status_code=409, content={"error": "MEMORY_APPROVAL_REJECTED"})
