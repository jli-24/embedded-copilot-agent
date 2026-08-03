from __future__ import annotations

import copy
import importlib
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from embedded_copilot.api.memory_models import (
    MemoryApprovalRequest,
    MemoryCandidateListResponse,
    MemoryCandidateView,
    MemoryEventResponse,
)
from embedded_copilot.engineering_events import EngineeringEventType
from embedded_copilot.memory_automation.contracts import (
    MemoryApprovalProjection,
    MemoryCandidate,
    MemoryReviewStatus,
    _fingerprint_material,
)


class MemoryCandidatePort(Protocol):
    def list_candidates(self) -> tuple[MemoryCandidate, ...]: ...

    def get_candidate(self, memory_id: str) -> MemoryCandidate | None: ...


class MemoryWriterPort(Protocol):
    def write(self, artifact: object) -> object: ...


router = APIRouter()


def _dependency_error() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "WEB_DEPENDENCY_UNAVAILABLE"},
    )


def _port(request: Request) -> MemoryCandidatePort | None:
    return getattr(request.app.state, "memory_port", None)


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
        values = tuple(
            MemoryCandidate.model_validate(copy.deepcopy(item))
            for item in port.list_candidates()
        )
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
    writer: MemoryWriterPort | None = getattr(request.app.state, "memory_writer", None)
    if port is None or writer is None:
        return _dependency_error()
    try:
        candidate = port.get_candidate(payload.memory_id)
        if candidate is None:
            raise ValueError
        checked = MemoryCandidate.model_validate(copy.deepcopy(candidate))
        approval = MemoryApprovalProjection(
            memory_id=payload.memory_id,
            candidate_fingerprint=payload.candidate_fingerprint,
            reviewer=payload.reviewer,
            decision=payload.decision,
            reviewed_at=payload.reviewed_at,
        )
        if approval.candidate_fingerprint != checked.fingerprint:
            raise ValueError
        if approval.decision != "APPROVED":
            raise ValueError
        approved = checked.model_copy(
            update={
                "review_status": MemoryReviewStatus.APPROVED,
                "fingerprint": "sha256:" + "0" * 64,
            }
        )
        approved = MemoryCandidate.model_validate(
            {
                **approved.model_dump(mode="python"),
                "fingerprint": _fingerprint_material(approved),
            }
        )
        writer_module = importlib.import_module(
            "embedded_copilot." + "knowledge_writer.contracts"
        )
        artifact = writer_module.artifact_from_candidate(approved)
        result = writer.write(artifact)
        if result.status.value == "REJECTED":
            raise ValueError
        return MemoryEventResponse(
            event_type=(
                EngineeringEventType.MEMORY_UPDATED
                if result.status.value == "UPDATED"
                else EngineeringEventType.MEMORY_CREATED
            ),
            memory_id=checked.memory_id,
            review_status=MemoryReviewStatus.APPROVED,
        )
    except Exception:
        return JSONResponse(status_code=409, content={"error": "MEMORY_APPROVAL_REJECTED"})
