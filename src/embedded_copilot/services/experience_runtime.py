from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from embedded_copilot.conversation.context import ContextResolver
from embedded_copilot.conversation.models import ConversationMessage, ConversationTurn
from embedded_copilot.conversation.reasoning import ReasoningPort
from embedded_copilot.conversation.repository import (
    ConversationNotFound,
    ProcessLocalConversationRepository,
)
from embedded_copilot.conversation.router import IntentRouter
from embedded_copilot.conversation.service import ConversationService
from embedded_copilot.copilot.models import (
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
)
from embedded_copilot.copilot.workspace import WorkspaceFile, track_file
from embedded_copilot.experience.existing_contracts import (
    ArtifactView,
    DesignSessionContext,
    ProjectWorkspace,
    WorkflowProgress,
)
from embedded_copilot.experience.models import BlueprintProjection
from embedded_copilot.experience.review import ProcessLocalReviewRepository
from embedded_copilot.experience.service import (
    ExperienceNotFound,
    ProcessLocalExperienceService,
)
from embedded_copilot.multimodal.context import (
    AttachmentBinding,
    AttachmentBindingConflict,
    AttachmentBindingNotFound,
    ProcessLocalAttachmentBindingRepository,
)
from embedded_copilot.multimodal.models import (
    MultimodalInputType,
)
from embedded_copilot.schemas.knowledge_trace import KnowledgeTrace


class _ArtifactProjectionPort:
    def get(self, session_id: str, artifact_id: str) -> ArtifactView | None:
        return None


class _WorkspaceProjectionPort:
    def __init__(self, repository: ProcessLocalConversationRepository) -> None:
        self._repository = repository

    def get(self, session_id: str) -> ProjectWorkspace:
        try:
            return self._repository.get(session_id)
        except ConversationNotFound as error:
            raise ExperienceNotFound("Workspace projection was not found") from error


class _BlueprintProjectionPort:
    def get(self, session_id: str, artifact_id: str) -> BlueprintProjection | None:
        return None


class _KnowledgeTraceProjectionPort:
    def __init__(self, repository: ProcessLocalConversationRepository) -> None:
        self._repository = repository

    def list(self, session_id: str) -> tuple[KnowledgeTrace, ...]:
        try:
            return self._repository.get(session_id).knowledge_traces
        except ConversationNotFound as error:
            raise ExperienceNotFound(
                "Knowledge trace projection was not found"
            ) from error


class _WorkflowProgressProjectionPort:
    def __init__(self, repository: ProcessLocalConversationRepository) -> None:
        self._repository = repository

    def list(self, session_id: str) -> tuple[WorkflowProgress, ...]:
        try:
            return self._repository.get(session_id).progress
        except ConversationNotFound as error:
            raise ExperienceNotFound("Progress projection was not found") from error


class ProcessLocalWorkspaceService:
    def __init__(
        self,
        *,
        repository: ProcessLocalConversationRepository,
        conversation_service: ConversationService,
        attachment_repository: ProcessLocalAttachmentBindingRepository,
    ) -> None:
        self._repository = repository
        self._conversation_service = conversation_service
        self._attachment_repository = attachment_repository

    async def create_session(
        self,
        *,
        session_id: str,
        project_name: str,
        user_requirement: str,
        created_at: datetime,
        trace_id: str,
    ) -> ProjectWorkspace:
        context = DesignSessionContext(
            session_id=session_id,
            project_name=project_name,
            user_requirement=user_requirement,
            created_at=created_at,
            updated_at=created_at,
        )
        workspace = ProjectWorkspace(session=context)
        self._repository.add(workspace)
        return self._repository.get(session_id)

    def get_session(self, session_id: str, *, trace_id: str) -> ProjectWorkspace:
        return self._repository.get(session_id)

    async def send_message(
        self,
        message: ConversationMessage,
        *,
        trace_id: str,
    ) -> ConversationTurn:
        return await self._conversation_service.send_message(message)

    def bind_attachment(
        self,
        binding: AttachmentBinding,
        *,
        trace_id: str,
    ) -> AttachmentBinding:
        workspace = self._repository.get(binding.session_id)
        try:
            self._attachment_repository.get(
                binding.session_id,
                binding.input.reference_id,
            )
        except AttachmentBindingNotFound:
            pass
        else:
            raise AttachmentBindingConflict("attachment reference already exists")
        if binding.input.type is MultimodalInputType.TEXT:
            raise AttachmentBindingConflict("attachment type is invalid")
        file_type = (
            WorkspaceFileType.DATASHEET
            if binding.input.type is MultimodalInputType.FILE
            else WorkspaceFileType.OTHER
        )
        updated = track_file(
            workspace,
            WorkspaceFile(
                file_id=binding.input.reference_id,
                filename=binding.basename,
                file_type=file_type,
                size_bytes=binding.size_bytes,
                source=WorkspaceFileSource.INPUT,
                status=WorkspaceFileStatus.REFERENCED,
                created_at=binding.created_at,
            ),
        )
        self._attachment_repository.bind(binding)
        self._repository.save(updated)
        return self._attachment_repository.get(
            binding.session_id,
            binding.input.reference_id,
        )


@dataclass(frozen=True)
class ExperienceRuntime:
    workspace_service: ProcessLocalWorkspaceService
    experience_service: ProcessLocalExperienceService
    attachment_repository: ProcessLocalAttachmentBindingRepository


def build_experience_runtime(*, reasoning: ReasoningPort) -> ExperienceRuntime:
    repository = ProcessLocalConversationRepository()
    attachment_repository = ProcessLocalAttachmentBindingRepository()
    conversation_service = ConversationService(
        repository=repository,
        context_resolver=ContextResolver(),
        intent_router=IntentRouter(),
        reasoning=reasoning,
        attachment_repository=attachment_repository,
    )
    workspace_service = ProcessLocalWorkspaceService(
        repository=repository,
        conversation_service=conversation_service,
        attachment_repository=attachment_repository,
    )
    experience_service = ProcessLocalExperienceService(
        workspace_port=_WorkspaceProjectionPort(repository),
        artifact_port=_ArtifactProjectionPort(),
        blueprint_port=_BlueprintProjectionPort(),
        knowledge_trace_port=_KnowledgeTraceProjectionPort(repository),
        progress_port=_WorkflowProgressProjectionPort(repository),
        review_repository=ProcessLocalReviewRepository(),
        clock=lambda: datetime.now(timezone.utc),
    )
    return ExperienceRuntime(
        workspace_service=workspace_service,
        experience_service=experience_service,
        attachment_repository=attachment_repository,
    )
