"""Strict immutable DTOs for the Web Console boundary."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from embedded_copilot.conversation_feedback import FeedbackType

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FP = re.compile(r"^sha256:[0-9a-f]{64}$")
_BASENAME = re.compile(r"^[^/\\\x00]{1,255}$")


class _WebModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        revalidate_instances="always",
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def canonical_web_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(kind: str, **values: object) -> str:
    payload = canonical_web_json({"kind": kind, **values}).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _values(model: BaseModel) -> dict[str, object]:
    return {
        name: getattr(model, name)
        for name in type(model).model_fields
        if name != "fingerprint"
    }


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _text(value: object, *, field: str, maximum: int = 4096) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} is invalid")
    return value


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _http_utc(value: object, *, field: str) -> datetime:
    """Parse the ISO-8601 representation used at the HTTP JSON boundary."""
    if type(value) is str:
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{field} must be an ISO-8601 datetime") from None
    return _utc(value, field=field)


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _fp(value: object) -> str:
    if type(value) is not str or _FP.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


class WebStage(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    ARCHITECTURE = "ARCHITECTURE"
    HARDWARE = "HARDWARE"
    FIRMWARE = "FIRMWARE"
    VALIDATION = "VALIDATION"
    ARTIFACT = "ARTIFACT"
    EXECUTION = "EXECUTION"
    FEEDBACK = "FEEDBACK"
    OPTIMIZATION = "OPTIMIZATION"


class WebStageStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class WebAttachmentType(StrEnum):
    DATASHEET_PDF = "DATASHEET_PDF"
    CODE = "CODE"
    LOG = "LOG"
    PCB_IMAGE = "PCB_IMAGE"
    SCHEMATIC_IMAGE = "SCHEMATIC_IMAGE"


class WebProjectCreateRequest(_WebModel):
    requirement: str

    _requirement = field_validator("requirement")(
        lambda value: _text(value, field="requirement")
    )

    @computed_field
    @property
    def fingerprint(self) -> str:
        return _fingerprint(type(self).__name__, requirement=self.requirement)


class WebChatRequest(_WebModel):
    message: str
    project_id: str | None = None
    request_id: str | None = None
    requested_at: datetime | None = None

    _message = field_validator("message")(lambda value: _text(value, field="message"))

    @field_validator("project_id", "request_id")
    @classmethod
    def validate_optional_ids(cls, value: object, info) -> str | None:
        if value is None:
            return None
        return _identifier(value, field=info.field_name)

    @field_validator("requested_at", mode="before")
    @classmethod
    def validate_optional_requested_at(cls, value: object) -> datetime | None:
        if value is None:
            return None
        return _http_utc(value, field="requested_at")

    @model_validator(mode="after")
    def validate_project_chat_binding(self) -> WebChatRequest:
        optional = (self.project_id, self.request_id, self.requested_at)
        if any(value is not None for value in optional) and any(
            value is None for value in optional
        ):
            raise ValueError("project chat binding is incomplete")
        return self

    @computed_field
    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            type(self).__name__,
            message=self.message,
            project_id=self.project_id,
            request_id=self.request_id,
            requested_at=self.requested_at,
        )


class WebFeedbackRequest(_WebModel):
    feedback_id: str
    project_id: str
    target_agent: str
    feedback_type: FeedbackType
    message: str
    timestamp: datetime

    @field_validator("feedback_id", "project_id")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("target_agent")
    @classmethod
    def validate_target_agent(cls, value: object) -> str:
        return _token(value, field="target_agent")

    @field_validator("feedback_type", mode="before")
    @classmethod
    def validate_feedback_type(cls, value: object) -> FeedbackType:
        if type(value) is FeedbackType:
            return value
        if type(value) is str:
            try:
                return FeedbackType(value)
            except ValueError:
                pass
        raise ValueError("feedback_type is invalid")

    _message = field_validator("message")(
        lambda value: _text(value, field="message")
    )
    _timestamp = field_validator("timestamp", mode="before")(
        lambda value: _http_utc(value, field="timestamp")
    )

    @computed_field
    @property
    def fingerprint(self) -> str:
        return _fingerprint(
            type(self).__name__,
            feedback_id=self.feedback_id,
            project_id=self.project_id,
            target_agent=self.target_agent,
            feedback_type=self.feedback_type,
            message=self.message,
            timestamp=self.timestamp,
        )


class WebAttachmentMetadataRequest(_WebModel):
    reference_id: str
    attachment_type: WebAttachmentType
    basename: str
    summary: str
    size_bytes: int = Field(ge=0, le=1_048_576)
    observed_at: datetime

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _summary = field_validator("summary")(
        lambda value: _text(value, field="summary", maximum=512)
    )
    _observed_at = field_validator("observed_at")(
        lambda value: _utc(value, field="observed_at")
    )

    @field_validator("basename")
    @classmethod
    def validate_basename(cls, value: object) -> str:
        if type(value) is not str or _BASENAME.fullmatch(value) is None:
            raise ValueError("basename is invalid")
        return value

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("size_bytes is invalid")
        return value

    @computed_field
    @property
    def fingerprint(self) -> str:
        return _fingerprint(type(self).__name__, **_values(self))


class WebAttachmentProjectionRequest(_WebModel):
    project_id: str
    session_id: str
    reference_id: str
    attachment_type: WebAttachmentType
    basename: str
    summary: str
    size_bytes: int = Field(ge=0, le=1_048_576)
    observed_at: datetime

    @field_validator("project_id", "session_id", "reference_id")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _summary = field_validator("summary")(
        lambda value: _text(value, field="summary", maximum=512)
    )
    _observed_at = field_validator("observed_at")(
        lambda value: _utc(value, field="observed_at")
    )

    @field_validator("basename")
    @classmethod
    def validate_basename(cls, value: object) -> str:
        if type(value) is not str or _BASENAME.fullmatch(value) is None:
            raise ValueError("basename is invalid")
        return value

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("size_bytes is invalid")
        return value

    @computed_field
    @property
    def fingerprint(self) -> str:
        return _fingerprint(type(self).__name__, **_values(self))


class _FingerprintModel(_WebModel):
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fp)

    def _check(self, function) -> None:
        if self.fingerprint != function(**_values(self)):
            raise ValueError("web fingerprint mismatch")


class WebProjectReference(_FingerprintModel):
    project_id: str
    project_name: str
    current_stage: WebStage
    workspace_fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _project_name = field_validator("project_name")(
        lambda value: _text(value, field="project_name", maximum=128)
    )
    _workspace = field_validator("workspace_fingerprint")(_fp)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebProjectReference:
        self._check(web_project_reference_fingerprint)
        return self


def web_project_reference_fingerprint(**values: object) -> str:
    return _fingerprint("WebProjectReference", **values)


class WebProjectDetail(_FingerprintModel):
    project: WebProjectReference
    artifact_reference_ids: tuple[str, ...]
    execution_reference_ids: tuple[str, ...]
    feedback_reference_ids: tuple[str, ...]
    optimization_reference_ids: tuple[str, ...]

    @field_validator(
        "artifact_reference_ids",
        "execution_reference_ids",
        "feedback_reference_ids",
        "optimization_reference_ids",
        mode="before",
    )
    @classmethod
    def validate_references(cls, value: object, info) -> object:
        value = _tuple(value, field=info.field_name)
        keys = tuple(_identifier(item, field=info.field_name) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError(f"{info.field_name} must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebProjectDetail:
        self._check(web_project_detail_fingerprint)
        return self


def web_project_detail_fingerprint(**values: object) -> str:
    return _fingerprint("WebProjectDetail", **values)


class WebStageProjection(_FingerprintModel):
    stage: WebStage
    status: WebStageStatus
    reference_ids: tuple[str, ...]

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        return _tuple(value, field="reference_ids")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebStageProjection:
        self._check(web_stage_fingerprint)
        return self


def web_stage_fingerprint(**values: object) -> str:
    return _fingerprint("WebStageProjection", **values)


class WebDashboardProjection(_FingerprintModel):
    project_id: str
    project_name: str
    current_stage: WebStage
    overall_progress: float = Field(ge=0.0, le=100.0)
    stages: tuple[WebStageProjection, ...]

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _project_name = field_validator("project_name")(
        lambda value: _text(value, field="project_name", maximum=128)
    )

    @field_validator("stages", mode="before")
    @classmethod
    def validate_stages(cls, value: object) -> object:
        return _tuple(value, field="stages")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebDashboardProjection:
        if tuple(item.stage for item in self.stages) != tuple(WebStage):
            raise ValueError("dashboard stages are invalid")
        self._check(web_dashboard_fingerprint)
        return self


def web_dashboard_fingerprint(**values: object) -> str:
    return _fingerprint("WebDashboardProjection", **values)


class WebTimelineEventProjection(_FingerprintModel):
    event: str
    reference_id: str
    reference_type: str
    timestamp: datetime
    source_fingerprint: str

    _event = field_validator("event")(lambda value: _identifier(value, field="event"))
    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _reference_type = field_validator("reference_type")(
        lambda value: _identifier(value, field="reference_type")
    )
    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _source = field_validator("source_fingerprint")(_fp)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebTimelineEventProjection:
        self._check(web_timeline_event_fingerprint)
        return self


def web_timeline_event_fingerprint(**values: object) -> str:
    return _fingerprint("WebTimelineEventProjection", **values)


class WebTimelineProjection(_FingerprintModel):
    project_id: str
    events: tuple[WebTimelineEventProjection, ...]

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )

    @field_validator("events", mode="before")
    @classmethod
    def validate_events(cls, value: object) -> object:
        return _tuple(value, field="events")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebTimelineProjection:
        self._check(web_timeline_fingerprint)
        return self


def web_timeline_fingerprint(**values: object) -> str:
    return _fingerprint("WebTimelineProjection", **values)


class WebReportSection(_FingerprintModel):
    stage: WebStage
    status: WebStageStatus
    reference_ids: tuple[str, ...]
    source_fingerprints: tuple[str, ...]

    @field_validator("reference_ids", "source_fingerprints", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebReportSection:
        self._check(web_report_section_fingerprint)
        return self


def web_report_section_fingerprint(**values: object) -> str:
    return _fingerprint("WebReportSection", **values)


class WebReviewProjection(_FingerprintModel):
    pending_reviews: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)
    change_requests: int = Field(ge=0)
    reference_ids: tuple[str, ...]

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        return _tuple(value, field="reference_ids")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebReviewProjection:
        self._check(web_review_fingerprint)
        return self


def web_review_fingerprint(**values: object) -> str:
    return _fingerprint("WebReviewProjection", **values)


class WebReportProjection(_FingerprintModel):
    project_id: str
    project_name: str
    project_summary: str
    sections: tuple[WebReportSection, ...]
    decision_ids: tuple[str, ...]
    review: WebReviewProjection
    generated_at: datetime
    source_fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _project_name = field_validator("project_name")(
        lambda value: _text(value, field="project_name", maximum=128)
    )
    _project_summary = field_validator("project_summary")(
        lambda value: _text(value, field="project_summary", maximum=512)
    )
    _generated = field_validator("generated_at")(
        lambda value: _utc(value, field="generated_at")
    )
    _source = field_validator("source_fingerprint")(_fp)

    @field_validator("sections", "decision_ids", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebReportProjection:
        self._check(web_report_fingerprint)
        return self


def web_report_fingerprint(**values: object) -> str:
    return _fingerprint("WebReportProjection", **values)


class WebAttachmentProjection(_FingerprintModel):
    project_id: str
    session_id: str
    reference_id: str
    attachment_type: WebAttachmentType
    basename: str
    summary: str
    size_bytes: int
    observed_at: datetime
    source_fingerprint: str

    @field_validator("project_id", "session_id", "reference_id")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    _summary = field_validator("summary")(
        lambda value: _text(value, field="summary", maximum=512)
    )
    _observed = field_validator("observed_at")(
        lambda value: _utc(value, field="observed_at")
    )
    _source = field_validator("source_fingerprint")(_fp)

    @field_validator("basename")
    @classmethod
    def validate_basename(cls, value: object) -> str:
        if type(value) is not str or _BASENAME.fullmatch(value) is None:
            raise ValueError("basename is invalid")
        return value

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, value: object) -> int:
        if type(value) is not int:
            raise ValueError("size_bytes is invalid")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebAttachmentProjection:
        self._check(web_attachment_fingerprint)
        return self


def web_attachment_fingerprint(**values: object) -> str:
    return _fingerprint("WebAttachmentProjection", **values)


class WebChatResponse(_FingerprintModel):
    project: WebProjectReference
    message: str
    current_stage: WebStage

    _message = field_validator("message")(
        lambda value: _text(value, field="message", maximum=128)
    )

    @model_validator(mode="after")
    def validate_fingerprint(self) -> WebChatResponse:
        self._check(web_chat_response_fingerprint)
        return self


def web_chat_response_fingerprint(**values: object) -> str:
    return _fingerprint("WebChatResponse", **values)


class WebErrorResponse(_WebModel):
    code: str
    message: str

    _code = field_validator("code")(lambda value: _identifier(value, field="code"))
    _message = field_validator("message")(
        lambda value: _text(value, field="message", maximum=128)
    )

    @computed_field
    @property
    def fingerprint(self) -> str:
        return _fingerprint(type(self).__name__, code=self.code, message=self.message)
