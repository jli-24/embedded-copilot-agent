from __future__ import annotations

import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from embedded_copilot.component_recommendation.contracts import (
    ComponentRecommendation,
    validate_recommendations,
)

router = APIRouter()


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


@router.get(
    "/api/components/{project_id}",
    response_model=tuple[ComponentRecommendation, ...],
)
async def get_components(
    project_id: str, request: Request
) -> tuple[ComponentRecommendation, ...] | JSONResponse:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", project_id):
        return _error("COMPONENT_RECOMMENDATION_REJECTED", 422)
    port = getattr(request.app.state, "component_recommendation_port", None)
    if port is None or not callable(getattr(port, "get_recommendations", None)):
        return _error("COMPONENT_UNAVAILABLE", 503)
    try:
        result = port.get_recommendations(project_id)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return _error("COMPONENT_UNAVAILABLE", 503)
    if result is None:
        return _error("COMPONENT_PROJECT_NOT_FOUND", 404)
    try:
        return validate_recommendations(result)
    except (ValidationError, TypeError, ValueError):
        return _error("COMPONENT_RECOMMENDATION_REJECTED", 422)
