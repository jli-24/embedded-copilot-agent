from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from embedded_copilot.api.copilot_routes import (
    WorkspaceService,
    router as copilot_router,
)
from embedded_copilot.api.experience_routes import (
    ExperienceService,
    router as experience_router,
)
from embedded_copilot.api.routes import ChatService, ProductAnalysisService, router
from embedded_copilot.model_runtime import create_model_runtime
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.schemas.result import ErrorCode, ErrorDetail
from embedded_copilot.services.config import Settings
from embedded_copilot.services.experience_runtime import build_experience_runtime
from embedded_copilot.services.runtime import build_analysis_service, build_runtime

logger = logging.getLogger(__name__)


class _UnsetService:
    pass


_UNSET_SERVICE = _UnsetService()


def _error_response(
    *,
    trace_id: str,
    code: ErrorCode,
    message: str,
    status_code: int,
) -> JSONResponse:
    response = ChatResponse(
        answer="",
        trace_id=trace_id,
        error=ErrorDetail(code=code, message=message, retryable=False),
    )
    return JSONResponse(
        status_code=status_code, content=response.model_dump(mode="json")
    )


def create_app(
    *,
    settings: Settings | None = None,
    service: ChatService | None = None,
    analysis_service: ProductAnalysisService | None = None,
    workspace_service: WorkspaceService | None | _UnsetService = _UNSET_SERVICE,
    experience_service: ExperienceService | None | _UnsetService = _UNSET_SERVICE,
) -> FastAPI:
    active_settings = settings or Settings()
    model_runtime = create_model_runtime(active_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        default_experience_runtime = None
        if isinstance(workspace_service, _UnsetService):
            default_experience_runtime = build_experience_runtime(
                reasoning=model_runtime.reasoning_port()
            )
            active_workspace_service: WorkspaceService | None = (
                default_experience_runtime.workspace_service
            )
        else:
            active_workspace_service = workspace_service
        if isinstance(experience_service, _UnsetService):
            active_experience_service: ExperienceService | None = (
                default_experience_runtime.experience_service
                if default_experience_runtime is not None
                else None
            )
        else:
            active_experience_service = experience_service
        application.state.settings = active_settings
        application.state.workspace_service = active_workspace_service
        application.state.experience_service = active_experience_service
        if service is not None:
            application.state.copilot_service = service
            application.state.health_status = "ok"
        else:
            runtime = await asyncio.to_thread(build_runtime, active_settings)
            application.state.copilot_service = runtime.service
            application.state.health_status = runtime.health_status
            application.state.ingestion_errors = runtime.ingestion_errors
        active_analysis = analysis_service or build_analysis_service(active_settings)
        application.state.analysis_service = active_analysis
        await active_analysis.start()
        try:
            yield
        finally:
            await active_analysis.close()

    application = FastAPI(
        title=active_settings.app_name,
        version=active_settings.version,
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def trace_middleware(request: Request, call_next: Any):
        request.state.trace_id = str(uuid4())
        response = await call_next(request)
        response.headers["x-trace-id"] = request.state.trace_id
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if request.url.path.startswith("/api/v1/copilot/"):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Request validation failed.",
                    "trace_id": request.state.trace_id,
                },
            )
        return _error_response(
            trace_id=request.state.trace_id,
            code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed.",
            status_code=422,
        )

    @application.exception_handler(Exception)
    async def internal_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "error_occurred",
            extra={
                "event_name": "error_occurred",
                "trace_id": request.state.trace_id,
                "error_category": "internal_error",
            },
        )
        return _error_response(
            trace_id=request.state.trace_id,
            code=ErrorCode.INTERNAL_ERROR,
            message="Internal server error.",
            status_code=500,
        )

    application.include_router(router)
    application.include_router(copilot_router)
    application.include_router(experience_router)
    return application


app = create_app()
