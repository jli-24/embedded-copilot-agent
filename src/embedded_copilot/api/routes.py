from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from embedded_copilot.schemas.api import ChatRequest, ChatResponse, HealthResponse
from embedded_copilot.schemas.result import ErrorCode


class ChatService(Protocol):
    async def chat(self, message: str, *, trace_id: str) -> ChatResponse: ...


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.copilot_service


def _error_status(error_code: ErrorCode) -> int:
    return {
        ErrorCode.VALIDATION_ERROR: 422,
        ErrorCode.PERMISSION_DENIED: 403,
        ErrorCode.TIMEOUT: 504,
        ErrorCode.RETRIEVAL_ERROR: 503,
        ErrorCode.MODEL_ERROR: 503,
        ErrorCode.INTERNAL_ERROR: 500,
    }[error_code]


router = APIRouter()


@router.post("/api/v1/chat", response_model=ChatResponse)
@router.post("/chat", response_model=ChatResponse, include_in_schema=False)
async def chat(
    payload: ChatRequest,
    request: Request,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse | JSONResponse:
    response = await service.chat(payload.message, trace_id=request.state.trace_id)
    if response.error is not None:
        return JSONResponse(
            status_code=_error_status(response.error.code),
            content=response.model_dump(mode="json"),
        )
    return response


@router.get("/api/v1/health", response_model=HealthResponse)
@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status=request.app.state.health_status,
        mode=request.app.state.settings.runtime_mode,
    )
