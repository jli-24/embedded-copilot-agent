"""Immutable, content-minimized Engineering Interface contracts."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])",
    re.IGNORECASE,
)


class _InterfaceContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
        hide_input_in_errors=True,
    )


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if _IDENTIFIER.fullmatch(candidate) is None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _safe_text(value: object, *, field: str, maximum: int) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not candidate or len(candidate) > maximum:
        raise ValueError(f"{field} is invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        raise ValueError(f"{field} is invalid")
    if _SENSITIVE.search(candidate) is not None:
        raise ValueError(f"{field} is invalid")
    return candidate


def _basename(value: object) -> str:
    candidate = _safe_text(value, field="basename", maximum=255)
    if candidate in {".", ".."} or any(marker in candidate for marker in ("/", "\\")):
        raise ValueError("basename is invalid")
    return candidate


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _references(value: object) -> tuple[str, ...]:
    values = _tuple(value, field="reference_ids")
    checked = tuple(_identifier(item, field="reference_id") for item in values)
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError("reference_ids must be sorted and unique")
    return checked


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _checked_fingerprint(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        encoded = value.astimezone(UTC).isoformat()
        return f"{encoded[:-6]}Z"
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        _jsonable(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class EngineeringChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class AttachmentProjectionType(StrEnum):
    IMAGE = "IMAGE"
    FILE = "FILE"


class EngineeringProgressSource(StrEnum):
    INTERFACE = "INTERFACE"
    WORKFLOW = "WORKFLOW"
    HUMAN_LOOP = "HUMAN_LOOP"


def engineering_project_fingerprint(
    *,
    project_id: str,
    name: str,
    summary: str,
    reference_ids: tuple[str, ...],
) -> str:
    return _fingerprint(
        {
            "project_id": project_id,
            "name": name,
            "summary": summary,
            "reference_ids": reference_ids,
        }
    )


class EngineeringProjectProjection(_InterfaceContract):
    project_id: str
    name: str
    summary: str
    reference_ids: tuple[str, ...] = ()
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _name = field_validator("name")(
        lambda value: _safe_text(value, field="name", maximum=128)
    )
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringProjectProjection:
        if self.fingerprint != engineering_project_fingerprint(
            project_id=self.project_id,
            name=self.name,
            summary=self.summary,
            reference_ids=self.reference_ids,
        ):
            raise ValueError("project fingerprint mismatch")
        return self


class EngineeringSessionCreateRequest(_InterfaceContract):
    session_id: str
    title: str
    project: EngineeringProjectProjection
    created_at: datetime

    _session_id = field_validator("session_id")(
        lambda value: _identifier(value, field="session_id")
    )
    _title = field_validator("title")(
        lambda value: _safe_text(value, field="title", maximum=128)
    )
    _created_at = field_validator("created_at")(
        lambda value: _utc(value, field="created_at")
    )


class EngineeringChatRequest(_InterfaceContract):
    session_id: str
    message_id: str
    role: EngineeringChatRole
    summary: str
    reference_ids: tuple[str, ...] = ()
    timestamp: datetime

    @field_validator("session_id", "message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )


def _message_fingerprint(request: EngineeringChatRequest) -> str:
    return _fingerprint(
        {
            "session_id": request.session_id,
            "message_id": request.message_id,
            "role": request.role,
            "summary": request.summary,
            "reference_ids": request.reference_ids,
            "timestamp": request.timestamp,
        }
    )


class EngineeringMessageProjection(_InterfaceContract):
    session_id: str
    message_id: str
    role: EngineeringChatRole
    summary: str
    reference_ids: tuple[str, ...]
    timestamp: datetime
    fingerprint: str

    @field_validator("session_id", "message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringMessageProjection:
        request = EngineeringChatRequest(
            session_id=self.session_id,
            message_id=self.message_id,
            role=self.role,
            summary=self.summary,
            reference_ids=self.reference_ids,
            timestamp=self.timestamp,
        )
        if self.fingerprint != _message_fingerprint(request):
            raise ValueError("message fingerprint mismatch")
        return self


class AttachmentProjectionRequest(_InterfaceContract):
    session_id: str
    reference_id: str
    type: AttachmentProjectionType
    basename: str
    summary: str
    size_bytes: int = Field(ge=0, le=1_048_576)
    timestamp: datetime

    @field_validator("session_id", "reference_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _basename_value = field_validator("basename")(_basename)
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=512)
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, value: int) -> int:
        if type(value) is not int:
            raise ValueError("size_bytes is invalid")
        return value


def _attachment_fingerprint(request: AttachmentProjectionRequest) -> str:
    return _fingerprint(request)


class EngineeringAttachmentProjection(_InterfaceContract):
    session_id: str
    reference_id: str
    type: AttachmentProjectionType
    basename: str
    summary: str
    size_bytes: int = Field(ge=0, le=1_048_576)
    timestamp: datetime
    fingerprint: str

    @field_validator("session_id", "reference_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _basename_value = field_validator("basename")(_basename)
    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=512)
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, value: int) -> int:
        if type(value) is not int:
            raise ValueError("size_bytes is invalid")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringAttachmentProjection:
        request = AttachmentProjectionRequest(
            session_id=self.session_id,
            reference_id=self.reference_id,
            type=self.type,
            basename=self.basename,
            summary=self.summary,
            size_bytes=self.size_bytes,
            timestamp=self.timestamp,
        )
        if self.fingerprint != _attachment_fingerprint(request):
            raise ValueError("attachment fingerprint mismatch")
        return self


class EngineeringWorkflowPreparationRequest(_InterfaceContract):
    session_id: str
    workflow_id: str
    source_message_id: str
    requested_at: datetime

    @field_validator("session_id", "workflow_id", "source_message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _requested_at = field_validator("requested_at")(
        lambda value: _utc(value, field="requested_at")
    )


def _workflow_projection_fingerprint(
    *,
    workflow_id: str,
    source_message_id: str,
    state: str,
    task_count: int,
    risk_count: int,
    review_required: bool,
    source_snapshot_fingerprint: str,
) -> str:
    return _fingerprint(
        {
            "workflow_id": workflow_id,
            "source_message_id": source_message_id,
            "state": state,
            "task_count": task_count,
            "risk_count": risk_count,
            "review_required": review_required,
            "source_snapshot_fingerprint": source_snapshot_fingerprint,
        }
    )


class EngineeringWorkflowUIProjection(_InterfaceContract):
    workflow_id: str
    source_message_id: str
    state: str
    task_count: int = Field(ge=1, le=128)
    risk_count: int = Field(ge=0, le=128)
    review_required: bool
    source_snapshot_fingerprint: str
    fingerprint: str

    @field_validator("workflow_id", "source_message_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _state = field_validator("state")(lambda value: _token(value, field="state"))
    _source_fingerprint = field_validator("source_snapshot_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator("task_count", "risk_count")
    @classmethod
    def validate_counts(cls, value: int, info) -> int:
        minimum = 1 if info.field_name == "task_count" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("review_required")
    @classmethod
    def validate_review_required(cls, value: bool) -> bool:
        if type(value) is not bool:
            raise ValueError("review_required is invalid")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringWorkflowUIProjection:
        expected = _workflow_projection_fingerprint(
            workflow_id=self.workflow_id,
            source_message_id=self.source_message_id,
            state=self.state,
            task_count=self.task_count,
            risk_count=self.risk_count,
            review_required=self.review_required,
            source_snapshot_fingerprint=self.source_snapshot_fingerprint,
        )
        if self.fingerprint != expected:
            raise ValueError("workflow projection fingerprint mismatch")
        return self


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _progress_fingerprint(
    *,
    sequence: int,
    session_id: str,
    source: EngineeringProgressSource,
    source_reference_id: str,
    source_sequence: int,
    event: str,
    state: str,
    count: int,
    timestamp: datetime,
) -> str:
    return _fingerprint(
        {
            "sequence": sequence,
            "session_id": session_id,
            "source": source,
            "source_reference_id": source_reference_id,
            "source_sequence": source_sequence,
            "event": event,
            "state": state,
            "count": count,
            "timestamp": timestamp,
        }
    )


class EngineeringProgressEvent(_InterfaceContract):
    sequence: int = Field(ge=1, le=512)
    session_id: str
    source: EngineeringProgressSource
    source_reference_id: str
    source_sequence: int = Field(ge=1)
    event: str
    state: str
    count: int = Field(ge=0)
    timestamp: datetime
    fingerprint: str

    @field_validator("session_id", "source_reference_id")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("sequence", "source_sequence", "count")
    @classmethod
    def validate_counts(cls, value: int, info) -> int:
        minimum = 0 if info.field_name == "count" else 1
        if type(value) is not int or value < minimum:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("event", "state")
    @classmethod
    def validate_tokens(cls, value: object, info) -> str:
        return _token(value, field=info.field_name)

    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringProgressEvent:
        expected = _progress_fingerprint(
            sequence=self.sequence,
            session_id=self.session_id,
            source=self.source,
            source_reference_id=self.source_reference_id,
            source_sequence=self.source_sequence,
            event=self.event,
            state=self.state,
            count=self.count,
            timestamp=self.timestamp,
        )
        if self.fingerprint != expected:
            raise ValueError("progress fingerprint mismatch")
        return self


def _human_review_fingerprint(
    *,
    proposal_id: str,
    artifact_type: str,
    artifact_version: int,
    summary: str,
    reference_ids: tuple[str, ...],
    state: str,
    decision: str,
    reviewer: str,
    reviewed_at: datetime,
    source_snapshot_fingerprint: str,
) -> str:
    return _fingerprint(
        {
            "proposal_id": proposal_id,
            "artifact_type": artifact_type,
            "artifact_version": artifact_version,
            "summary": summary,
            "reference_ids": reference_ids,
            "state": state,
            "decision": decision,
            "reviewer": reviewer,
            "reviewed_at": reviewed_at,
            "source_snapshot_fingerprint": source_snapshot_fingerprint,
        }
    )


class HumanReviewUIProjection(_InterfaceContract):
    proposal_id: str
    artifact_type: str
    artifact_version: int = Field(ge=1)
    summary: str
    reference_ids: tuple[str, ...]
    state: str
    decision: str
    reviewer: str
    reviewed_at: datetime
    source_snapshot_fingerprint: str
    fingerprint: str

    @field_validator("proposal_id", "reviewer")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("artifact_type", "state", "decision")
    @classmethod
    def validate_tokens(cls, value: object, info) -> str:
        return _token(value, field=info.field_name)

    @field_validator("artifact_version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("artifact_version is invalid")
        return value

    _summary = field_validator("summary")(
        lambda value: _safe_text(value, field="summary", maximum=1024)
    )
    _reference_ids = field_validator("reference_ids", mode="before")(_references)
    _reviewed_at = field_validator("reviewed_at")(
        lambda value: _utc(value, field="reviewed_at")
    )
    _source_fingerprint = field_validator("source_snapshot_fingerprint")(
        _checked_fingerprint
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> HumanReviewUIProjection:
        expected = _human_review_fingerprint(
            proposal_id=self.proposal_id,
            artifact_type=self.artifact_type,
            artifact_version=self.artifact_version,
            summary=self.summary,
            reference_ids=self.reference_ids,
            state=self.state,
            decision=self.decision,
            reviewer=self.reviewer,
            reviewed_at=self.reviewed_at,
            source_snapshot_fingerprint=self.source_snapshot_fingerprint,
        )
        if self.fingerprint != expected:
            raise ValueError("human review projection fingerprint mismatch")
        return self


def engineering_session_fingerprint(
    *,
    session_id: str,
    title: str,
    project: EngineeringProjectProjection,
    created_at: datetime,
    updated_at: datetime,
    messages: tuple[EngineeringMessageProjection, ...],
    attachments: tuple[EngineeringAttachmentProjection, ...],
    workflows: tuple[EngineeringWorkflowUIProjection, ...],
    human_reviews: tuple[HumanReviewUIProjection, ...],
    progress_events: tuple[EngineeringProgressEvent, ...],
) -> str:
    return _fingerprint(
        {
            "session_id": session_id,
            "title": title,
            "project": project,
            "created_at": created_at,
            "updated_at": updated_at,
            "messages": messages,
            "attachments": attachments,
            "workflows": workflows,
            "human_reviews": human_reviews,
            "progress_events": progress_events,
        }
    )


class EngineeringSessionSnapshot(_InterfaceContract):
    session_id: str
    title: str
    project: EngineeringProjectProjection
    created_at: datetime
    updated_at: datetime
    messages: tuple[EngineeringMessageProjection, ...] = Field(max_length=256)
    attachments: tuple[EngineeringAttachmentProjection, ...] = Field(max_length=64)
    workflows: tuple[EngineeringWorkflowUIProjection, ...] = Field(max_length=64)
    human_reviews: tuple[HumanReviewUIProjection, ...] = Field(max_length=64)
    progress_events: tuple[EngineeringProgressEvent, ...] = Field(max_length=512)
    fingerprint: str

    _session_id = field_validator("session_id")(
        lambda value: _identifier(value, field="session_id")
    )
    _title = field_validator("title")(
        lambda value: _safe_text(value, field="title", maximum=128)
    )
    _created_at = field_validator("created_at")(
        lambda value: _utc(value, field="created_at")
    )
    _updated_at = field_validator("updated_at")(
        lambda value: _utc(value, field="updated_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @field_validator(
        "messages",
        "attachments",
        "workflows",
        "human_reviews",
        "progress_events",
        mode="before",
    )
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_snapshot(self) -> EngineeringSessionSnapshot:
        if self.updated_at < self.created_at:
            raise ValueError("session time binding is invalid")
        message_keys = tuple(
            (item.timestamp, item.message_id) for item in self.messages
        )
        if message_keys != tuple(sorted(message_keys)) or len(message_keys) != len(
            set(message_keys)
        ):
            raise ValueError("messages must be sorted and unique")
        for field_name, values, key_name in (
            ("attachments", self.attachments, "reference_id"),
            ("workflows", self.workflows, "workflow_id"),
            ("human_reviews", self.human_reviews, "proposal_id"),
        ):
            keys = tuple(getattr(item, key_name) for item in values)
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                raise ValueError(f"{field_name} must be sorted and unique")
        if any(item.session_id != self.session_id for item in self.messages):
            raise ValueError("message session binding is invalid")
        if any(item.session_id != self.session_id for item in self.attachments):
            raise ValueError("attachment session binding is invalid")
        sequences = tuple(item.sequence for item in self.progress_events)
        if sequences != tuple(range(1, len(sequences) + 1)):
            raise ValueError("progress sequence is invalid")
        if any(item.session_id != self.session_id for item in self.progress_events):
            raise ValueError("progress session binding is invalid")
        expected = engineering_session_fingerprint(
            session_id=self.session_id,
            title=self.title,
            project=self.project,
            created_at=self.created_at,
            updated_at=self.updated_at,
            messages=self.messages,
            attachments=self.attachments,
            workflows=self.workflows,
            human_reviews=self.human_reviews,
            progress_events=self.progress_events,
        )
        if self.fingerprint != expected:
            raise ValueError("session fingerprint mismatch")
        return self


def make_message_projection(
    request: EngineeringChatRequest,
) -> EngineeringMessageProjection:
    return EngineeringMessageProjection(
        session_id=request.session_id,
        message_id=request.message_id,
        role=request.role,
        summary=request.summary,
        reference_ids=request.reference_ids,
        timestamp=request.timestamp,
        fingerprint=_message_fingerprint(request),
    )


def make_attachment_projection(
    request: AttachmentProjectionRequest,
) -> EngineeringAttachmentProjection:
    return EngineeringAttachmentProjection(
        session_id=request.session_id,
        reference_id=request.reference_id,
        type=request.type,
        basename=request.basename,
        summary=request.summary,
        size_bytes=request.size_bytes,
        timestamp=request.timestamp,
        fingerprint=_attachment_fingerprint(request),
    )


def make_workflow_projection(
    *,
    workflow_id: str,
    source_message_id: str,
    state: str,
    task_count: int,
    risk_count: int,
    review_required: bool,
    source_snapshot_fingerprint: str,
) -> EngineeringWorkflowUIProjection:
    values = dict(
        workflow_id=workflow_id,
        source_message_id=source_message_id,
        state=state,
        task_count=task_count,
        risk_count=risk_count,
        review_required=review_required,
        source_snapshot_fingerprint=source_snapshot_fingerprint,
    )
    return EngineeringWorkflowUIProjection(
        **values,
        fingerprint=_workflow_projection_fingerprint(**values),
    )


def make_progress_event(
    *,
    sequence: int,
    session_id: str,
    source: EngineeringProgressSource,
    source_reference_id: str,
    source_sequence: int,
    event: str,
    state: str,
    count: int,
    timestamp: datetime,
) -> EngineeringProgressEvent:
    values = dict(
        sequence=sequence,
        session_id=session_id,
        source=source,
        source_reference_id=source_reference_id,
        source_sequence=source_sequence,
        event=event,
        state=state,
        count=count,
        timestamp=timestamp,
    )
    return EngineeringProgressEvent(
        **values,
        fingerprint=_progress_fingerprint(**values),
    )


def make_human_review_projection(
    *,
    proposal_id: str,
    artifact_type: str,
    artifact_version: int,
    summary: str,
    reference_ids: tuple[str, ...],
    state: str,
    decision: str,
    reviewer: str,
    reviewed_at: datetime,
    source_snapshot_fingerprint: str,
) -> HumanReviewUIProjection:
    values = dict(
        proposal_id=proposal_id,
        artifact_type=artifact_type,
        artifact_version=artifact_version,
        summary=summary,
        reference_ids=reference_ids,
        state=state,
        decision=decision,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        source_snapshot_fingerprint=source_snapshot_fingerprint,
    )
    return HumanReviewUIProjection(
        **values,
        fingerprint=_human_review_fingerprint(**values),
    )
