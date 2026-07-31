from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_RISK_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_SENSITIVE = re.compile(
    r"(?:api[_ -]?key\s*[:=]|access[_ -]?token\s*[:=]|bearer\s+"
    r"|password\s*[:=]|credential\s*[:=]|secret\s*[:=])",
    re.IGNORECASE,
)
_LOCAL_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|^\\\\|^file://|^/)")


class _WorkflowContract(BaseModel):
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


def _safe_text(value: object, *, field: str, maximum: int = 1024) -> str:
    if type(value) is not str:
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if (
        not candidate
        or len(candidate) > maximum
        or any(character in candidate for character in ("\r", "\n", "\x00"))
        or _SENSITIVE.search(candidate) is not None
    ):
        raise ValueError(f"{field} is unsafe")
    return candidate


def _safe_reference(value: object) -> str:
    candidate = _safe_text(value, field="reference", maximum=512)
    if _LOCAL_PATH.search(candidate) is not None:
        raise ValueError("reference is unsafe")
    parsed = urlsplit(candidate)
    if parsed.scheme:
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("reference is unsafe")
    elif _IDENTIFIER.fullmatch(candidate) is None:
        raise ValueError("reference is unsafe")
    return candidate


def _utc(value: object, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field} must be timezone aware")
    if value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone aware")
    return value.astimezone(UTC)


def _tuple(value: object, *, field: str) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be a tuple")
    return value


def _safe_text_tuple(
    value: object,
    *,
    field: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    items = _tuple(value, field=field)
    checked = tuple(_safe_text(item, field=field, maximum=512) for item in items)
    if not allow_empty and not checked:
        raise ValueError(f"{field} must not be empty")
    if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
        raise ValueError(f"{field} must be sorted and unique")
    return checked


def _finite_confidence(value: object) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise ValueError("confidence is invalid")
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence is invalid")
    return value


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _checked_fingerprint(value: object, *, field: str) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


class WorkflowSourceType(StrEnum):
    KNOWLEDGE_CONTEXT = "KNOWLEDGE_CONTEXT"
    MEMORY_CONTEXT = "MEMORY_CONTEXT"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"


class WorkflowState(StrEnum):
    RECEIVED = "RECEIVED"
    REQUIREMENTS_READY = "REQUIREMENTS_READY"
    CONTEXT_PROJECTED = "CONTEXT_PROJECTED"
    RISKS_PROJECTED = "RISKS_PROJECTED"
    PLAN_READY = "PLAN_READY"
    DAG_VALIDATED = "DAG_VALIDATED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SCHEDULED = "SCHEDULED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class WorkflowProgressEventType(StrEnum):
    WORKFLOW_RECEIVED = "WORKFLOW_RECEIVED"
    REQUIREMENTS_READY = "REQUIREMENTS_READY"
    CONTEXT_PROJECTED = "CONTEXT_PROJECTED"
    RISKS_PROJECTED = "RISKS_PROJECTED"
    PLAN_READY = "PLAN_READY"
    DAG_VALIDATED = "DAG_VALIDATED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    WORKFLOW_SCHEDULED = "WORKFLOW_SCHEDULED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"


class WorkflowApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"


class WorkflowPreparationRequest(_WorkflowContract):
    workflow_id: str
    requirement_summary: str
    requested_at: datetime

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("requirement_summary", mode="before")
    @classmethod
    def validate_requirement_summary(cls, value: object) -> str:
        return _safe_text(value, field="requirement_summary", maximum=2048)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: object) -> datetime:
        return _utc(value, field="requested_at")


class RequirementAgentRequest(_WorkflowContract):
    workflow_id: str
    requirement_summary: str
    requested_at: datetime

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("requirement_summary", mode="before")
    @classmethod
    def validate_requirement_summary(cls, value: object) -> str:
        return _safe_text(value, field="requirement_summary", maximum=2048)

    @field_validator("requested_at")
    @classmethod
    def validate_requested_at(cls, value: object) -> datetime:
        return _utc(value, field="requested_at")


def requirement_specification_fingerprint(
    *,
    workflow_id: str,
    requirements: tuple[str, ...],
    constraints: tuple[str, ...],
    assumptions: tuple[str, ...],
) -> str:
    return _fingerprint(
        {
            "workflow_id": workflow_id,
            "requirements": list(requirements),
            "constraints": list(constraints),
            "assumptions": list(assumptions),
        }
    )


class RequirementSpecification(_WorkflowContract):
    workflow_id: str
    requirements: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    fingerprint: str

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("requirements", mode="before")
    @classmethod
    def validate_requirements(cls, value: object) -> tuple[str, ...]:
        return _safe_text_tuple(value, field="requirements", allow_empty=False)

    @field_validator("constraints", "assumptions", mode="before")
    @classmethod
    def validate_optional_text(cls, value: object, info) -> tuple[str, ...]:
        return _safe_text_tuple(value, field=info.field_name, allow_empty=True)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        return _checked_fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> RequirementSpecification:
        expected = requirement_specification_fingerprint(
            workflow_id=self.workflow_id,
            requirements=self.requirements,
            constraints=self.constraints,
            assumptions=self.assumptions,
        )
        if self.fingerprint != expected:
            raise ValueError("requirement fingerprint does not match content")
        return self


class WorkflowContextRequest(_WorkflowContract):
    workflow_id: str
    requirement_fingerprint: str

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("requirement_fingerprint", mode="before")
    @classmethod
    def validate_requirement_fingerprint(cls, value: object) -> str:
        return _checked_fingerprint(value, field="requirement_fingerprint")


class VerifiedWorkflowSourceReference(_WorkflowContract):
    source_type: WorkflowSourceType
    source_id: str
    verification_status: Literal["VERIFIED"] = "VERIFIED"
    reference: str
    confidence: float

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        return _identifier(value, field="source_id")

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _safe_reference(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _finite_confidence(value)


class WorkflowRiskItem(_WorkflowContract):
    risk_type: str
    source_type: WorkflowSourceType
    source_id: str
    confidence: float
    reference: str

    @field_validator("risk_type", mode="before")
    @classmethod
    def validate_risk_type(cls, value: object) -> str:
        if type(value) is not str or _RISK_TYPE.fullmatch(value) is None:
            raise ValueError("risk_type is invalid")
        return value

    @field_validator("source_id", mode="before")
    @classmethod
    def validate_source_id(cls, value: object) -> str:
        return _identifier(value, field="source_id")

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _finite_confidence(value)

    @field_validator("reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return _safe_reference(value)


def workflow_context_fingerprint(
    *,
    workflow_id: str,
    requirement_fingerprint: str,
    confidence: float,
    verified_source_references: tuple[VerifiedWorkflowSourceReference, ...],
) -> str:
    return _fingerprint(
        {
            "workflow_id": workflow_id,
            "requirement_fingerprint": requirement_fingerprint,
            "confidence": confidence,
            "verified_source_references": [
                item.model_dump(mode="json") for item in verified_source_references
            ],
        }
    )


class WorkflowContextProjection(_WorkflowContract):
    workflow_id: str
    requirement_fingerprint: str
    context_fingerprint: str
    confidence: float
    verified_source_references: tuple[VerifiedWorkflowSourceReference, ...] = ()
    projected_risks: tuple[WorkflowRiskItem, ...] = ()

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("requirement_fingerprint", "context_fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return _checked_fingerprint(value, field=info.field_name)

    @field_validator("confidence", mode="before")
    @classmethod
    def validate_confidence(cls, value: object) -> float:
        return _finite_confidence(value)

    @field_validator("verified_source_references", "projected_risks", mode="before")
    @classmethod
    def validate_tuple_fields(cls, value: object, info) -> object:
        return _tuple(value, field=info.field_name)

    @model_validator(mode="after")
    def validate_projection(self) -> WorkflowContextProjection:
        source_keys = tuple(
            (item.source_type.value, item.source_id, item.reference)
            for item in self.verified_source_references
        )
        if source_keys != tuple(sorted(source_keys)) or len(source_keys) != len(
            set(source_keys)
        ):
            raise ValueError("verified sources must be sorted and unique")
        risk_keys = tuple(
            (item.risk_type, item.source_type.value, item.source_id, item.reference)
            for item in self.projected_risks
        )
        if risk_keys != tuple(sorted(risk_keys)) or len(risk_keys) != len(
            set(risk_keys)
        ):
            raise ValueError("projected risks must be sorted and unique")
        expected = workflow_context_fingerprint(
            workflow_id=self.workflow_id,
            requirement_fingerprint=self.requirement_fingerprint,
            confidence=self.confidence,
            verified_source_references=self.verified_source_references,
        )
        if self.context_fingerprint != expected:
            raise ValueError("context fingerprint does not match content")
        return self


def workflow_risk_fingerprint(risks: tuple[WorkflowRiskItem, ...]) -> str:
    return _fingerprint([item.model_dump(mode="json") for item in risks])


class WorkflowRiskProjection(_WorkflowContract):
    risks: tuple[WorkflowRiskItem, ...] = ()
    fingerprint: str

    @field_validator("risks", mode="before")
    @classmethod
    def validate_risks_tuple(cls, value: object) -> object:
        return _tuple(value, field="risks")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        return _checked_fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def validate_projection(self) -> WorkflowRiskProjection:
        keys = tuple(
            (item.risk_type, item.source_type.value, item.source_id, item.reference)
            for item in self.risks
        )
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("risks must be sorted and unique")
        if self.fingerprint != workflow_risk_fingerprint(self.risks):
            raise ValueError("risk fingerprint does not match content")
        return self


class EngineeringWorkflowTask(_WorkflowContract):
    task_id: str
    summary: str
    dependencies: tuple[str, ...] = ()

    @field_validator("task_id", mode="before")
    @classmethod
    def validate_task_id(cls, value: object) -> str:
        return _identifier(value, field="task_id")

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _safe_text(value, field="summary", maximum=512)

    @field_validator("dependencies", mode="before")
    @classmethod
    def validate_dependencies(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="dependencies")
        checked = tuple(_identifier(item, field="dependency") for item in values)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("dependencies must be sorted and unique")
        return checked


def engineering_workflow_plan_fingerprint(
    *,
    workflow_id: str,
    plan_id: str,
    tasks: tuple[EngineeringWorkflowTask, ...],
) -> str:
    return _fingerprint(
        {
            "workflow_id": workflow_id,
            "plan_id": plan_id,
            "tasks": [item.model_dump(mode="json") for item in tasks],
        }
    )


class EngineeringWorkflowPlan(_WorkflowContract):
    workflow_id: str
    plan_id: str
    tasks: tuple[EngineeringWorkflowTask, ...] = Field(min_length=1, max_length=128)
    fingerprint: str

    @field_validator("workflow_id", "plan_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks_tuple(cls, value: object) -> object:
        return _tuple(value, field="tasks")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        return _checked_fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def validate_plan(self) -> EngineeringWorkflowPlan:
        task_ids = tuple(item.task_id for item in self.tasks)
        if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValueError("tasks must be sorted and unique")
        expected = engineering_workflow_plan_fingerprint(
            workflow_id=self.workflow_id,
            plan_id=self.plan_id,
            tasks=self.tasks,
        )
        if self.fingerprint != expected:
            raise ValueError("plan fingerprint does not match content")
        return self


class EngineeringPlanningRequest(_WorkflowContract):
    requirements: RequirementSpecification
    context: WorkflowContextProjection
    risks: WorkflowRiskProjection


def task_dag_fingerprint(
    *,
    workflow_id: str,
    plan_fingerprint: str,
    tasks: tuple[EngineeringWorkflowTask, ...],
) -> str:
    return _fingerprint(
        {
            "workflow_id": workflow_id,
            "plan_fingerprint": plan_fingerprint,
            "tasks": [item.model_dump(mode="json") for item in tasks],
        }
    )


class FrozenTaskDAG(_WorkflowContract):
    workflow_id: str
    plan_fingerprint: str
    tasks: tuple[EngineeringWorkflowTask, ...] = Field(min_length=1, max_length=128)
    fingerprint: str

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("plan_fingerprint", "fingerprint", mode="before")
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return _checked_fingerprint(value, field=info.field_name)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks_tuple(cls, value: object) -> object:
        return _tuple(value, field="tasks")

    @model_validator(mode="after")
    def validate_dag(self) -> FrozenTaskDAG:
        task_ids = tuple(item.task_id for item in self.tasks)
        if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
            raise ValueError("DAG tasks must be sorted and unique")
        known = set(task_ids)
        for task in self.tasks:
            if task.task_id in task.dependencies:
                raise ValueError("DAG self dependency is invalid")
            if not set(task.dependencies).issubset(known):
                raise ValueError("DAG dependency is missing")
        remaining = {item.task_id: set(item.dependencies) for item in self.tasks}
        while remaining:
            ready = sorted(
                key for key, dependencies in remaining.items() if not dependencies
            )
            if not ready:
                raise ValueError("DAG contains a cycle")
            for task_id in ready:
                remaining.pop(task_id)
            for dependencies in remaining.values():
                dependencies.difference_update(ready)
        expected = task_dag_fingerprint(
            workflow_id=self.workflow_id,
            plan_fingerprint=self.plan_fingerprint,
            tasks=self.tasks,
        )
        if self.fingerprint != expected:
            raise ValueError("DAG fingerprint does not match content")
        return self


class WorkflowScheduleBatch(_WorkflowContract):
    batch_index: int = Field(ge=1)
    task_ids: tuple[str, ...] = Field(min_length=1, max_length=128)

    @field_validator("batch_index", mode="before")
    @classmethod
    def validate_batch_index(cls, value: object) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("batch_index is invalid")
        return value

    @field_validator("task_ids", mode="before")
    @classmethod
    def validate_task_ids(cls, value: object) -> tuple[str, ...]:
        values = _tuple(value, field="task_ids")
        checked = tuple(_identifier(item, field="task_id") for item in values)
        if checked != tuple(sorted(checked)) or len(checked) != len(set(checked)):
            raise ValueError("batch task IDs must be sorted and unique")
        return checked


class WorkflowProgressEvent(_WorkflowContract):
    sequence: int = Field(ge=1)
    workflow_id: str
    event: WorkflowProgressEventType
    state: WorkflowState
    count: int = Field(ge=0)
    timestamp: datetime

    @field_validator("sequence", "count", mode="before")
    @classmethod
    def validate_counts(cls, value: object, info) -> int:
        minimum = 1 if info.field_name == "sequence" else 0
        if type(value) is not int or value < minimum:
            raise ValueError(f"{info.field_name} is invalid")
        return value

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return _utc(value, field="timestamp")


class WorkflowApprovalContext(_WorkflowContract):
    workflow_id: str
    requirement_fingerprint: str
    context_fingerprint: str
    risk_fingerprint: str
    dag_fingerprint: str
    waiting_snapshot_fingerprint: str
    decision: WorkflowApprovalDecision
    reviewer: str
    reviewed_at: datetime

    @field_validator("workflow_id", "reviewer", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator(
        "requirement_fingerprint",
        "context_fingerprint",
        "risk_fingerprint",
        "dag_fingerprint",
        "waiting_snapshot_fingerprint",
        mode="before",
    )
    @classmethod
    def validate_fingerprints(cls, value: object, info) -> str:
        return _checked_fingerprint(value, field=info.field_name)

    @field_validator("reviewed_at")
    @classmethod
    def validate_reviewed_at(cls, value: object) -> datetime:
        return _utc(value, field="reviewed_at")


def workflow_snapshot_fingerprint(
    *,
    workflow_id: str,
    state: WorkflowState,
    requirements: RequirementSpecification,
    context: WorkflowContextProjection,
    risks: WorkflowRiskProjection,
    plan: EngineeringWorkflowPlan,
    dag: FrozenTaskDAG,
    schedule: tuple[WorkflowScheduleBatch, ...],
    progress_sequence: int,
) -> str:
    return _fingerprint(
        {
            "workflow_id": workflow_id,
            "state": state.value,
            "requirements": requirements.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
            "risks": risks.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "dag": dag.model_dump(mode="json"),
            "schedule": [item.model_dump(mode="json") for item in schedule],
            "progress_sequence": progress_sequence,
        }
    )


class FrozenWorkflowSnapshot(_WorkflowContract):
    workflow_id: str
    state: WorkflowState
    requirements: RequirementSpecification
    context: WorkflowContextProjection
    risks: WorkflowRiskProjection
    plan: EngineeringWorkflowPlan
    dag: FrozenTaskDAG
    schedule: tuple[WorkflowScheduleBatch, ...] = ()
    progress_sequence: int = Field(ge=1)
    fingerprint: str

    @field_validator("workflow_id", mode="before")
    @classmethod
    def validate_workflow_id(cls, value: object) -> str:
        return _identifier(value, field="workflow_id")

    @field_validator("schedule", mode="before")
    @classmethod
    def validate_schedule_tuple(cls, value: object) -> object:
        return _tuple(value, field="schedule")

    @field_validator("progress_sequence", mode="before")
    @classmethod
    def validate_progress_sequence(cls, value: object) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("progress_sequence is invalid")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint_format(cls, value: object) -> str:
        return _checked_fingerprint(value, field="fingerprint")

    @model_validator(mode="after")
    def validate_snapshot(self) -> FrozenWorkflowSnapshot:
        if any(
            value != self.workflow_id
            for value in (
                self.requirements.workflow_id,
                self.context.workflow_id,
                self.plan.workflow_id,
                self.dag.workflow_id,
            )
        ):
            raise ValueError("snapshot workflow binding is invalid")
        if self.state is WorkflowState.SCHEDULED:
            if not self.schedule:
                raise ValueError("scheduled workflow requires batches")
        elif self.schedule:
            raise ValueError("non-scheduled workflow cannot contain batches")
        if self.state not in {
            WorkflowState.WAITING_APPROVAL,
            WorkflowState.SCHEDULED,
            WorkflowState.REJECTED,
        }:
            raise ValueError("public snapshot state is invalid")
        expected = workflow_snapshot_fingerprint(
            workflow_id=self.workflow_id,
            state=self.state,
            requirements=self.requirements,
            context=self.context,
            risks=self.risks,
            plan=self.plan,
            dag=self.dag,
            schedule=self.schedule,
            progress_sequence=self.progress_sequence,
        )
        if self.fingerprint != expected:
            raise ValueError("workflow fingerprint does not match content")
        return self
