from __future__ import annotations

import copy
from datetime import datetime

from pydantic import field_validator

from embedded_copilot.copilot.models import (
    CopilotContractModel,
    DesignStage,
    WorkflowProgressStatus,
    safe_summary,
    utc_datetime,
)

_STAGE_INDEX = {stage: index for index, stage in enumerate(DesignStage)}
_TRANSITIONS = {
    WorkflowProgressStatus.PENDING: {
        WorkflowProgressStatus.RUNNING,
        WorkflowProgressStatus.FAILED,
    },
    WorkflowProgressStatus.RUNNING: {
        WorkflowProgressStatus.COMPLETED,
        WorkflowProgressStatus.FAILED,
    },
    WorkflowProgressStatus.COMPLETED: set(),
    WorkflowProgressStatus.FAILED: set(),
}


class WorkflowProgress(CopilotContractModel):
    stage: DesignStage
    status: WorkflowProgressStatus
    summary: str
    updated_at: datetime

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return safe_summary(value, field="summary")

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, value: object) -> datetime:
        return utc_datetime(value, field="updated_at")


def update_progress(
    progress: tuple[WorkflowProgress, ...],
    snapshot: WorkflowProgress,
) -> tuple[WorkflowProgress, ...]:
    current = tuple(_snapshot(item) for item in copy.deepcopy(progress))
    if len({item.stage for item in current}) != len(current):
        raise ValueError("progress contains duplicate stage snapshots")
    candidate = _snapshot(snapshot)
    existing = next(
        (item for item in current if item.stage is candidate.stage),
        None,
    )
    if existing is None:
        if candidate.status is not WorkflowProgressStatus.PENDING:
            raise ValueError("a progress stage must begin as pending")
        updated = (*current, candidate)
    else:
        if candidate.status not in _TRANSITIONS[existing.status]:
            raise ValueError("progress status transition is invalid")
        if candidate.updated_at <= existing.updated_at:
            raise ValueError("progress update timestamp must increase")
        updated = tuple(
            candidate if item.stage is candidate.stage else item for item in current
        )
    return tuple(sorted(updated, key=lambda item: _STAGE_INDEX[item.stage]))


def _snapshot(value: WorkflowProgress) -> WorkflowProgress:
    if not isinstance(value, WorkflowProgress):
        raise TypeError("workflow progress snapshot is invalid")
    return WorkflowProgress.model_validate(
        copy.deepcopy(value.model_dump(mode="python"))
    )
