from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.autonomous_loop.contracts import (
    AutonomousLoopSnapshot,
    LoopStage,
    LoopTimelineItem,
    PendingAction,
    RepairProposal,
    autonomous_loop_fingerprint,
)
from embedded_copilot.approval_gate.contracts import ApprovalStatus


def _snapshot() -> AutonomousLoopSnapshot:
    return AutonomousLoopSnapshot.create(
        project_id="demo",
        loop_id="loop-1",
        current_stage=LoopStage.INITIALIZING,
        completed_stages=(),
        pending_action=None,
        approval_status=ApprovalStatus.PENDING,
        iteration=0,
        timeline=(
            LoopTimelineItem(
                stage=LoopStage.INITIALIZING,
                status="RUNNING",
                label="Initializing",
            ),
        ),
    )


def test_snapshot_is_strict_frozen_and_fingerprinted() -> None:
    snapshot = _snapshot()
    assert snapshot.fingerprint == autonomous_loop_fingerprint(snapshot)
    with pytest.raises(ValidationError):
        snapshot.loop_id = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        AutonomousLoopSnapshot.model_validate(
            {**snapshot.model_dump(), "command": "git"}
        )


def test_snapshot_rejects_non_tuple_and_tamper() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValidationError):
        AutonomousLoopSnapshot.model_validate(
            {**snapshot.model_dump(), "completed_stages": []}
        )
    with pytest.raises(ValidationError):
        AutonomousLoopSnapshot.model_validate(
            {**snapshot.model_dump(), "fingerprint": "sha256:" + "0" * 64}
        )


def test_pending_action_and_repair_projection_are_safe() -> None:
    action = PendingAction.create(
        action_id="action-1",
        loop_id="loop-1",
        action_type="WORKSPACE_WRITE",
        action_fingerprint="sha256:" + "1" * 64,
    )
    assert action.approval_status is ApprovalStatus.PENDING
    proposal = RepairProposal.create(
        issue_summary="Validation failed",
        affected_area="firmware",
        suggested_change="Review generated proposal",
        evidence_reference="observation-1",
    )
    assert proposal.fingerprint.startswith("sha256:")
    with pytest.raises(ValidationError):
        RepairProposal.create(
            issue_summary="provider: secret",
            affected_area="firmware",
            suggested_change="change",
            evidence_reference="evidence-1",
        )
