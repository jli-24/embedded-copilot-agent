from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from embedded_copilot.api.experience_models import ReviewIntentRequest
from embedded_copilot.experience.models import (
    ExperienceRequest,
    ExperienceResponse,
    ReviewIntent,
    ReviewReceipt,
)
from embedded_copilot.experience.presentation import (
    ArtifactViewerResponse,
    ExperienceProjectionUnavailable,
    FileExplorerResponse,
    ProgressResponse,
)
from embedded_copilot.experience.review import ReviewStateConflict
from embedded_copilot.experience.service import ExperienceNotFound


class ExperienceService(Protocol):
    def get_workspace(self, request: ExperienceRequest) -> ExperienceResponse: ...

    def get_artifacts(self, request: ExperienceRequest) -> ArtifactViewerResponse: ...

    def get_files(self, request: ExperienceRequest) -> FileExplorerResponse: ...

    def get_progress(self, request: ExperienceRequest) -> ProgressResponse: ...

    def record_review(self, intent: ReviewIntent) -> ReviewReceipt: ...


def get_experience_service(request: Request) -> ExperienceService | None:
    return request.app.state.experience_service


def _error(request: Request, *, status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "trace_id": request.state.trace_id},
    )


def _map_error(request: Request, error: Exception) -> JSONResponse:
    if isinstance(error, ExperienceNotFound):
        return _error(
            request,
            status_code=404,
            detail="Copilot experience resource was not found.",
        )
    if isinstance(error, (ReviewStateConflict, ValueError)):
        return _error(
            request,
            status_code=409,
            detail="Copilot experience state conflict.",
        )
    if isinstance(error, ExperienceProjectionUnavailable):
        return _error(
            request,
            status_code=503,
            detail="Copilot experience projection is unavailable.",
        )
    if isinstance(error, TimeoutError):
        return _error(
            request,
            status_code=504,
            detail="Copilot experience request timed out.",
        )
    raise error


def _service_unavailable(request: Request) -> JSONResponse:
    return _error(
        request,
        status_code=503,
        detail="Copilot experience service is unavailable.",
    )


router = APIRouter(prefix="/api/v1/copilot/sessions/{session_id}")


@router.get("/workspace", response_model=ExperienceResponse)
def get_workspace_experience(
    session_id: str,
    request: Request,
    service: ExperienceService | None = Depends(get_experience_service),
) -> ExperienceResponse | JSONResponse:
    if service is None:
        return _service_unavailable(request)
    try:
        return service.get_workspace(ExperienceRequest(session_id=session_id))
    except Exception as error:
        return _map_error(request, error)


@router.get("/artifact-view", response_model=ArtifactViewerResponse)
def get_artifact_experience(
    session_id: str,
    request: Request,
    service: ExperienceService | None = Depends(get_experience_service),
) -> ArtifactViewerResponse | JSONResponse:
    if service is None:
        return _service_unavailable(request)
    try:
        return service.get_artifacts(ExperienceRequest(session_id=session_id))
    except Exception as error:
        return _map_error(request, error)


@router.get("/files", response_model=FileExplorerResponse)
def get_files_experience(
    session_id: str,
    request: Request,
    service: ExperienceService | None = Depends(get_experience_service),
) -> FileExplorerResponse | JSONResponse:
    if service is None:
        return _service_unavailable(request)
    try:
        return service.get_files(ExperienceRequest(session_id=session_id))
    except Exception as error:
        return _map_error(request, error)


@router.get("/progress", response_model=ProgressResponse)
def get_progress_experience(
    session_id: str,
    request: Request,
    service: ExperienceService | None = Depends(get_experience_service),
) -> ProgressResponse | JSONResponse:
    if service is None:
        return _service_unavailable(request)
    try:
        return service.get_progress(ExperienceRequest(session_id=session_id))
    except Exception as error:
        return _map_error(request, error)


@router.post("/review", response_model=ReviewReceipt, status_code=202)
def record_review_experience(
    session_id: str,
    payload: ReviewIntentRequest,
    request: Request,
    service: ExperienceService | None = Depends(get_experience_service),
) -> ReviewReceipt | JSONResponse:
    if service is None:
        return _service_unavailable(request)
    try:
        return service.record_review(payload.to_intent(session_id))
    except Exception as error:
        return _map_error(request, error)
