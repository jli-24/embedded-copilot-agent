from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

import embedded_copilot.copilot.progress as progress_module
from embedded_copilot.copilot.models import (
    DesignStage,
    WorkflowProgressStatus,
)
from embedded_copilot.copilot.progress import WorkflowProgress, update_progress
from embedded_copilot.copilot.session import create_session
from embedded_copilot.copilot.workspace import (
    ProjectWorkspace,
    create_workspace,
    record_progress,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


def _snapshot(
    stage: DesignStage,
    status: WorkflowProgressStatus,
    *,
    minutes: int,
) -> WorkflowProgress:
    return WorkflowProgress(
        stage=stage,
        status=status,
        summary=f"{stage.value} presentation snapshot.",
        updated_at=NOW + timedelta(minutes=minutes),
    )


def test_progress_updates_are_immutable_and_sorted_by_display_stage() -> None:
    hardware = _snapshot(
        DesignStage.HARDWARE_DESIGN,
        WorkflowProgressStatus.PENDING,
        minutes=2,
    )
    requirement = _snapshot(
        DesignStage.REQUIREMENT_ANALYSIS,
        WorkflowProgressStatus.PENDING,
        minutes=1,
    )

    first = update_progress((), hardware)
    updated = update_progress(first, requirement)

    assert tuple(item.stage for item in updated) == (
        DesignStage.REQUIREMENT_ANALYSIS,
        DesignStage.HARDWARE_DESIGN,
    )
    assert first == (hardware,)
    assert updated[1] is not hardware


def test_progress_allows_only_defined_forward_status_transitions() -> None:
    pending = _snapshot(
        DesignStage.HARDWARE_DESIGN,
        WorkflowProgressStatus.PENDING,
        minutes=1,
    )
    running = pending.model_copy(
        update={
            "status": WorkflowProgressStatus.RUNNING,
            "updated_at": NOW + timedelta(minutes=2),
        }
    )
    completed = running.model_copy(
        update={
            "status": WorkflowProgressStatus.COMPLETED,
            "updated_at": NOW + timedelta(minutes=3),
        }
    )

    progress = update_progress((), pending)
    progress = update_progress(progress, running)
    progress = update_progress(progress, completed)

    assert progress == (completed,)


@pytest.mark.parametrize(
    ("initial", "target"),
    (
        (WorkflowProgressStatus.PENDING, WorkflowProgressStatus.COMPLETED),
        (WorkflowProgressStatus.RUNNING, WorkflowProgressStatus.PENDING),
        (WorkflowProgressStatus.COMPLETED, WorkflowProgressStatus.FAILED),
        (WorkflowProgressStatus.FAILED, WorkflowProgressStatus.RUNNING),
    ),
)
def test_progress_rejects_invalid_or_terminal_transitions(
    initial: WorkflowProgressStatus,
    target: WorkflowProgressStatus,
) -> None:
    current = _snapshot(DesignStage.DEBUG, initial, minutes=1)
    candidate = current.model_copy(
        update={"status": target, "updated_at": NOW + timedelta(minutes=2)}
    )

    with pytest.raises(ValueError):
        update_progress((current,), candidate)


def test_progress_requires_pending_as_a_stage_initial_state() -> None:
    with pytest.raises(ValueError):
        update_progress(
            (),
            _snapshot(
                DesignStage.REPORT,
                WorkflowProgressStatus.RUNNING,
                minutes=1,
            ),
        )


def test_progress_rejects_unsafe_summary_and_non_utc_timestamp() -> None:
    with pytest.raises(ValidationError):
        WorkflowProgress(
            stage=DesignStage.DEBUG,
            status=WorkflowProgressStatus.PENDING,
            summary="api_key=sk-privatecredential",
            updated_at=NOW,
        )
    with pytest.raises(ValidationError):
        WorkflowProgress(
            stage=DesignStage.DEBUG,
            status=WorkflowProgressStatus.PENDING,
            summary="Debug presentation snapshot.",
            updated_at=NOW.replace(tzinfo=None),
        )


def test_progress_is_not_an_authoritative_execution_state() -> None:
    source = inspect.getsource(progress_module).casefold()

    for forbidden_dependency in (
        "supervisor",
        "agentresult",
        "langgraph",
        "services.runtime",
        "workflowstate",
    ):
        assert forbidden_dependency not in source
    assert not hasattr(WorkflowProgress, "execute")
    assert not hasattr(WorkflowProgress, "route")


def test_workspace_records_progress_without_changing_session_state() -> None:
    session = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review the existing engineering Artifact.",
        created_at=NOW,
    )
    workspace = create_workspace(session)
    snapshot = _snapshot(
        DesignStage.REQUIREMENT_ANALYSIS,
        WorkflowProgressStatus.PENDING,
        minutes=1,
    )

    updated = record_progress(workspace, snapshot)

    assert updated.progress == (snapshot,)
    assert updated.session == workspace.session
    assert workspace.progress == ()


def test_workspace_direct_construction_rejects_unsorted_progress() -> None:
    session = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review the existing engineering Artifact.",
        created_at=NOW,
    )
    requirement = _snapshot(
        DesignStage.REQUIREMENT_ANALYSIS,
        WorkflowProgressStatus.PENDING,
        minutes=1,
    )
    hardware = _snapshot(
        DesignStage.HARDWARE_DESIGN,
        WorkflowProgressStatus.PENDING,
        minutes=2,
    )

    with pytest.raises(ValidationError):
        ProjectWorkspace.model_validate(
            {
                **create_workspace(session).model_dump(mode="python"),
                "progress": (hardware, requirement),
            }
        )
