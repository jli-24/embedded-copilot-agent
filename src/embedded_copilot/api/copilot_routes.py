from __future__ import annotations

from datetime import datetime
from typing import Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from embedded_copilot.api.copilot_models import (
    CopilotMessageRequest,
    CopilotSessionCreateRequest,
)
from embedded_copilot.conversation.models import ConversationMessage, ConversationTurn
from embedded_copilot.conversation.repository import (
    ConversationNotFound,
    ConversationStateConflict,
)
from embedded_copilot.copilot.workspace import ProjectWorkspace
from embedded_copilot.intelligence.exceptions import (
    ModelGatewayError,
    ModelProviderUnavailable,
)


class WorkspaceService(Protocol):
    async def create_session(
        self,
        *,
        session_id: str,
        project_name: str,
        user_requirement: str,
        created_at: datetime,
        trace_id: str,
    ) -> ProjectWorkspace: ...

    def get_session(
        self,
        session_id: str,
        *,
        trace_id: str,
    ) -> ProjectWorkspace: ...

    async def send_message(
        self,
        message: ConversationMessage,
        *,
        trace_id: str,
    ) -> ConversationTurn: ...


def get_workspace_service(request: Request) -> WorkspaceService | None:
    return request.app.state.workspace_service


def _error(request: Request, *, status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "trace_id": request.state.trace_id},
    )


def _map_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, ConversationNotFound):
        return _error(
            request,
            status_code=404,
            detail="Copilot session was not found.",
        )
    if isinstance(error, ConversationStateConflict):
        return _error(
            request,
            status_code=409,
            detail="Copilot session state conflict.",
        )
    if isinstance(error, (ModelProviderUnavailable, ModelGatewayError)):
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    if isinstance(error, TimeoutError):
        return _error(
            request,
            status_code=504,
            detail="Copilot workspace request timed out.",
        )
    raise error


router = APIRouter(prefix="/api/v1/copilot")


@router.post(
    "/sessions",
    response_model=ProjectWorkspace,
    status_code=201,
)
async def create_copilot_session(
    payload: CopilotSessionCreateRequest,
    request: Request,
    service: WorkspaceService | None = Depends(get_workspace_service),
) -> ProjectWorkspace | JSONResponse:
    if service is None:
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    try:
        return await service.create_session(
            session_id=payload.session_id,
            project_name=payload.project_name,
            user_requirement=payload.user_requirement,
            created_at=payload.created_at,
            trace_id=request.state.trace_id,
        )
    except Exception as error:
        return _map_error(request, error)


@router.get(
    "/sessions/{session_id}",
    response_model=ProjectWorkspace,
)
def get_copilot_session(
    session_id: str,
    request: Request,
    service: WorkspaceService | None = Depends(get_workspace_service),
) -> ProjectWorkspace | JSONResponse:
    if service is None:
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    try:
        return service.get_session(session_id, trace_id=request.state.trace_id)
    except Exception as error:
        return _map_error(request, error)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ConversationTurn,
)
async def send_copilot_message(
    session_id: str,
    payload: CopilotMessageRequest,
    request: Request,
    service: WorkspaceService | None = Depends(get_workspace_service),
) -> ConversationTurn | JSONResponse:
    if service is None:
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    try:
        return await service.send_message(
            payload.to_message(session_id),
            trace_id=request.state.trace_id,
        )
    except Exception as error:
        return _map_error(request, error)
