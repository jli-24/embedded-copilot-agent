"""Thin FastAPI routing boundary for the Web Console."""

from fastapi import APIRouter, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from embedded_copilot.ai_runtime import EngineeringResponse
from embedded_copilot.conversation_feedback import ConversationFeedbackProjection
from embedded_copilot.web_api.models import (
    WebAttachmentMetadataRequest,
    WebAttachmentProjection,
    WebChatRequest,
    WebChatResponse,
    WebDashboardProjection,
    WebFeedbackRequest,
    WebProjectCreateRequest,
    WebProjectDetail,
    WebProjectReference,
    WebReportProjection,
    WebTimelineProjection,
)
from embedded_copilot.web_api.service import WebConsoleService


def create_web_router(service: WebConsoleService) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/api/projects",
        response_model=WebProjectReference,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(request: WebProjectCreateRequest) -> WebProjectReference:
        return service.create_project(request)

    @router.get("/api/projects/{project_id}", response_model=WebProjectDetail)
    def get_project(project_id: str) -> WebProjectDetail:
        return service.get_project(project_id)

    @router.get(
        "/api/projects/{project_id}/dashboard",
        response_model=WebDashboardProjection,
    )
    def get_dashboard(project_id: str) -> WebDashboardProjection:
        return service.get_dashboard(project_id)

    @router.get(
        "/api/projects/{project_id}/timeline",
        response_model=WebTimelineProjection,
    )
    def get_timeline(project_id: str) -> WebTimelineProjection:
        return service.get_timeline(project_id)

    @router.get("/api/projects/{project_id}/report", response_model=WebReportProjection)
    def get_report(project_id: str) -> WebReportProjection:
        return service.get_report(project_id)

    @router.post("/api/chat", response_model=WebChatResponse | EngineeringResponse)
    async def chat(
        request: WebChatRequest,
    ) -> WebChatResponse | EngineeringResponse:
        return await service.chat(request)

    @router.post(
        "/api/feedback",
        response_model=ConversationFeedbackProjection,
    )
    def project_feedback(
        request: WebFeedbackRequest,
    ) -> ConversationFeedbackProjection:
        return service.project_feedback(request)

    @router.post(
        "/api/projects/{project_id}/attachments",
        response_model=WebAttachmentProjection,
        status_code=status.HTTP_201_CREATED,
    )
    async def project_attachment(
        project_id: str, request: Request
    ) -> WebAttachmentProjection:
        try:
            metadata = WebAttachmentMetadataRequest.model_validate_json(
                await request.body()
            )
        except ValidationError as error:
            raise RequestValidationError(error.errors()) from None
        return service.project_attachment(project_id, metadata)

    return router
