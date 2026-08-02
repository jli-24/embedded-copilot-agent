"""FastAPI application factory for the Web Console."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from embedded_copilot.ai_runtime import EngineeringChatPort
from embedded_copilot.conversation_feedback import ConversationFeedbackPort
from embedded_copilot.web_api.contracts import (
    WebAttachmentProjectionPort,
    WebProjectPreparationPort,
    WebProjectRepositoryPort,
)
from embedded_copilot.web_api.exceptions import (
    WebDependencyUnavailable,
    WebProjectNotFound,
    WebRequestRejected,
)
from embedded_copilot.web_api.models import WebErrorResponse
from embedded_copilot.web_api.routes import create_web_router
from embedded_copilot.web_api.service import WebConsoleService


def create_web_api_app(
    *,
    product_port: object,
    preparation_port: WebProjectPreparationPort,
    repository_port: WebProjectRepositoryPort,
    attachment_port: WebAttachmentProjectionPort,
    engineering_chat_port: EngineeringChatPort | None = None,
    feedback_port: ConversationFeedbackPort | None = None,
) -> FastAPI:
    service = WebConsoleService(
        product_port=product_port,
        preparation_port=preparation_port,
        repository_port=repository_port,
        attachment_port=attachment_port,
        engineering_chat_port=engineering_chat_port,
        feedback_port=feedback_port,
    )
    application = FastAPI(title="Embedded Copilot Web API", version="1.1.0")
    application.include_router(create_web_router(service))

    @application.exception_handler(WebProjectNotFound)
    async def project_not_found(request: Request, error: WebProjectNotFound):
        return _error(404, "PROJECT_NOT_FOUND", "Project is unavailable")

    @application.exception_handler(WebRequestRejected)
    async def request_rejected(request: Request, error: WebRequestRejected):
        return _error(422, "WEB_REQUEST_REJECTED", "Web request was rejected")

    @application.exception_handler(RequestValidationError)
    async def validation_rejected(request: Request, error: RequestValidationError):
        return _error(422, "WEB_REQUEST_REJECTED", "Web request was rejected")

    @application.exception_handler(WebDependencyUnavailable)
    async def dependency_unavailable(request: Request, error: WebDependencyUnavailable):
        return _error(
            503,
            "WEB_DEPENDENCY_UNAVAILABLE",
            "Web dependency is unavailable",
        )

    return application


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    body = WebErrorResponse(code=code, message=message)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
