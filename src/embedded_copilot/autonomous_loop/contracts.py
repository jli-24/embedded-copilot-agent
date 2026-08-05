from __future__ import annotations

import copy
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.approval_gate.contracts import ApprovalStatus

from .models import canonical_fingerprint, fingerprint, identifier, safe_text


class AutonomousLoopContract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class LoopStage(StrEnum):
    INITIALIZING = "INITIALIZING"
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    BUILDING = "BUILDING"
    VALIDATING = "VALIDATING"
    ANALYZING = "ANALYZING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LoopViewStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_APPROVAL = "WAITING_APPROVAL"


class LoopTimelineItem(AutonomousLoopContract):
    stage: LoopStage
    status: str
    label: str
    summary: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, value: object) -> str:
        text = identifier(value, field="status", maximum=32)
        if text not in {item.value for item in LoopViewStatus}:
            raise ValueError("timeline status is invalid")
        return text

    @field_validator("label", mode="before")
    @classmethod
    def validate_label(cls, value: object) -> str:
        return safe_text(value, field="label", maximum=160)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str | None:
        return None if value is None else safe_text(value, field="summary", maximum=512)


class PendingAction(AutonomousLoopContract):
    action_id: str
    loop_id: str
    action_type: str
    action_fingerprint: str
    approval_status: ApprovalStatus = ApprovalStatus.PENDING

    @field_validator("action_id", "loop_id", "action_type", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("action_fingerprint", mode="before")
    @classmethod
    def validate_action_fingerprint(cls, value: object) -> str:
        return fingerprint(value, field="action_fingerprint")

    @classmethod
    def create(cls, **values: object) -> "PendingAction":
        return cls.model_validate(values)


class AutonomousLoopSnapshot(AutonomousLoopContract):
    project_id: str
    loop_id: str
    current_stage: LoopStage
    completed_stages: tuple[LoopStage, ...]
    pending_action: PendingAction | None
    approval_status: ApprovalStatus
    iteration: int = Field(ge=0, le=1000)
    timeline: tuple[LoopTimelineItem, ...]
    fingerprint: str

    @field_validator("project_id", "loop_id", mode="before")
    @classmethod
    def validate_ids(cls, value: object, info) -> str:
        return identifier(value, field=info.field_name)

    @field_validator("completed_stages", "timeline", mode="before")
    @classmethod
    def validate_tuples(cls, value: object, info) -> object:
        if type(value) is not tuple:
            raise ValueError(f"{info.field_name} must be a tuple")
        return value

    @field_validator("iteration", mode="before")
    @classmethod
    def validate_iteration(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("iteration must be an integer")
        return value

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "AutonomousLoopSnapshot":
        if len(self.completed_stages) != len(set(self.completed_stages)):
            raise ValueError("completed stages must be unique")
        if self.current_stage in self.completed_stages:
            raise ValueError("current stage cannot be completed")
        if (
            self.pending_action is not None
            and self.pending_action.loop_id != self.loop_id
        ):
            raise ValueError("pending action loop binding mismatch")
        stages = [item.stage for item in self.timeline]
        if len(stages) != len(set(stages)):
            raise ValueError("timeline stages must be unique")
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("autonomous loop fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "AutonomousLoopSnapshot":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


class RepairProposal(AutonomousLoopContract):
    issue_summary: str
    affected_area: str
    suggested_change: str
    evidence_reference: str
    fingerprint: str

    @field_validator(
        "issue_summary", "affected_area", "suggested_change", mode="before"
    )
    @classmethod
    def validate_text(cls, value: object, info) -> str:
        return safe_text(value, field=info.field_name)

    @field_validator("evidence_reference", mode="before")
    @classmethod
    def validate_reference(cls, value: object) -> str:
        return identifier(value, field="evidence_reference")

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return fingerprint(value)

    @model_validator(mode="after")
    def verify(self) -> "RepairProposal":
        if self.fingerprint != canonical_fingerprint(self, exclude={"fingerprint"}):
            raise ValueError("repair proposal fingerprint mismatch")
        return self

    @classmethod
    def create(cls, **values: object) -> "RepairProposal":
        provisional = cls.model_construct(
            **{**values, "fingerprint": "sha256:" + "0" * 64}
        )
        values["fingerprint"] = canonical_fingerprint(
            provisional, exclude={"fingerprint"}
        )
        return cls.model_validate(values)


@runtime_checkable
class LoopStatePort(Protocol):
    def get_snapshot(self, project_id: str) -> AutonomousLoopSnapshot | None: ...

    def save_snapshot(
        self, snapshot: AutonomousLoopSnapshot
    ) -> AutonomousLoopSnapshot: ...


@runtime_checkable
class LoopCoordinatorPort(Protocol):
    def get_snapshot(self, project_id: str) -> AutonomousLoopSnapshot | None: ...

    def resume(
        self, project_id: str, expected_fingerprint: str | None = None
    ) -> AutonomousLoopSnapshot: ...

    def approve(self, action_id: str, decision: object) -> AutonomousLoopSnapshot: ...

    def reject(self, action_id: str, decision: object) -> AutonomousLoopSnapshot: ...


def autonomous_loop_fingerprint(value: AutonomousLoopSnapshot) -> str:
    return canonical_fingerprint(value, exclude={"fingerprint"})


def validate_snapshot(value: object) -> AutonomousLoopSnapshot:
    if type(value) is not AutonomousLoopSnapshot:
        raise TypeError("autonomous loop snapshot is invalid")
    return AutonomousLoopSnapshot.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )


__all__ = [
    "AutonomousLoopSnapshot",
    "AutonomousLoopContract",
    "LoopCoordinatorPort",
    "LoopStage",
    "LoopStatePort",
    "LoopTimelineItem",
    "LoopViewStatus",
    "PendingAction",
    "RepairProposal",
    "autonomous_loop_fingerprint",
    "validate_snapshot",
]
