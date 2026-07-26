from __future__ import annotations

from datetime import datetime
from typing import Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from embedded_copilot.api.copilot_models import (
    CopilotAttachmentReceipt,
    CopilotAttachmentRequest,
    CopilotMessageRequest,
    CopilotSessionCreateRequest,
    CopilotVisionRequest,
    CopilotVisionResponse,
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
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingConflict,
    AttachmentBindingNotFound,
)
from embedded_copilot.vision.models import VisionSuggestion


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

    def bind_attachment(
        self,
        binding: AttachmentBinding,
        *,
        trace_id: str,
    ) -> AttachmentBinding: ...

    async def analyze_vision(
        self,
        *,
        session_id: str,
        reference_id: str,
        message_summary: str,
        trace_id: str,
    ) -> VisionSuggestion: ...


def get_workspace_service(request: Request) -> WorkspaceService | None:
    return request.app.state.workspace_service


def _error(request: Request, *, status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "trace_id": request.state.trace_id},
    )


def _map_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, (ConversationNotFound, AttachmentBindingNotFound)):
        return _error(
            request,
            status_code=404,
            detail="Copilot session was not found.",
        )
    if isinstance(error, (ConversationStateConflict, AttachmentBindingConflict)):
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


@router.post(
    "/sessions/{session_id}/attachments",
    response_model=CopilotAttachmentReceipt,
    status_code=201,
)
def bind_copilot_attachment(
    session_id: str,
    payload: CopilotAttachmentRequest,
    request: Request,
    service: WorkspaceService | None = Depends(get_workspace_service),
) -> CopilotAttachmentReceipt | JSONResponse:
    if service is None:
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    try:
        binding = service.bind_attachment(
            payload.to_binding(session_id),
            trace_id=request.state.trace_id,
        )
        return CopilotAttachmentReceipt.from_binding(binding)
    except Exception as error:
        return _map_error(request, error)


@router.post(
    "/sessions/{session_id}/vision",
    response_model=CopilotVisionResponse,
)
async def analyze_copilot_vision(
    session_id: str,
    payload: CopilotVisionRequest,
    request: Request,
    service: WorkspaceService | None = Depends(get_workspace_service),
) -> CopilotVisionResponse | JSONResponse:
    if service is None:
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    try:
        suggestion = await service.analyze_vision(
            session_id=session_id,
            reference_id=payload.reference_id,
            message_summary=payload.message_summary,
            trace_id=request.state.trace_id,
        )
        return CopilotVisionResponse(summary=suggestion.summary)
    except Exception as error:
        return _map_error(request, error)
