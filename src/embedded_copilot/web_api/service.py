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
from embedded_copilot.execution import (
    BuildApproval,
    BuildExecutionRequest,
    BuildExecutionServicePort,
    BuildResult,
    build_execution_request_fingerprint,
)
from embedded_copilot.firmware_agent import (
    FirmwareAgentPort,
    FirmwareGenerationRequest,
    FirmwarePlatform,
    FirmwareProposal,
    firmware_generation_request_fingerprint,
)
from embedded_copilot.web_api.contracts import (
    WebAttachmentProjectionPort,
    WebBuildApprovalPort,
    WebBuildResultRepositoryPort,
    WebFirmwareProposalRepositoryPort,
    WebObservationProjectionPort,
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
    WebBuildResultProjection,
    WebBuildStartRequest,
    WebChatRequest,
    WebChatResponse,
    WebDashboardProjection,
    WebFeedbackRequest,
    WebFirmwareGenerateRequest,
    WebProjectCreateRequest,
    WebProjectDetail,
    WebProjectReference,
    WebReportProjection,
    WebTimelineProjection,
    web_build_result_fingerprint,
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
        "_build_approval",
        "_build_execution",
        "_build_repository",
        "_engineering_chat",
        "_feedback",
        "_firmware_agent",
        "_firmware_repository",
        "_observation",
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
        firmware_agent_port: FirmwareAgentPort | None = None,
        build_execution_port: BuildExecutionServicePort | None = None,
        build_approval_port: WebBuildApprovalPort | None = None,
        observation_port: WebObservationProjectionPort | None = None,
        firmware_repository_port: WebFirmwareProposalRepositoryPort | None = None,
        build_repository_port: WebBuildResultRepositoryPort | None = None,
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
        optional_ports = (
            firmware_agent_port,
            build_execution_port,
            build_approval_port,
            observation_port,
            firmware_repository_port,
            build_repository_port,
        )
        if any(item is not None for item in optional_ports) and any(
            item is None for item in optional_ports
        ):
            raise TypeError("v1.3 web ports must be configured together")
        if firmware_agent_port is not None and not isinstance(
            firmware_agent_port, FirmwareAgentPort
        ):
            raise TypeError("firmware_agent_port is invalid")
        if build_execution_port is not None and not isinstance(
            build_execution_port, BuildExecutionServicePort
        ):
            raise TypeError("build_execution_port is invalid")
        if build_approval_port is not None and not isinstance(
            build_approval_port, WebBuildApprovalPort
        ):
            raise TypeError("build_approval_port is invalid")
        if observation_port is not None and not isinstance(
            observation_port, WebObservationProjectionPort
        ):
            raise TypeError("observation_port is invalid")
        if firmware_repository_port is not None and not isinstance(
            firmware_repository_port, WebFirmwareProposalRepositoryPort
        ):
            raise TypeError("firmware_repository_port is invalid")
        if build_repository_port is not None and not isinstance(
            build_repository_port, WebBuildResultRepositoryPort
        ):
            raise TypeError("build_repository_port is invalid")
        self._product = ProductGateway(product_port)
        self._preparation = preparation_port
        self._repository = repository_port
        self._attachment = attachment_port
        self._engineering_chat = engineering_chat_port
        self._feedback = feedback_port
        self._firmware_agent = firmware_agent_port
        self._firmware_repository = firmware_repository_port
        self._build_execution = build_execution_port
        self._build_approval = build_approval_port
        self._build_repository = build_repository_port
        self._observation = observation_port

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

    async def generate_firmware(
        self, request: WebFirmwareGenerateRequest
    ) -> FirmwareProposal:
        checked = _copy(request, WebFirmwareGenerateRequest)
        self._require_v13()
        workspace = self._load(checked.project_id)
        context = project_engineering_workspace(workspace)
        values = {
            "request_id": checked.request_id,
            "context": context,
            "knowledge": (),
            "platform": FirmwarePlatform.ESP_IDF,
            "requested_at": checked.requested_at,
        }
        generated_request = FirmwareGenerationRequest(
            **values,
            fingerprint=firmware_generation_request_fingerprint(**values),
        )
        try:
            assert self._firmware_agent is not None
            assert self._firmware_repository is not None
            candidate = await self._firmware_agent.generate(
                generated_request.model_copy(deep=True)
            )
            proposal = _copy(candidate, FirmwareProposal)
            if (
                proposal.request_id != generated_request.request_id
                or proposal.project_id != generated_request.context.project_id
                or proposal.source_context_fingerprint
                != generated_request.context.fingerprint
                or proposal.source_workspace_fingerprint
                != generated_request.context.workspace_fingerprint
            ):
                raise WebDependencyUnavailable("web dependency is unavailable")
            self._firmware_repository.save(
                proposal.request_id, proposal.model_copy(deep=True)
            )
            return proposal
        except WebRequestRejected:
            raise
        except Exception:  # noqa: BLE001 - dependency errors are sanitized
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    async def start_build(
        self, request: WebBuildStartRequest
    ) -> WebBuildResultProjection:
        checked = _copy(request, WebBuildStartRequest)
        self._require_v13()
        try:
            assert self._firmware_repository is not None
            assert self._build_execution is not None
            assert self._build_approval is not None
            assert self._observation is not None
            assert self._build_repository is not None
            proposal = _copy(
                self._firmware_repository.load(checked.firmware_request_id),
                FirmwareProposal,
            )
            approval = _copy(
                self._build_approval.resolve(
                    approval_reference_id=checked.approval_reference_id,
                    build_id=checked.build_id,
                    proposal_fingerprint=proposal.fingerprint,
                ),
                BuildApproval,
            )
            request_values = {
                "build_id": checked.build_id,
                "proposal": proposal,
                "approval": approval,
                "requested_at": checked.requested_at,
            }
            build_request = BuildExecutionRequest(
                **request_values,
                fingerprint=build_execution_request_fingerprint(**request_values),
            )
            result = _copy(
                await self._build_execution.execute(
                    build_request.model_copy(deep=True)
                ),
                BuildResult,
            )
            observation = self._observation.observe(result.model_copy(deep=True))
            projection_values = {"result": result, "observation": observation}
            projection = WebBuildResultProjection(
                **projection_values,
                fingerprint=web_build_result_fingerprint(**projection_values),
            )
            self._build_repository.save(
                result.build_id, projection.model_copy(deep=True)
            )
            return projection
        except WebRequestRejected:
            raise
        except Exception:  # noqa: BLE001 - dependency errors are sanitized
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    def get_build_result(self, build_id: str) -> WebBuildResultProjection:
        _project_id(build_id)
        self._require_v13()
        try:
            assert self._build_repository is not None
            return _copy(
                self._build_repository.load(build_id),
                WebBuildResultProjection,
            )
        except WebRequestRejected:
            raise
        except Exception:  # noqa: BLE001 - repository errors are sanitized
            raise WebDependencyUnavailable("web dependency is unavailable") from None

    def _require_v13(self) -> None:
        if self._firmware_agent is None:
            raise WebDependencyUnavailable("web dependency is unavailable")

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
