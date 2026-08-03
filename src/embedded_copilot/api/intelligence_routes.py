from __future__ import annotations

import copy

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from embedded_copilot.engineering_intelligence.context import build_context_snapshot
from embedded_copilot.engineering_intelligence.contracts import (
    EngineeringContextInputProjection,
    EngineeringIntelligenceRequest,
)

from .intelligence_models import (
    IntelligenceContextResponse,
    IntelligenceQueryRequest,
    IntelligenceQueryResponse,
)

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


def _dependencies(request: Request) -> tuple[object | None, object | None]:
    return (
        getattr(request.app.state, "intelligence_port", None),
        getattr(request.app.state, "intelligence_context_port", None),
    )


@router.post(
    "/api/intelligence/query",
    response_model=IntelligenceQueryResponse,
)
@router.post(
    "/api/v1/intelligence/query",
    response_model=IntelligenceQueryResponse,
    include_in_schema=False,
)
async def query_intelligence(payload: IntelligenceQueryRequest, request: Request):
    intelligence, context_port = _dependencies(request)
    if intelligence is None or context_port is None:
        return _error("INTELLIGENCE_DEPENDENCY_UNAVAILABLE", 503)
    try:
        raw = context_port.get_context(payload.project_id)
    except Exception:
        return _error("INTELLIGENCE_DEPENDENCY_UNAVAILABLE", 503)
    if raw is None:
        return _error("INTELLIGENCE_CONTEXT_NOT_FOUND", 404)
    if type(raw) is not EngineeringContextInputProjection:
        return _error("INTELLIGENCE_CONTEXT_REJECTED", 409)
    try:
        snapshot = build_context_snapshot(copy.deepcopy(raw))
        internal = EngineeringIntelligenceRequest(
            project_id=payload.project_id,
            question=payload.question,
            context_snapshot=snapshot,
        )
        result = await intelligence.query(internal)
        return IntelligenceQueryResponse(result=result)
    except ValueError:
        return _error("INTELLIGENCE_CONTEXT_REJECTED", 409)
    except Exception:
        return _error("INTELLIGENCE_DEPENDENCY_UNAVAILABLE", 503)


@router.get(
    "/api/intelligence/context/{project_id}",
    response_model=IntelligenceContextResponse,
)
@router.get(
    "/api/v1/intelligence/context/{project_id}",
    response_model=IntelligenceContextResponse,
    include_in_schema=False,
)
async def get_intelligence_context(project_id: str, request: Request):
    _, context_port = _dependencies(request)
    if context_port is None:
        return _error("INTELLIGENCE_DEPENDENCY_UNAVAILABLE", 503)
    try:
        raw = context_port.get_context(project_id)
    except Exception:
        return _error("INTELLIGENCE_DEPENDENCY_UNAVAILABLE", 503)
    if raw is None:
        return _error("INTELLIGENCE_CONTEXT_NOT_FOUND", 404)
    if type(raw) is not EngineeringContextInputProjection:
        return _error("INTELLIGENCE_CONTEXT_REJECTED", 409)
    try:
        return IntelligenceContextResponse(
            context=build_context_snapshot(copy.deepcopy(raw))
        )
    except Exception:
        return _error("INTELLIGENCE_CONTEXT_REJECTED", 409)
