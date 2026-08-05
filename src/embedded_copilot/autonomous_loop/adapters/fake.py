from __future__ import annotations

import copy

from embedded_copilot.approval_gate.contracts import ApprovalStatus

from ..contracts import (
    AutonomousLoopSnapshot,
    LoopStage,
    LoopStatePort,
    LoopTimelineItem,
)


class FakeLoopStatePort(LoopStatePort):
    def __init__(self, snapshot: AutonomousLoopSnapshot) -> None:
        self._snapshot = copy.deepcopy(snapshot)

    def get_snapshot(self, project_id: str) -> AutonomousLoopSnapshot | None:
        if project_id != self._snapshot.project_id:
            return None
        return copy.deepcopy(self._snapshot)

    def save_snapshot(self, snapshot: AutonomousLoopSnapshot) -> AutonomousLoopSnapshot:
        self._snapshot = copy.deepcopy(snapshot)
        return copy.deepcopy(self._snapshot)


def initial_snapshot(*, project_id: str, loop_id: str) -> AutonomousLoopSnapshot:
    return AutonomousLoopSnapshot.create(
        project_id=project_id,
        loop_id=loop_id,
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


__all__ = ["FakeLoopStatePort", "initial_snapshot"]
