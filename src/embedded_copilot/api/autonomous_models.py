from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AutonomousContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class LoopStatus(StrEnum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    APPROVAL = "APPROVAL"
    EXECUTING = "EXECUTING"
    BUILDING = "BUILDING"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TimelineStage(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    PLANNING = "PLANNING"
    APPROVAL = "APPROVAL"
    AGENT_EXECUTION = "AGENT_EXECUTION"
    BUILD = "BUILD"
    VERIFICATION = "VERIFICATION"
    REPAIR = "REPAIR"
    GENERATION = "GENERATION"
    REVIEW = "REVIEW"


class ViewStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_REQUIRED = "NOT_REQUIRED"
    COMPLETED = "COMPLETED"


def _safe_text(value: object, *, field: str, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError(f"{field} is invalid")
    if "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} is invalid")
    if any(
        token in value.lower()
        for token in ("prompt", "token", "secret", "password", "provider", "exception")
    ):
        raise ValueError(f"{field} is invalid")
    return value


def _project_id(value: object) -> str:
    text = _safe_text(value, field="project_id", maximum=96)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", text) or text in {".", ".."}:
        raise ValueError("project_id is invalid")
    return text


def _identifier(value: object, *, field: str) -> str:
    text = _safe_text(value, field=field, maximum=96)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", text):
        raise ValueError(f"{field} is invalid")
    return text


def _timestamp(value: object, *, field: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{field} is invalid") from error
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _tuple_only(value: object, *, field: str) -> object:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    return value


class LoopTimelineItem(AutonomousContract):
    stage: TimelineStage
    status: ViewStatus
    label: str
    summary: str | None = None

    _label = field_validator("label", mode="before")(
        lambda value: _safe_text(value, field="label")
    )
    _summary = field_validator("summary", mode="before")(
        lambda value: None if value is None else _safe_text(value, field="summary")
    )


class TaskGraphNode(AutonomousContract):
    node_id: str
    label: str
    status: ViewStatus

    _node_id = field_validator("node_id", mode="before")(
        lambda value: _identifier(value, field="node_id")
    )
    _label = field_validator("label", mode="before")(
        lambda value: _safe_text(value, field="label")
    )


class TaskGraphEdge(AutonomousContract):
    source: str
    target: str

    _source = field_validator("source", mode="before")(
        lambda value: _identifier(value, field="source")
    )
    _target = field_validator("target", mode="before")(
        lambda value: _identifier(value, field="target")
    )


class TaskGraph(AutonomousContract):
    nodes: tuple[TaskGraphNode, ...]
    edges: tuple[TaskGraphEdge, ...]

    _nodes = field_validator("nodes", mode="before")(
        lambda value: _tuple_only(value, field="nodes")
    )
    _edges = field_validator("edges", mode="before")(
        lambda value: _tuple_only(value, field="edges")
    )

    @model_validator(mode="after")
    def validate_graph(self) -> "TaskGraph":
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate graph node")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError("graph edge is invalid")
        return self


class AgentExecutionView(AutonomousContract):
    agent_id: str
    task_id: str
    status: ViewStatus
    summary: str | None = None

    _agent_id = field_validator("agent_id", mode="before")(
        lambda value: _identifier(value, field="agent_id")
    )
    _task_id = field_validator("task_id", mode="before")(
        lambda value: _identifier(value, field="task_id")
    )
    _summary = field_validator("summary", mode="before")(
        lambda value: None if value is None else _safe_text(value, field="summary")
    )


class ApprovalGateView(AutonomousContract):
    status: ViewStatus
    reviewer: str | None = None

    _reviewer = field_validator("reviewer", mode="before")(
        lambda value: (
            None if value is None else _safe_text(value, field="reviewer", maximum=96)
        )
    )


class VerificationStatusView(AutonomousContract):
    status: ViewStatus
    review_required: bool


class RepairLoopView(AutonomousContract):
    status: ViewStatus
    iteration: int = Field(ge=0, le=1000)
    max_iterations: int = Field(ge=1, le=1000)

    @field_validator("iteration", "max_iterations", mode="before")
    @classmethod
    def strict_int(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("iteration values must be integers")
        return value

    @model_validator(mode="after")
    def validate_iterations(self) -> "RepairLoopView":
        if self.iteration > self.max_iterations:
            raise ValueError("iteration exceeds maximum")
        return self


def _fingerprint_material(snapshot: "AutonomousLoopSnapshot") -> dict[str, object]:
    return snapshot.model_dump(mode="json", exclude={"fingerprint"})


def autonomous_snapshot_fingerprint(snapshot: "AutonomousLoopSnapshot") -> str:
    encoded = json.dumps(
        _fingerprint_material(snapshot),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class AutonomousLoopSnapshot(AutonomousContract):
    project_id: str
    status: LoopStatus
    progress: int = Field(ge=0, le=100)
    tasks: tuple[str, ...]
    current_task: str | None = None
    next_task: str | None = None
    timeline: tuple[LoopTimelineItem, ...]
    task_graph: TaskGraph
    agents: tuple[AgentExecutionView, ...]
    approval: ApprovalGateView
    verification: VerificationStatusView
    repair: RepairLoopView
    updated_at: datetime
    fingerprint: str

    _project_id_validator = field_validator("project_id", mode="before")(_project_id)

    @field_validator("progress", mode="before")
    @classmethod
    def validate_progress(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("progress must be an integer")
        return value

    @field_validator("tasks", "timeline", "agents", mode="before")
    @classmethod
    def tuples(cls, value: object, info) -> object:
        return _tuple_only(value, field=info.field_name)

    @field_validator("tasks", mode="before")
    @classmethod
    def task_values(cls, value: object) -> object:
        if isinstance(value, tuple):
            return tuple(_identifier(item, field="task") for item in value)
        return value

    @field_validator("current_task", "next_task", mode="before")
    @classmethod
    def optional_tasks(cls, value: object, info) -> object:
        return None if value is None else _identifier(value, field=info.field_name)

    @field_validator("updated_at", mode="before")
    @classmethod
    def updated(cls, value: object) -> datetime:
        return _timestamp(value, field="updated_at")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def fingerprint_format(cls, value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", value
        ):
            raise ValueError("fingerprint is invalid")
        return value

    @model_validator(mode="after")
    def validate_fingerprint(self) -> "AutonomousLoopSnapshot":
        task_ids = list(self.tasks)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("duplicate task")
        node_ids = {node.node_id for node in self.task_graph.nodes}
        if not set(task_ids).issubset(node_ids):
            raise ValueError("task graph does not cover tasks")
        if self.current_task is not None and self.current_task not in task_ids:
            raise ValueError("current task is invalid")
        if self.next_task is not None and self.next_task not in task_ids:
            raise ValueError("next task is invalid")
        timeline_stages = [item.stage for item in self.timeline]
        if len(timeline_stages) != len(set(timeline_stages)):
            raise ValueError("duplicate timeline stage")
        agent_keys = [(item.agent_id, item.task_id) for item in self.agents]
        if len(agent_keys) != len(set(agent_keys)):
            raise ValueError("duplicate agent task")
        expected = autonomous_snapshot_fingerprint(self.model_copy(deep=True))
        if self.fingerprint != expected:
            raise ValueError("fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "AutonomousLoopSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = autonomous_snapshot_fingerprint(provisional)
        return cls.model_validate(values)


class LoopSnapshotPort(Protocol):
    def get_snapshot(self, project_id: str) -> AutonomousLoopSnapshot | None: ...


def validate_snapshot(snapshot: object) -> AutonomousLoopSnapshot:
    if not isinstance(snapshot, AutonomousLoopSnapshot):
        raise TypeError("snapshot is invalid")
    return AutonomousLoopSnapshot.model_validate(copy.deepcopy(snapshot))


__all__ = [
    "AgentExecutionView",
    "ApprovalGateView",
    "AutonomousLoopSnapshot",
    "LoopSnapshotPort",
    "LoopStatus",
    "LoopTimelineItem",
    "RepairLoopView",
    "TaskGraph",
    "TaskGraphEdge",
    "TaskGraphNode",
    "TimelineStage",
    "VerificationStatusView",
    "ViewStatus",
    "autonomous_snapshot_fingerprint",
    "validate_snapshot",
]
