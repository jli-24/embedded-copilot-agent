from __future__ import annotations

import copy
from collections.abc import Iterable
from datetime import datetime
from pathlib import PurePath

from pydantic import Field, field_validator, model_validator

from embedded_copilot.copilot.context import ChatMessage, DesignSessionContext
from embedded_copilot.copilot.events import ApprovalEvent, KnowledgeTrace
from embedded_copilot.copilot.models import (
    CopilotContractModel,
    DesignStage,
    WorkspaceFileSource,
    WorkspaceFileStatus,
    WorkspaceFileType,
    safe_identifier,
    safe_summary,
    utc_datetime,
)
from embedded_copilot.copilot.progress import WorkflowProgress, update_progress

_STAGE_INDEX = {stage: index for index, stage in enumerate(DesignStage)}


class WorkspaceFile(CopilotContractModel):
    file_id: str
    filename: str
    file_type: WorkspaceFileType
    size_bytes: int = Field(ge=0)
    source: WorkspaceFileSource
    status: WorkspaceFileStatus
    created_at: datetime

    @field_validator("file_id", mode="before")
    @classmethod
    def validate_file_id(cls, value: object) -> str:
        return safe_identifier(value, field="file_id")

    @field_validator("filename", mode="before")
    @classmethod
    def validate_filename(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("filename must be a string")
        candidate = value.strip()
        if (
            not candidate
            or len(candidate) > 255
            or PurePath(candidate).name != candidate
            or "/" in candidate
            or "\\" in candidate
            or candidate in {".", ".."}
        ):
            raise ValueError("filename must be a basename")
        return safe_summary(candidate, field="filename", max_length=255)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="created_at")


class ProjectWorkspace(CopilotContractModel):
    session: DesignSessionContext
    files: tuple[WorkspaceFile, ...] = ()
    messages: tuple[ChatMessage, ...] = ()
    progress: tuple[WorkflowProgress, ...] = ()
    approval_events: tuple[ApprovalEvent, ...] = ()
    knowledge_traces: tuple[KnowledgeTrace, ...] = ()

    @model_validator(mode="after")
    def validate_reference_indexes(self) -> "ProjectWorkspace":
        _unique_ids((item.file_id for item in self.files), field="file")
        _unique_ids((item.message_id for item in self.messages), field="message")
        _unique_ids(
            (item.approval_id for item in self.approval_events),
            field="approval event",
        )
        workspace_file_ids = {item.file_id.casefold() for item in self.files}
        session_file_ids = {item.casefold() for item in self.session.file_ids}
        if not workspace_file_ids.issubset(session_file_ids):
            raise ValueError("workspace file metadata is not bound to the session")
        known_references = {
            item.casefold()
            for item in (
                *self.session.artifact_ids,
                *self.session.decision_ids,
                *self.session.file_ids,
            )
        }
        if any(
            reference.casefold() not in known_references
            for message in self.messages
            for reference in message.references
        ):
            raise ValueError("workspace message reference is not bound to the session")
        progress_stages = tuple(item.stage for item in self.progress)
        if len(progress_stages) != len(set(progress_stages)):
            raise ValueError("workspace progress stages are ambiguous")
        if progress_stages != tuple(sorted(progress_stages, key=_stage_index)):
            raise ValueError("workspace progress stages are not in display order")
        return self


def create_workspace(context: DesignSessionContext) -> ProjectWorkspace:
    return ProjectWorkspace(session=_session(context))


def track_file(workspace: ProjectWorkspace, file: WorkspaceFile) -> ProjectWorkspace:
    isolated = _workspace(workspace)
    candidate = WorkspaceFile.model_validate(file.model_dump(mode="python"))
    if candidate.file_id.casefold() in {
        item.file_id.casefold() for item in isolated.files
    }:
        raise ValueError("file reference already exists")
    session = _update_session_files(isolated.session, candidate)
    return _replace(
        isolated,
        session=session,
        files=(*isolated.files, candidate),
    )


def record_message(
    workspace: ProjectWorkspace,
    message: ChatMessage,
) -> ProjectWorkspace:
    isolated = _workspace(workspace)
    candidate = ChatMessage.model_validate(message.model_dump(mode="python"))
    known_ids = {
        item.casefold()
        for item in (
            *isolated.session.artifact_ids,
            *isolated.session.decision_ids,
            *isolated.session.file_ids,
        )
    }
    if any(reference.casefold() not in known_ids for reference in candidate.references):
        raise ValueError("chat reference is not bound to the session")
    if candidate.message_id.casefold() in {
        item.message_id.casefold() for item in isolated.messages
    }:
        raise ValueError("message already exists")
    return _replace(isolated, messages=(*isolated.messages, candidate))


def record_approval_event(
    workspace: ProjectWorkspace,
    event: ApprovalEvent,
) -> ProjectWorkspace:
    isolated = _workspace(workspace)
    candidate = ApprovalEvent.model_validate(event.model_dump(mode="python"))
    if candidate.approval_id.casefold() in {
        item.approval_id.casefold() for item in isolated.approval_events
    }:
        raise ValueError("approval event already exists")
    return _replace(
        isolated,
        approval_events=(*isolated.approval_events, candidate),
    )


def record_knowledge_trace(
    workspace: ProjectWorkspace,
    trace: KnowledgeTrace,
) -> ProjectWorkspace:
    isolated = _workspace(workspace)
    candidate = KnowledgeTrace.model_validate(trace.model_dump(mode="python"))
    return _replace(
        isolated,
        knowledge_traces=(*isolated.knowledge_traces, candidate),
    )


def record_progress(
    workspace: ProjectWorkspace,
    snapshot: WorkflowProgress,
) -> ProjectWorkspace:
    isolated = _workspace(workspace)
    return _replace(
        isolated,
        progress=update_progress(isolated.progress, snapshot),
    )


def _workspace(workspace: ProjectWorkspace) -> ProjectWorkspace:
    if not isinstance(workspace, ProjectWorkspace):
        raise TypeError("workspace is invalid")
    return ProjectWorkspace.model_validate(
        copy.deepcopy(workspace.model_dump(mode="python"))
    )


def _session(context: DesignSessionContext) -> DesignSessionContext:
    if not isinstance(context, DesignSessionContext):
        raise TypeError("session context is invalid")
    return DesignSessionContext.model_validate(
        copy.deepcopy(context.model_dump(mode="python"))
    )


def _update_session_files(
    context: DesignSessionContext,
    file: WorkspaceFile,
) -> DesignSessionContext:
    if file.created_at <= context.updated_at:
        raise ValueError("file timestamp must follow the session update")
    payload = context.model_dump(mode="python")
    payload.update(
        file_ids=(*context.file_ids, file.file_id),
        updated_at=file.created_at,
    )
    return DesignSessionContext.model_validate(payload)


def _replace(workspace: ProjectWorkspace, **updates: object) -> ProjectWorkspace:
    payload = workspace.model_dump(mode="python")
    payload.update(updates)
    return ProjectWorkspace.model_validate(payload)


def _unique_ids(values: Iterable[str], *, field: str) -> None:
    identifiers = tuple(item.casefold() for item in values)
    if len(identifiers) != len(set(identifiers)):
        raise ValueError(f"workspace {field} identifiers are ambiguous")


def _stage_index(stage: DesignStage) -> int:
    return _STAGE_INDEX[stage]
