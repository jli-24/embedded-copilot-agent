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

from embedded_copilot.api.dependencies import build_runtime
from embedded_copilot.api.routes import ChatService, router
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.schemas.result import ErrorCode, ErrorDetail
from embedded_copilot.services.config import Settings


logger = logging.getLogger(__name__)


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
    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


def create_app(
    *,
    settings: Settings | None = None,
    service: ChatService | None = None,
) -> FastAPI:
    active_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.settings = active_settings
        if service is not None:
            application.state.copilot_service = service
            application.state.health_status = "ok"
        else:
            runtime = await asyncio.to_thread(build_runtime, active_settings)
            application.state.copilot_service = runtime.service
            application.state.health_status = runtime.health_status
            application.state.ingestion_errors = runtime.ingestion_errors
        yield

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
    return application


app = create_app()
