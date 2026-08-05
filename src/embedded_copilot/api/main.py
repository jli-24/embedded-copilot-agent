from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from embedded_copilot.api.copilot_routes import (
    WorkspaceService,
    router as copilot_router,
)
from embedded_copilot.api.memory_routes import router as memory_router
from embedded_copilot.api.intelligence_routes import router as intelligence_router
from embedded_copilot.api.reasoning_routes import router as reasoning_layer_router
from embedded_copilot.api.autonomous_routes import router as autonomous_loop_router
from embedded_copilot.api.generation_routes import router as generation_router
from embedded_copilot.api.workspace_routes import router as workspace_router
from embedded_copilot.api.toolchain_routes import router as toolchain_router
from embedded_copilot.api.component_routes import router as component_router
from embedded_copilot.api.device_routes import router as device_router
from embedded_copilot.api.observation_routes import router as observation_router
from embedded_copilot.api.validation_routes import router as validation_router
from embedded_copilot.api.autonomous_v20_routes import router as autonomous_v20_router
from embedded_copilot.api.tool_adapter_routes import router as tool_adapter_router
from embedded_copilot.api.hardware_v22_routes import router as hardware_v22_router
from embedded_copilot.api.debug_v23_routes import router as debug_v23_router
from embedded_copilot.api.optimization_v23_routes import router as optimization_v23_router
from embedded_copilot.api.firmware_v24_routes import router as firmware_v24_router
from embedded_copilot.api.hil_v25_routes import router as hil_v25_router
from embedded_copilot.api.context_adapters import (
    CopilotContextReferenceResolver,
    CopilotDatasheetContextSource,
    CopilotFileContextSource,
    CopilotVisionContextSource,
    UnavailableEngineeringContextPort,
)
from embedded_copilot.api.experience_routes import (
    ExperienceService,
    router as experience_router,
)
from embedded_copilot.api.file_reference_catalog import (
    CopilotFileReferenceCatalog,
)
from embedded_copilot.api.reasoning_adapters import ContextBackedReasoningService
from embedded_copilot.api.routes import ChatService, ProductAnalysisService, router
from embedded_copilot.datasheet_runtime import (
    DatasheetIntelligencePort,
    create_datasheet_runtime,
)
from embedded_copilot.context_runtime import (
    EngineeringContextPort,
    create_engineering_context_runtime,
)
from embedded_copilot.file_runtime import (
    FileIntelligencePort,
    create_file_runtime,
)
from embedded_copilot.model_runtime import create_model_runtime
from embedded_copilot.reasoning_runtime import (
    ReasoningPort,
    create_reasoning_runtime,
)
from embedded_copilot.reasoning import ReasoningService
from embedded_copilot.multimodal.context import (
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.schemas.api import ChatResponse
from embedded_copilot.schemas.result import ErrorCode, ErrorDetail
from embedded_copilot.services.config import Settings
from embedded_copilot.services.experience_runtime import build_experience_runtime
from embedded_copilot.services.runtime import build_analysis_service, build_runtime
from embedded_copilot.vision_runtime import (
    VisionPort,
    create_vision_runtime,
)

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
    vision_port: VisionPort | None | _UnsetService = _UNSET_SERVICE,
    file_port: FileIntelligencePort | None | _UnsetService = _UNSET_SERVICE,
    datasheet_port: DatasheetIntelligencePort | None | _UnsetService = _UNSET_SERVICE,
    context_port: EngineeringContextPort | None | _UnsetService = _UNSET_SERVICE,
    reasoning_port: ReasoningPort | None | _UnsetService = _UNSET_SERVICE,
    file_reference_paths: Mapping[tuple[str, str], str | Path] | None = None,
    memory_port: object | None = None,
    memory_writer: object | None = None,
    intelligence_port: object | None = None,
    intelligence_context_port: object | None = None,
    reasoning_layer_port: object | None = None,
    reasoning_input_resolver: object | None = None,
    autonomous_loop_port: object | None = None,
    generation_port: object | None = None,
    workspace_snapshot_port: object | None = None,
    toolchain_snapshot_port: object | None = None,
    component_recommendation_port: object | None = None,
    device_snapshot_port: object | None = None,
    flash_port: object | None = None,
    observation_snapshot_port: object | None = None,
    validation_loop_port: object | None = None,
    loop_coordinator_port: object | None = None,
    approval_gate_port: object | None = None,
    loop_state_port: object | None = None,
    memory_automation_port: object | None = None,
    tool_adapter_status_port: object | None = None,
    tool_adapter_build_port: object | None = None,
    tool_adapter_flash_port: object | None = None,
    tool_adapter_device_port: object | None = None,
    hardware_design_port: object | None = None,
    hardware_review_port: object | None = None,
    debug_analysis_port: object | None = None,
    optimization_port: object | None = None,
    optimization_approval_port: object | None = None,
    firmware_engineering_port: object | None = None,
    firmware_build_port: object | None = None,
    firmware_debug_port: object | None = None,
    hil_validation_port: object | None = None,
    device_observation_port: object | None = None,
    hardware_capability_port: object | None = None,
) -> FastAPI:
    active_settings = settings or Settings()
    model_runtime = create_model_runtime(active_settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        default_attachment_repository = (
            ProcessLocalAttachmentBindingRepository()
            if isinstance(workspace_service, _UnsetService)
            else None
        )
        if isinstance(vision_port, _UnsetService):
            active_vision_port: VisionPort | None = (
                create_vision_runtime(
                    active_settings,
                    default_attachment_repository,
                ).vision_port()
                if default_attachment_repository is not None
                else None
            )
        else:
            active_vision_port = vision_port
        default_file_runtime = None
        if default_attachment_repository is not None and (
            isinstance(file_port, _UnsetService)
            or isinstance(datasheet_port, _UnsetService)
        ):
            default_file_runtime = create_file_runtime(
                active_settings,
                CopilotFileReferenceCatalog(
                    default_attachment_repository,
                    file_reference_paths or {},
                ),
            )
        if isinstance(file_port, _UnsetService):
            active_file_port: FileIntelligencePort | None = (
                default_file_runtime.file_port()
                if default_file_runtime is not None
                else None
            )
        else:
            active_file_port = file_port
        if isinstance(datasheet_port, _UnsetService):
            active_datasheet_port: DatasheetIntelligencePort | None = (
                create_datasheet_runtime(
                    default_file_runtime.extraction_port()
                ).datasheet_port()
                if default_file_runtime is not None
                else None
            )
        else:
            active_datasheet_port = datasheet_port
        if isinstance(context_port, _UnsetService):
            active_context_port: EngineeringContextPort | None = (
                create_engineering_context_runtime(
                    file_port=CopilotFileContextSource(active_file_port),
                    datasheet_port=CopilotDatasheetContextSource(active_datasheet_port),
                    vision_port=CopilotVisionContextSource(active_vision_port),
                    reference_resolver=CopilotContextReferenceResolver(
                        default_attachment_repository
                    ),
                ).context_port()
                if default_attachment_repository is not None
                and active_file_port is not None
                and active_datasheet_port is not None
                and active_vision_port is not None
                else None
            )
        else:
            active_context_port = context_port
        if isinstance(reasoning_port, _UnsetService):
            active_reasoning_port: ReasoningPort | None = (
                model_runtime.enhance_reasoning_port(
                    create_reasoning_runtime().reasoning_port()
                )
                if active_context_port is not None
                else None
            )
        else:
            active_reasoning_port = reasoning_port
        active_reasoning_service = None
        if active_context_port is not None and active_reasoning_port is not None:
            active_reasoning_service = ContextBackedReasoningService(
                active_context_port,
                active_reasoning_port,
            )
        default_experience_runtime = None
        if isinstance(workspace_service, _UnsetService):
            if default_attachment_repository is None:
                raise RuntimeError("attachment repository composition failed")
            default_experience_runtime = build_experience_runtime(
                reasoning=model_runtime.reasoning_port(),
                context_port=(
                    active_context_port
                    if active_context_port is not None
                    else UnavailableEngineeringContextPort()
                ),
                attachment_repository=default_attachment_repository,
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
        application.state.model_status_port = model_runtime.status_port()
        application.state.vision_port = active_vision_port
        application.state.file_port = active_file_port
        application.state.datasheet_port = active_datasheet_port
        application.state.context_port = active_context_port
        application.state.reasoning_port = active_reasoning_port
        application.state.reasoning_service = active_reasoning_service
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
        application.state.memory_port = memory_port
        application.state.memory_writer = memory_writer
        application.state.intelligence_port = intelligence_port
        application.state.intelligence_context_port = intelligence_context_port
        application.state.reasoning_input_resolver = reasoning_input_resolver
        application.state.autonomous_loop_port = autonomous_loop_port
        application.state.generation_port = generation_port
        application.state.workspace_snapshot_port = workspace_snapshot_port
        application.state.toolchain_snapshot_port = toolchain_snapshot_port
        application.state.component_recommendation_port = component_recommendation_port
        application.state.device_snapshot_port = device_snapshot_port
        application.state.flash_port = flash_port
        application.state.observation_snapshot_port = observation_snapshot_port
        application.state.validation_loop_port = validation_loop_port
        application.state.loop_coordinator_port = loop_coordinator_port
        application.state.approval_gate_port = approval_gate_port
        application.state.loop_state_port = loop_state_port
        application.state.memory_automation_port = memory_automation_port
        application.state.tool_adapter_status_port = tool_adapter_status_port
        application.state.tool_adapter_build_port = tool_adapter_build_port
        application.state.tool_adapter_flash_port = tool_adapter_flash_port
        application.state.tool_adapter_device_port = tool_adapter_device_port
        application.state.hardware_design_port = hardware_design_port
        application.state.hardware_review_port = hardware_review_port
        application.state.debug_analysis_port = debug_analysis_port
        application.state.optimization_port = optimization_port
        application.state.optimization_approval_port = optimization_approval_port
        application.state.firmware_engineering_port = firmware_engineering_port
        application.state.firmware_build_port = firmware_build_port
        application.state.firmware_debug_port = firmware_debug_port
        application.state.hil_validation_port = hil_validation_port
        application.state.device_observation_port = device_observation_port
        application.state.hardware_capability_port = hardware_capability_port
        application.state.reasoning_layer_service = (
            ReasoningService(reasoning_layer_port)
            if reasoning_layer_port is not None
            else None
        )
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
        if request.url.path.endswith("/context"):
            return JSONResponse(
                status_code=422,
                content={
                    "error": "context_unavailable",
                    "trace_id": request.state.trace_id,
                },
            )
        if request.url.path.endswith("/reasoning"):
            return JSONResponse(
                status_code=422,
                content={
                    "error": "reasoning_unavailable",
                    "trace_id": request.state.trace_id,
                },
            )
        if request.url.path.endswith("/reasoning/query"):
            return JSONResponse(
                status_code=422,
                content={"error": "REASONING_REQUEST_REJECTED"},
            )
        if request.url.path.endswith("/intelligence/query"):
            return JSONResponse(
                status_code=422,
                content={"error": "INTELLIGENCE_QUERY_REJECTED"},
            )
        if "/api/optimization/v23/" in request.url.path:
            return JSONResponse(
                status_code=422,
                content={"error": "PROPOSAL_REJECTED"},
            )
        if "/api/firmware/v24/" in request.url.path:
            return JSONResponse(
                status_code=422,
                content={"error": "FIRMWARE_REJECTED"},
            )
        if "/api/hil/v25/" in request.url.path:
            return JSONResponse(
                status_code=422,
                content={"error": "HIL_REJECTED"},
            )
        if request.url.path.endswith("/datasheets/analyze"):
            return JSONResponse(
                status_code=422,
                content={
                    "error": "datasheet_unavailable",
                    "trace_id": request.state.trace_id,
                },
            )
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
    application.include_router(memory_router)
    application.include_router(intelligence_router)
    application.include_router(reasoning_layer_router)
    application.include_router(autonomous_loop_router)
    application.include_router(generation_router)
    application.include_router(workspace_router)
    application.include_router(toolchain_router)
    application.include_router(component_router)
    application.include_router(device_router)
    application.include_router(observation_router)
    application.include_router(validation_router)
    application.include_router(autonomous_v20_router)
    application.include_router(tool_adapter_router)
    application.include_router(hardware_v22_router)
    application.include_router(debug_v23_router)
    application.include_router(optimization_v23_router)
    application.include_router(firmware_v24_router)
    application.include_router(hil_v25_router)
    return application


app = create_app()
