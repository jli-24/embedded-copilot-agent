from __future__ import annotations

from datetime import datetime
from typing import Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from embedded_copilot.api.copilot_models import (
    CopilotAttachmentReceipt,
    CopilotAttachmentRequest,
    CopilotDatasheetRequest,
    CopilotDatasheetResponse,
    CopilotEngineeringContextRequest,
    CopilotEngineeringContextResponse,
    CopilotFileIntelligenceRequest,
    CopilotFileIntelligenceResponse,
    CopilotMessageRequest,
    CopilotModelStatusResponse,
    CopilotReasoningRequest,
    CopilotReasoningResponse,
    CopilotSessionCreateRequest,
    CopilotVisionRequest,
    CopilotVisionResponse,
)
from embedded_copilot.api.reasoning_adapters import ContextBackedReasoningService
from embedded_copilot.conversation.models import ConversationMessage, ConversationTurn
from embedded_copilot.context_runtime import EngineeringContextPort
from embedded_copilot.context_runtime.exceptions import (
    EngineeringContextConflict,
    EngineeringContextReferenceNotFound,
    EngineeringContextRejected,
    EngineeringContextTimeout,
    EngineeringContextUnavailable,
)
from embedded_copilot.conversation.repository import (
    ConversationNotFound,
    ConversationStateConflict,
)
from embedded_copilot.copilot.workspace import ProjectWorkspace
from embedded_copilot.datasheet_runtime import (
    DatasheetAnalysisTimeout,
    DatasheetDocumentRejected,
    DatasheetIntelligencePort,
    DatasheetRequest,
    DatasheetRuntimeUnavailable,
)
from embedded_copilot.file_runtime import (
    FileAnalysisTimeout,
    FileIntelligencePort,
    FileReferenceConflict,
    FileReferenceNotFound,
    FileReferenceRequest,
    FileRuntimeUnavailable,
    FileType,
)
from embedded_copilot.intelligence.exceptions import (
    ModelGatewayError,
    ModelProviderUnavailable,
)
from embedded_copilot.model_runtime import StatusPort
from embedded_copilot.reasoning_runtime import (
    ReasoningAnalysisTimeout,
    ReasoningContextConflict,
    ReasoningContextNotFound,
    ReasoningRequestRejected,
    ReasoningRuntimeUnavailable,
)
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingConflict,
    AttachmentBindingNotFound,
)
from embedded_copilot.vision_runtime import (
    ImageType,
    VisionPort,
    VisionProviderTimeout,
    VisionProviderUnavailable,
    VisionReferenceConflict,
    VisionRequest,
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

    def bind_attachment(
        self,
        binding: AttachmentBinding,
        *,
        trace_id: str,
    ) -> AttachmentBinding: ...


def get_workspace_service(request: Request) -> WorkspaceService | None:
    return request.app.state.workspace_service


def get_model_status_port(request: Request) -> StatusPort:
    return request.app.state.model_status_port


def get_vision_port(request: Request) -> VisionPort | None:
    return request.app.state.vision_port


def get_file_port(request: Request) -> FileIntelligencePort | None:
    return request.app.state.file_port


def get_datasheet_port(request: Request) -> DatasheetIntelligencePort | None:
    return request.app.state.datasheet_port


def get_context_port(request: Request) -> EngineeringContextPort | None:
    return request.app.state.context_port


def get_reasoning_service(request: Request) -> ContextBackedReasoningService | None:
    return request.app.state.reasoning_service


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
    if isinstance(
        error,
        (
            ConversationStateConflict,
            AttachmentBindingConflict,
            VisionReferenceConflict,
        ),
    ):
        return _error(
            request,
            status_code=409,
            detail="Copilot session state conflict.",
        )
    if isinstance(
        error,
        (
            ModelProviderUnavailable,
            ModelGatewayError,
            VisionProviderUnavailable,
        ),
    ):
        return _error(
            request,
            status_code=503,
            detail="Copilot workspace service is unavailable.",
        )
    if isinstance(error, (TimeoutError, VisionProviderTimeout)):
        return _error(
            request,
            status_code=504,
            detail="Copilot workspace request timed out.",
        )
    raise error


def _file_error(request: Request, *, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "file_unavailable",
            "trace_id": request.state.trace_id,
        },
    )


def _map_file_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, FileReferenceNotFound):
        return _file_error(request, status_code=404)
    if isinstance(error, FileReferenceConflict):
        return _file_error(request, status_code=409)
    if isinstance(error, FileRuntimeUnavailable):
        return _file_error(request, status_code=503)
    if isinstance(error, FileAnalysisTimeout):
        return _file_error(request, status_code=504)
    raise error


def _datasheet_error(request: Request, *, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "datasheet_unavailable",
            "trace_id": request.state.trace_id,
        },
    )


def _map_datasheet_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, FileReferenceNotFound):
        return _datasheet_error(request, status_code=404)
    if isinstance(error, FileReferenceConflict):
        return _datasheet_error(request, status_code=409)
    if isinstance(error, (DatasheetDocumentRejected, ValidationError)):
        return _datasheet_error(request, status_code=422)
    if isinstance(
        error,
        (DatasheetRuntimeUnavailable, FileRuntimeUnavailable),
    ):
        return _datasheet_error(request, status_code=503)
    if isinstance(
        error,
        (DatasheetAnalysisTimeout, FileAnalysisTimeout),
    ):
        return _datasheet_error(request, status_code=504)
    raise error


def _context_error(request: Request, *, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "context_unavailable",
            "trace_id": request.state.trace_id,
        },
    )


def _reasoning_error(request: Request, *, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": "reasoning_unavailable",
            "trace_id": request.state.trace_id,
        },
    )


def _map_reasoning_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, ReasoningContextNotFound):
        return _reasoning_error(request, status_code=404)
    if isinstance(error, ReasoningContextConflict):
        return _reasoning_error(request, status_code=409)
    if isinstance(error, ReasoningRequestRejected):
        return _reasoning_error(request, status_code=422)
    if isinstance(error, ReasoningRuntimeUnavailable):
        return _reasoning_error(request, status_code=503)
    if isinstance(error, ReasoningAnalysisTimeout):
        return _reasoning_error(request, status_code=504)
    raise error


def _map_context_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, EngineeringContextReferenceNotFound):
        return _context_error(request, status_code=404)
    if isinstance(error, EngineeringContextConflict):
        return _context_error(request, status_code=409)
    if isinstance(error, (EngineeringContextRejected, ValidationError)):
        return _context_error(request, status_code=422)
    if isinstance(error, EngineeringContextUnavailable):
        return _context_error(request, status_code=503)
    if isinstance(error, EngineeringContextTimeout):
        return _context_error(request, status_code=504)
    raise error


router = APIRouter(prefix="/api/v1/copilot")


@router.get(
    "/models/status",
    response_model=CopilotModelStatusResponse,
)
async def get_model_status(
    port: StatusPort = Depends(get_model_status_port),
) -> CopilotModelStatusResponse:
    result = await port.status()
    return CopilotModelStatusResponse(
        provider=result.provider,
        status=result.status,
        capabilities=result.capabilities,
        model=result.model,
    )


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
    port: VisionPort | None = Depends(get_vision_port),
) -> CopilotVisionResponse | JSONResponse:
    if port is None:
        return _error(
            request,
            status_code=503,
            detail="Copilot vision service is unavailable.",
        )
    try:
        suggestion = await port.analyze(
            VisionRequest(
                session_id=session_id,
                reference_id=payload.reference_id,
                image_type=ImageType.UNKNOWN,
                instruction_summary=payload.instruction_summary,
            )
        )
        return CopilotVisionResponse(
            type=suggestion.output_type,
            summary=suggestion.summary,
            review_required=suggestion.review_required,
        )
    except Exception as error:
        return _map_error(request, error)


@router.post(
    "/sessions/{session_id}/files/analyze",
    response_model=CopilotFileIntelligenceResponse,
)
async def analyze_copilot_file(
    session_id: str,
    payload: CopilotFileIntelligenceRequest,
    request: Request,
    port: FileIntelligencePort | None = Depends(get_file_port),
) -> CopilotFileIntelligenceResponse | JSONResponse:
    if port is None:
        return _file_error(request, status_code=503)
    try:
        suggestion = await port.analyze(
            FileReferenceRequest(
                session_id=session_id,
                file_id=payload.file_id,
                file_type=FileType.UNKNOWN,
                instruction_summary=payload.instruction_summary,
            )
        )
        return CopilotFileIntelligenceResponse(
            type=suggestion.output_type,
            summary=suggestion.summary,
            review_required=suggestion.review_required,
        )
    except Exception as error:
        return _map_file_error(request, error)


@router.post(
    "/sessions/{session_id}/datasheets/analyze",
    response_model=CopilotDatasheetResponse,
)
async def analyze_copilot_datasheet(
    session_id: str,
    payload: CopilotDatasheetRequest,
    request: Request,
    port: DatasheetIntelligencePort | None = Depends(get_datasheet_port),
) -> CopilotDatasheetResponse | JSONResponse:
    if port is None:
        return _datasheet_error(request, status_code=503)
    try:
        suggestion = await port.analyze(
            DatasheetRequest(
                session_id=session_id,
                file_id=payload.file_id,
                instruction_summary=payload.instruction_summary,
            )
        )
        return CopilotDatasheetResponse(
            type=suggestion.output_type,
            summary=suggestion.summary,
            review_required=suggestion.review_required,
        )
    except Exception as error:
        return _map_datasheet_error(request, error)


@router.post(
    "/sessions/{session_id}/context",
    response_model=CopilotEngineeringContextResponse,
)
async def compose_engineering_context(
    session_id: str,
    payload: CopilotEngineeringContextRequest,
    request: Request,
    port: EngineeringContextPort | None = Depends(get_context_port),
) -> CopilotEngineeringContextResponse | JSONResponse:
    if port is None:
        return _context_error(request, status_code=503)
    try:
        response = await port.compose(payload.to_context_request(session_id))
        return CopilotEngineeringContextResponse(
            output_type=response.output_type,
            context_summary=response.context_summary,
            review_required=response.review_required,
        )
    except Exception as error:
        return _map_context_error(request, error)


@router.post(
    "/sessions/{session_id}/reasoning",
    response_model=CopilotReasoningResponse,
)
async def analyze_copilot_reasoning(
    session_id: str,
    payload: CopilotReasoningRequest,
    request: Request,
    service: ContextBackedReasoningService | None = Depends(get_reasoning_service),
) -> CopilotReasoningResponse | JSONResponse:
    if service is None:
        return _reasoning_error(request, status_code=503)
    try:
        response = await service.analyze(
            session_id=session_id,
            trace_id=request.state.trace_id,
            payload=payload,
        )
        return CopilotReasoningResponse(
            output_type=response.output_type,
            reasoning_summary=response.reasoning_summary,
            risks=response.risks,
            next_steps=response.next_steps,
            trace=response.trace,
            review_required=response.review_required,
        )
    except Exception as error:
        return _map_reasoning_error(request, error)
