from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from embedded_copilot.copilot.context import DesignSessionContext
from embedded_copilot.copilot.models import DesignStage, SessionApprovalStatus
from embedded_copilot.copilot.session import (
    advance_stage,
    bind_artifact,
    create_session,
)
from embedded_copilot.hardware_design.approval import (
    DesignApproval,
    DesignApprovalStatus,
)

from tests.copilot.test_artifact_view import artifact

UTC = timezone.utc
CREATED = datetime(2026, 7, 26, 8, 0, tzinfo=UTC)


def test_create_session_builds_initial_reference_snapshot() -> None:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    )

    assert context.current_stage is DesignStage.REQUIREMENT_ANALYSIS
    assert context.approval_status is SessionApprovalStatus.NONE
    assert context.artifact_ids == ()
    assert context.decision_ids == ()
    assert context.file_ids == ()
    assert context.created_at == context.updated_at == CREATED


def test_session_stage_can_skip_forward_without_runtime_side_effects() -> None:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    )
    before = context.model_dump_json()

    advanced = advance_stage(
        context,
        DesignStage.HARDWARE_DESIGN,
        updated_at=CREATED + timedelta(minutes=1),
    )

    assert advanced.current_stage is DesignStage.HARDWARE_DESIGN
    assert advanced.updated_at == CREATED + timedelta(minutes=1)
    assert context.model_dump_json() == before


@pytest.mark.parametrize(
    ("current", "target"),
    (
        (DesignStage.HARDWARE_DESIGN, DesignStage.HARDWARE_DESIGN),
        (DesignStage.HARDWARE_DESIGN, DesignStage.KNOWLEDGE_RETRIEVAL),
        (DesignStage.REPORT, DesignStage.REPORT),
    ),
)
def test_session_stage_rejects_repeat_or_backward_transition(
    current: DesignStage,
    target: DesignStage,
) -> None:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    ).model_copy(update={"current_stage": current})

    with pytest.raises(ValueError):
        advance_stage(
            context,
            target,
            updated_at=CREATED + timedelta(minutes=1),
        )


def test_session_stage_requires_strictly_newer_utc_timestamp() -> None:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    )

    for timestamp in (CREATED, CREATED - timedelta(seconds=1)):
        with pytest.raises(ValueError):
            advance_stage(
                context,
                DesignStage.REPORT,
                updated_at=timestamp,
            )


def test_bind_artifact_copies_references_without_taking_ownership() -> None:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    )
    source = artifact()
    before = source.model_dump_json()

    bound = bind_artifact(
        context,
        artifact_id="artifact:1",
        artifact=source,
        updated_at=CREATED + timedelta(minutes=1),
    )

    assert bound.artifact_ids == ("artifact:1",)
    assert bound.decision_ids == (source.decisions[0].decision_id,)
    assert bound.approval_status is SessionApprovalStatus.PROPOSED
    assert "artifact" not in DesignSessionContext.model_fields
    assert source.model_dump_json() == before


def test_bind_artifact_rejects_duplicate_or_modified_artifact() -> None:
    context = create_session(
        session_id="session:1",
        project_name="Security Terminal",
        user_requirement="Review an existing embedded design.",
        created_at=CREATED,
    )
    source = artifact()
    bound = bind_artifact(
        context,
        artifact_id="artifact:1",
        artifact=source,
        updated_at=CREATED + timedelta(minutes=1),
    )
    with pytest.raises(ValueError):
        bind_artifact(
            bound,
            artifact_id="artifact:1",
            artifact=source,
            updated_at=CREATED + timedelta(minutes=2),
        )

    modified = source.model_copy(
        update={
            "approval": DesignApproval(status=DesignApprovalStatus.MODIFIED),
        }
    )
    with pytest.raises(ValueError):
        bind_artifact(
            context,
            artifact_id="artifact:modified",
            artifact=modified,
            updated_at=CREATED + timedelta(minutes=1),
        )
