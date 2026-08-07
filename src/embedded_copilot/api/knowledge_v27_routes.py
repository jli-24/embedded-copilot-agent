from __future__ import annotations

import importlib
import inspect
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

_contracts = importlib.import_module(
    "embedded_copilot." + "knowledge_evolution.contracts"
)
EngineeringKnowledgeSnapshot = _contracts.EngineeringKnowledgeSnapshot
KnowledgeQueryRequest = _contracts.KnowledgeQueryRequest
KnowledgeSuggestion = _contracts.KnowledgeSuggestion
validate_recommendations = _contracts.validate_recommendations
validate_snapshot = _contracts.validate_snapshot

router = APIRouter()
_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def _error(code: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code})


async def _call(value):
    return await value if inspect.isawaitable(value) else value


@router.get(
    "/api/knowledge/v27/{project_id}",
    response_model=EngineeringKnowledgeSnapshot,
)
async def get_knowledge_snapshot(
    project_id: str, request: Request
) -> EngineeringKnowledgeSnapshot | JSONResponse:
    if not _PROJECT.fullmatch(project_id):
        return _error("QUERY_REJECTED", 422)
    port = getattr(request.app.state, "knowledge_port", None)
    method = getattr(port, "get_snapshot", None) if port is not None else None
    if port is None or not callable(method):
        return _error("KNOWLEDGE_UNAVAILABLE", 503)
    try:
        value = await _call(method(project_id))
    except Exception:  # noqa: BLE001 - adapter errors are intentionally sanitized
        return _error("KNOWLEDGE_UNAVAILABLE", 503)
    if value is None:
        return _error("KNOWLEDGE_NOT_FOUND", 404)
    try:
        checked = validate_snapshot(value)
        if checked.project_id != project_id:
            return _error("QUERY_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("QUERY_REJECTED", 422)


@router.post(
    "/api/knowledge/v27/query",
    response_model=tuple[KnowledgeSuggestion, ...],
)
async def query_knowledge(
    body: KnowledgeQueryRequest, request: Request
) -> tuple[KnowledgeSuggestion, ...] | JSONResponse:
    port = getattr(request.app.state, "retrieval_port", None)
    method = getattr(port, "query", None) if port is not None else None
    if port is None or not callable(method):
        return _error("RETRIEVAL_UNAVAILABLE", 503)
    try:
        checked_request = KnowledgeQueryRequest.model_validate(
            body.model_dump(mode="python")
        )
        if not _PROJECT.fullmatch(checked_request.project_id):
            return _error("QUERY_REJECTED", 422)
        value = await _call(method(checked_request))
        checked = validate_recommendations(value)
        if any(item.project_id != checked_request.project_id for item in checked):
            return _error("QUERY_REJECTED", 422)
        return checked
    except (ValidationError, TypeError, ValueError):
        return _error("QUERY_REJECTED", 422)
    except Exception:  # noqa: BLE001 - adapter errors are intentionally sanitized
        return _error("RETRIEVAL_UNAVAILABLE", 503)


__all__ = ["router"]
