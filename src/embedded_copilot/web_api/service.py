"""Stateless Web Console application service."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.ai_runtime import (
    AIRequestRejected,
    EngineeringChatPort,
    EngineeringChatRequest,
    EngineeringResponse,
    engineering_chat_request_fingerprint,
    project_engineering_workspace,
)
from embedded_copilot.conversation_feedback import (
    ConversationFeedbackPort,
    ConversationFeedbackProjection,
    UserFeedback,
    user_feedback_fingerprint,
)
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
from embedded_copilot.web_api.integration.product import ProductGateway
from embedded_copilot.web_api.models import (
    WebAttachmentMetadataRequest,
    WebAttachmentProjection,
    WebAttachmentProjectionRequest,
    WebChatRequest,
    WebChatResponse,
    WebDashboardProjection,
    WebProjectCreateRequest,
    WebProjectDetail,
    WebProjectReference,
    WebFeedbackRequest,
    WebReportProjection,
    WebTimelineProjection,
    web_chat_response_fingerprint,
)
from embedded_copilot.web_api.projections import (
    project_dashboard,
    project_detail,
    project_reference,
    project_report,
    project_timeline,
)


class WebConsoleService:
    __slots__ = (
        "_attachment",
        "_engineering_chat",
        "_feedback",
        "_preparation",
        "_product",
        "_repository",
    )

    def __init__(
        self,
        *,
        product_port: object,
        preparation_port: WebProjectPreparationPort,
        repository_port: WebProjectRepositoryPort,
        attachment_port: WebAttachmentProjectionPort,
        engineering_chat_port: EngineeringChatPort | None = None,
        feedback_port: ConversationFeedbackPort | None = None,
    ) -> None:
        if not isinstance(preparation_port, WebProjectPreparationPort):
            raise TypeError("preparation_port is invalid")
        if not isinstance(repository_port, WebProjectRepositoryPort):
            raise TypeError("repository_port is invalid")
        if not isinstance(attachment_port, WebAttachmentProjectionPort):
            raise TypeError("attachment_port is invalid")
        if engineering_chat_port is not None and not isinstance(
            engineering_chat_port, EngineeringChatPort
        ):
            raise TypeError("engineering_chat_port is invalid")
        if feedback_port is not None and not isinstance(
            feedback_port, ConversationFeedbackPort
        ):
            raise TypeError("feedback_port is invalid")
        self._product = ProductGateway(product_port)
        self._preparation = preparation_port
        self._repository = repository_port
        self._attachment = attachment_port
        self._engineering_chat = engineering_chat_port
        self._feedback = feedback_port

    def create_project(self, request: WebProjectCreateRequest) -> WebProjectReference:
        checked = _copy(request, WebProjectCreateRequest)
        try:
            prepared = self._preparation.prepare(checked.model_copy(deep=True))
            workspace = self._product.create(prepared)
            self._repository.save(workspace.model_copy(deep=True))
            session = self._product.project(workspace)
            return project_reference(workspace, session)
        except WebRequestRejected:
            raise
        except WebProjectNotFound:
            raise
        except Exception:
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    def get_project(self, project_id: str) -> WebProjectDetail:
        workspace = self._load(project_id)
        return project_detail(workspace, self._product.project(workspace))

    def get_dashboard(self, project_id: str) -> WebDashboardProjection:
        workspace = self._load(project_id)
        return project_dashboard(workspace, self._product.dashboard(workspace))

    def get_timeline(self, project_id: str) -> WebTimelineProjection:
        workspace = self._load(project_id)
        return project_timeline(workspace, self._product.timeline(workspace))

    def get_report(self, project_id: str) -> WebReportProjection:
        workspace = self._load(project_id)
        return project_report(self._product.report(workspace))

    async def chat(
        self,
        request: WebChatRequest,
    ) -> WebChatResponse | EngineeringResponse:
        checked = _copy(request, WebChatRequest)
        if checked.project_id is not None:
            return await self._engineering_project_chat(checked)
        project = self.create_project(
            WebProjectCreateRequest(requirement=checked.message)
        )
        values = dict(
            project=project,
            message="Project Created",
            current_stage=project.current_stage,
        )
        return WebChatResponse(
            **values, fingerprint=web_chat_response_fingerprint(**values)
        )

    async def _engineering_project_chat(
        self,
        request: WebChatRequest,
    ) -> EngineeringResponse:
        if self._engineering_chat is None:
            raise WebDependencyUnavailable("web dependency is unavailable")
        assert request.project_id is not None
        assert request.request_id is not None
        assert request.requested_at is not None
        workspace = self._load(request.project_id)
        context = project_engineering_workspace(workspace)
        values = dict(
            request_id=request.request_id,
            project_id=request.project_id,
            message=request.message,
            context=context,
            requested_at=request.requested_at,
        )
        chat_request = EngineeringChatRequest(
            **values,
            fingerprint=engineering_chat_request_fingerprint(**values),
        )
        try:
            candidate = await self._engineering_chat.chat(
                chat_request.model_copy(deep=True)
            )
            return _copy(candidate, EngineeringResponse)
        except AIRequestRejected:
            raise WebRequestRejected("web request is invalid") from None
        except Exception:
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    def project_feedback(
        self,
        request: WebFeedbackRequest,
    ) -> ConversationFeedbackProjection:
        checked = _copy(request, WebFeedbackRequest)
        if self._feedback is None:
            raise WebDependencyUnavailable("web dependency is unavailable")
        workspace = self._load(checked.project_id)
        session = self._product.project(workspace)
        values = dict(
            feedback_id=checked.feedback_id,
            session_id=session.session_id,
            target_agent=checked.target_agent,
            feedback_type=checked.feedback_type,
            message=checked.message,
            timestamp=checked.timestamp,
        )
        feedback = UserFeedback(
            **values,
            fingerprint=user_feedback_fingerprint(**values),
        )
        try:
            candidate = self._feedback.project(feedback.model_copy(deep=True))
            return _copy(candidate, ConversationFeedbackProjection)
        except Exception:
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    def project_attachment(
        self, project_id: str, request: WebAttachmentMetadataRequest
    ) -> WebAttachmentProjection:
        checked = _copy(request, WebAttachmentMetadataRequest)
        workspace = self._load(project_id)
        session = self._product.project(workspace)
        projected = WebAttachmentProjectionRequest(
            project_id=workspace.project_id,
            session_id=session.session_id,
            reference_id=checked.reference_id,
            attachment_type=checked.attachment_type,
            basename=checked.basename,
            summary=checked.summary,
            size_bytes=checked.size_bytes,
            observed_at=checked.observed_at,
        )
        try:
            candidate = self._attachment.project(projected.model_copy(deep=True))
            result = _copy(candidate, WebAttachmentProjection)
            if (
                result.project_id != projected.project_id
                or result.session_id != projected.session_id
                or result.reference_id != projected.reference_id
                or result.attachment_type is not projected.attachment_type
                or result.source_fingerprint != projected.fingerprint
            ):
                raise WebDependencyUnavailable("web dependency is unavailable")
            return result
        except Exception:
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    def _load(self, project_id: str):
        _project_id(project_id)
        try:
            value = self._repository.load(project_id)
        except WebProjectNotFound:
            raise WebProjectNotFound("project is unavailable") from None
        except Exception:
            raise WebDependencyUnavailable("web dependency is unavailable") from None
        return self._product.workspace(value)


def _copy(value: object, expected_type: type):
    if type(value) is not expected_type:
        raise WebRequestRejected("web request is invalid") from None
    try:
        return expected_type.model_validate(value.model_copy(deep=True))
    except (TypeError, ValueError, ValidationError):
        raise WebRequestRejected("web request is invalid") from None


def _project_id(value: object) -> str:
    if type(value) is not str or not value or len(value) > 128:
        raise WebRequestRejected("web request is invalid") from None
    return value
