from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from embedded_copilot.reasoning import (
    ReasoningRequestRejected,
    ReasoningRuntimeUnavailable,
    ReasoningService,
)

from .reasoning_models import ReasoningQueryRequest, ReasoningQueryResponse

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@router.post(
    "/api/reasoning/query",
    response_model=ReasoningQueryResponse,
)
async def query_reasoning(
    payload: ReasoningQueryRequest,
    request: Request,
) -> ReasoningQueryResponse | JSONResponse:
    service = getattr(request.app.state, "reasoning_layer_service", None)
    resolver = getattr(request.app.state, "reasoning_input_resolver", None)
    if not isinstance(service, ReasoningService) or not callable(
        getattr(resolver, "resolve", None)
    ):
        return _error("REASONING_UNAVAILABLE", 503)
    try:
        projection = resolver.resolve(payload.recommendation_id)
        if projection is None:
            return _error("REASONING_REQUEST_REJECTED", 422)
        response = service.reason(
            projection=projection,
            question=payload.question,
            reasoning_mode=payload.mode,
        )
        return ReasoningQueryResponse.from_response(response)
    except ReasoningRequestRejected:
        return _error("REASONING_REQUEST_REJECTED", 422)
    except ReasoningRuntimeUnavailable:
        return _error("REASONING_UNAVAILABLE", 503)
    except Exception:
        return _error("REASONING_UNAVAILABLE", 503)


__all__ = ["router"]
