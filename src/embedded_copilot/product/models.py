"""Immutable Product Layer presentation contracts."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FP = re.compile(r"^sha256:[0-9a-f]{64}$")


class _ProductModel(BaseModel):
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


def canonical_product_json(value: object) -> str:
    return json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(kind: str, **values: object) -> str:
    content = canonical_product_json({"kind": kind, **values}).encode("utf-8")
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _identifier(value: object, *, field: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _token(value: object, *, field: str) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def _text(value: object, *, field: str, limit: int = 512) -> str:
    if type(value) is not str or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} is invalid")
    return value


def _fp(value: object) -> str:
    if type(value) is not str or _FP.fullmatch(value) is None:
        raise ValueError("fingerprint is invalid")
    return value


def _utc(value: object, *, field: str) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> object:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _values(model: BaseModel) -> dict[str, object]:
    return {
        name: getattr(model, name)
        for name in type(model).model_fields
        if name != "fingerprint"
    }


class ProductStage(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    ARCHITECTURE = "ARCHITECTURE"
    HARDWARE = "HARDWARE"
    FIRMWARE = "FIRMWARE"
    VALIDATION = "VALIDATION"
    ARTIFACT = "ARTIFACT"
    EXECUTION = "EXECUTION"
    FEEDBACK = "FEEDBACK"
    OPTIMIZATION = "OPTIMIZATION"


class ProductStageStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"


class ProductReferenceType(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    ARCHITECTURE = "ARCHITECTURE"
    CONTEXT = "CONTEXT"
    HARDWARE = "HARDWARE"
    FIRMWARE = "FIRMWARE"
    VALIDATION = "VALIDATION"
    ARTIFACT = "ARTIFACT"
    EXECUTION = "EXECUTION"
    FEEDBACK = "FEEDBACK"
    OPTIMIZATION = "OPTIMIZATION"


class ProductTimelineEventType(StrEnum):
    REQUIREMENT_COMPLETED = "REQUIREMENT_COMPLETED"
    ARCHITECTURE_COMPLETED = "ARCHITECTURE_COMPLETED"
    HARDWARE_PROPOSAL_GENERATED = "HARDWARE_PROPOSAL_GENERATED"
    FIRMWARE_PROPOSAL_GENERATED = "FIRMWARE_PROPOSAL_GENERATED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    ARTIFACT_GENERATED = "ARTIFACT_GENERATED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    FEEDBACK_RECEIVED = "FEEDBACK_RECEIVED"
    OPTIMIZATION_GENERATED = "OPTIMIZATION_GENERATED"


class ProductDecisionOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class ProductReference(_ProductModel):
    reference_type: ProductReferenceType
    reference_id: str
    source_fingerprint: str
    fingerprint: str

    _reference_id = field_validator("reference_id")(
        lambda value: _identifier(value, field="reference_id")
    )
    _source = field_validator("source_fingerprint")(_fp)
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> ProductReference:
        if self.fingerprint != product_reference_fingerprint(**_values(self)):
            raise ValueError("product reference fingerprint mismatch")
        return self


def product_reference_fingerprint(**values: object) -> str:
    return _fingerprint("ProductReference", **values)


class ProductStageReference(_ProductModel):
    stage: ProductStage
    status: ProductStageStatus
    references: tuple[ProductReference, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("references", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        return _tuple(value, field="references")

    @model_validator(mode="after")
    def validate_stage(self) -> ProductStageReference:
        keys = tuple(item.reference_type for item in self.references)
        order = {value: index for index, value in enumerate(ProductReferenceType)}
        indexes = tuple(order[item] for item in keys)
        if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
            raise ValueError("stage references must be sorted and unique")
        if self.status in {
            ProductStageStatus.NOT_STARTED,
            ProductStageStatus.IN_PROGRESS,
        }:
            if self.references:
                raise ValueError("inactive stage cannot contain references")
        elif not self.references:
            raise ValueError("active stage requires references")
        if self.fingerprint != product_stage_reference_fingerprint(**_values(self)):
            raise ValueError("stage reference fingerprint mismatch")
        return self


def product_stage_reference_fingerprint(**values: object) -> str:
    return _fingerprint("ProductStageReference", **values)


class ProjectSession(_ProductModel):
    project_id: str
    session_id: str
    current_stage: ProductStage
    artifact_references: tuple[ProductReference, ...]
    execution_references: tuple[ProductReference, ...]
    feedback_references: tuple[ProductReference, ...]
    optimization_references: tuple[ProductReference, ...]
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _session_id = field_validator("session_id")(
        lambda value: _identifier(value, field="session_id")
    )
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator(
        "artifact_references",
        "execution_references",
        "feedback_references",
        "optimization_references",
        mode="before",
    )
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> ProjectSession:
        if self.fingerprint != project_session_fingerprint(**_values(self)):
            raise ValueError("project session fingerprint mismatch")
        return self


def project_session_fingerprint(**values: object) -> str:
    return _fingerprint("ProjectSession", **values)


class EngineeringTimelineEvent(_ProductModel):
    event_type: ProductTimelineEventType
    reference: ProductReference
    timestamp: datetime
    fingerprint: str

    _timestamp = field_validator("timestamp")(
        lambda value: _utc(value, field="timestamp")
    )
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringTimelineEvent:
        if self.fingerprint != timeline_event_fingerprint(**_values(self)):
            raise ValueError("timeline event fingerprint mismatch")
        return self


def timeline_event_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringTimelineEvent", **values)


class EngineeringTimelineProjection(_ProductModel):
    events: tuple[EngineeringTimelineEvent, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("events", mode="before")
    @classmethod
    def validate_events(cls, value: object) -> object:
        return _tuple(value, field="events")

    @model_validator(mode="after")
    def validate_timeline(self) -> EngineeringTimelineProjection:
        order = {value: index for index, value in enumerate(ProductTimelineEventType)}
        keys = tuple(order[item.event_type] for item in self.events)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("timeline events must be sorted and unique")
        if self.fingerprint != timeline_projection_fingerprint(**_values(self)):
            raise ValueError("timeline fingerprint mismatch")
        return self


def timeline_projection_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringTimelineProjection", **values)


class ProductDecisionProjection(_ProductModel):
    decision_id: str
    decision: str
    reason: str
    evidence_references: tuple[str, ...]
    feedback_references: tuple[str, ...]
    outcome: ProductDecisionOutcome
    fingerprint: str

    _decision_id = field_validator("decision_id")(
        lambda value: _identifier(value, field="decision_id")
    )
    _decision = field_validator("decision")(
        lambda value: _token(value, field="decision")
    )
    _reason = field_validator("reason")(lambda value: _token(value, field="reason"))
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("evidence_references", "feedback_references", mode="before")
    @classmethod
    def validate_reference_tuples(cls, value: object, info) -> object:
        value = _tuple(value, field=info.field_name)
        keys = tuple(_identifier(item, field=info.field_name) for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError(f"{info.field_name} must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> ProductDecisionProjection:
        if self.fingerprint != product_decision_fingerprint(**_values(self)):
            raise ValueError("product decision fingerprint mismatch")
        return self


def product_decision_fingerprint(**values: object) -> str:
    return _fingerprint("ProductDecisionProjection", **values)


class ReviewDashboardProjection(_ProductModel):
    pending_reviews: int = Field(ge=0)
    approved: int = Field(ge=0)
    rejected: int = Field(ge=0)
    change_requests: int = Field(ge=0)
    reference_ids: tuple[str, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        value = _tuple(value, field="reference_ids")
        keys = tuple(_identifier(item, field="reference_ids") for item in value)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("review references must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> ReviewDashboardProjection:
        if self.fingerprint != review_dashboard_fingerprint(**_values(self)):
            raise ValueError("review dashboard fingerprint mismatch")
        return self


def review_dashboard_fingerprint(**values: object) -> str:
    return _fingerprint("ReviewDashboardProjection", **values)


class EngineeringWorkspace(_ProductModel):
    project_id: str
    project_name: str
    project_summary: str
    session: ProjectSession
    stage_references: tuple[ProductStageReference, ...]
    timeline: EngineeringTimelineProjection
    decisions: tuple[ProductDecisionProjection, ...]
    review_dashboard: ReviewDashboardProjection
    created_at: datetime
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _name = field_validator("project_name")(
        lambda value: _text(value, field="project_name", limit=128)
    )
    _summary = field_validator("project_summary")(
        lambda value: _text(value, field="project_summary")
    )
    _created_at = field_validator("created_at")(
        lambda value: _utc(value, field="created_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("stage_references", "decisions", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_workspace(self) -> EngineeringWorkspace:
        if tuple(item.stage for item in self.stage_references) != tuple(ProductStage):
            raise ValueError("workspace stages are invalid")
        decision_ids = tuple(item.decision_id for item in self.decisions)
        if decision_ids != tuple(sorted(decision_ids)) or len(decision_ids) != len(
            set(decision_ids)
        ):
            raise ValueError("workspace decisions must be sorted and unique")
        if self.session.project_id != self.project_id:
            raise ValueError("workspace session binding mismatch")
        if self.fingerprint != engineering_workspace_fingerprint(**_values(self)):
            raise ValueError("workspace fingerprint mismatch")
        return self


def engineering_workspace_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringWorkspace", **values)


class DashboardStageProjection(_ProductModel):
    stage: ProductStage
    status: ProductStageStatus
    reference_ids: tuple[str, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("reference_ids", mode="before")
    @classmethod
    def validate_references(cls, value: object) -> object:
        return _tuple(value, field="reference_ids")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> DashboardStageProjection:
        if self.fingerprint != dashboard_stage_fingerprint(**_values(self)):
            raise ValueError("dashboard stage fingerprint mismatch")
        return self


def dashboard_stage_fingerprint(**values: object) -> str:
    return _fingerprint("DashboardStageProjection", **values)


class EngineeringDashboardProjection(_ProductModel):
    project_id: str
    current_stage: ProductStage
    stages: tuple[DashboardStageProjection, ...]
    completed_count: int = Field(ge=0, le=9)
    blocked_count: int = Field(ge=0, le=9)
    overall_percent: float = Field(ge=0.0, le=100.0, allow_inf_nan=False)
    workspace_fingerprint: str
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _workspace = field_validator("workspace_fingerprint")(_fp)
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("stages", mode="before")
    @classmethod
    def validate_stages(cls, value: object) -> object:
        return _tuple(value, field="stages")

    @model_validator(mode="after")
    def validate_dashboard(self) -> EngineeringDashboardProjection:
        if tuple(item.stage for item in self.stages) != tuple(ProductStage):
            raise ValueError("dashboard stages are invalid")
        if self.completed_count != sum(
            item.status is ProductStageStatus.COMPLETED for item in self.stages
        ) or self.blocked_count != sum(
            item.status is ProductStageStatus.BLOCKED for item in self.stages
        ):
            raise ValueError("dashboard counts mismatch")
        if self.fingerprint != engineering_dashboard_fingerprint(**_values(self)):
            raise ValueError("dashboard fingerprint mismatch")
        return self


def engineering_dashboard_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringDashboardProjection", **values)


class EngineeringReleaseSection(_ProductModel):
    stage: ProductStage
    status: ProductStageStatus
    reference_ids: tuple[str, ...]
    source_fingerprints: tuple[str, ...]
    fingerprint: str

    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("reference_ids", "source_fingerprints", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_fingerprint(self) -> EngineeringReleaseSection:
        if self.fingerprint != release_section_fingerprint(**_values(self)):
            raise ValueError("release section fingerprint mismatch")
        return self


def release_section_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringReleaseSection", **values)


class EngineeringReleaseReport(_ProductModel):
    project_id: str
    project_name: str
    project_summary: str
    workspace_fingerprint: str
    sections: tuple[EngineeringReleaseSection, ...]
    decision_history: tuple[ProductDecisionProjection, ...]
    review_dashboard: ReviewDashboardProjection
    generated_at: datetime
    fingerprint: str

    _project_id = field_validator("project_id")(
        lambda value: _identifier(value, field="project_id")
    )
    _name = field_validator("project_name")(
        lambda value: _text(value, field="project_name", limit=128)
    )
    _summary = field_validator("project_summary")(
        lambda value: _text(value, field="project_summary")
    )
    _workspace = field_validator("workspace_fingerprint")(_fp)
    _generated_at = field_validator("generated_at")(
        lambda value: _utc(value, field="generated_at")
    )
    _fingerprint_format = field_validator("fingerprint")(_fp)

    @field_validator("sections", "decision_history", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_report(self) -> EngineeringReleaseReport:
        if tuple(item.stage for item in self.sections) != tuple(ProductStage):
            raise ValueError("release report sections are invalid")
        if self.fingerprint != engineering_release_report_fingerprint(**_values(self)):
            raise ValueError("release report fingerprint mismatch")
        return self


def engineering_release_report_fingerprint(**values: object) -> str:
    return _fingerprint("EngineeringReleaseReport", **values)
