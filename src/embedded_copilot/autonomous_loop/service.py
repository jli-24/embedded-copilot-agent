from __future__ import annotations

import copy

from embedded_copilot.approval_gate.contracts import ApprovalStatus
from embedded_copilot.approval_gate.contracts import ApprovalDecision, ApprovalGatePort
from embedded_copilot.approval_gate.exceptions import ApprovalRejected

from .contracts import (
    AutonomousLoopSnapshot,
    LoopStage,
    LoopStatePort,
    LoopTimelineItem,
    LoopViewStatus,
    validate_snapshot,
)
from .exceptions import ActionApprovalRequired, InvalidTransition, LoopNotFound
from .models import fingerprint, identifier


_NEXT_STAGE: dict[LoopStage, LoopStage] = {
    LoopStage.INITIALIZING: LoopStage.PLANNING,
    LoopStage.PLANNING: LoopStage.GENERATING,
    LoopStage.GENERATING: LoopStage.BUILDING,
    LoopStage.BUILDING: LoopStage.VALIDATING,
    LoopStage.VALIDATING: LoopStage.ANALYZING,
    LoopStage.ANALYZING: LoopStage.WAITING_APPROVAL,
    LoopStage.WAITING_APPROVAL: LoopStage.COMPLETED,
}


class LoopCoordinatorService:
    __slots__ = (
        "_state",
        "_approval_gate",
        "_generation",
        "_build",
        "_validation",
        "_reasoning",
        "_memory",
    )

    def __init__(
        self,
        state_port: LoopStatePort,
        approval_gate: ApprovalGatePort | None = None,
        *,
        generation_port: object | None = None,
        build_port: object | None = None,
        validation_port: object | None = None,
        reasoning_port: object | None = None,
        memory_port: object | None = None,
    ) -> None:
        if not isinstance(state_port, LoopStatePort):
            raise TypeError("loop state port is invalid")
        if approval_gate is not None and not isinstance(
            approval_gate, ApprovalGatePort
        ):
            raise TypeError("approval gate port is invalid")
        self._state = state_port
        self._approval_gate = approval_gate
        self._generation = generation_port
        self._build = build_port
        self._validation = validation_port
        self._reasoning = reasoning_port
        self._memory = memory_port

    def get_snapshot(self, project_id: str) -> AutonomousLoopSnapshot | None:
        checked_project = identifier(project_id, field="project_id")
        result = self._state.get_snapshot(copy.deepcopy(checked_project))
        return None if result is None else validate_snapshot(result)

    def resume(
        self, project_id: str, expected_fingerprint: str | None = None
    ) -> AutonomousLoopSnapshot:
        snapshot = self.get_snapshot(project_id)
        if snapshot is None:
            raise LoopNotFound()
        if (
            expected_fingerprint is not None
            and fingerprint(expected_fingerprint) != snapshot.fingerprint
        ):
            raise InvalidTransition()
        if snapshot.current_stage in {LoopStage.COMPLETED, LoopStage.FAILED}:
            raise InvalidTransition()
        if (
            snapshot.pending_action is not None
            and snapshot.approval_status is not ApprovalStatus.APPROVED
        ):
            raise ActionApprovalRequired()
        next_stage = _NEXT_STAGE.get(snapshot.current_stage)
        if next_stage is None:
            raise InvalidTransition()
        updated = AutonomousLoopSnapshot.create(
            project_id=snapshot.project_id,
            loop_id=snapshot.loop_id,
            current_stage=next_stage,
            completed_stages=(*snapshot.completed_stages, snapshot.current_stage),
            pending_action=None,
            approval_status=ApprovalStatus.PENDING,
            iteration=snapshot.iteration + 1,
            timeline=(
                *snapshot.timeline,
                LoopTimelineItem(
                    stage=next_stage,
                    status=LoopViewStatus.RUNNING.value,
                    label=next_stage.value.title(),
                ),
            ),
        )
        return validate_snapshot(self._state.save_snapshot(copy.deepcopy(updated)))

    def approve(
        self, action_id: str, decision: ApprovalDecision
    ) -> AutonomousLoopSnapshot:
        if self._approval_gate is None:
            raise ActionApprovalRequired()
        action = self._approval_gate.approve(copy.deepcopy(decision))
        snapshot = self.get_snapshot(action.loop_id)
        if snapshot is None:
            raise LoopNotFound()
        updated = AutonomousLoopSnapshot.create(
            project_id=snapshot.project_id,
            loop_id=snapshot.loop_id,
            current_stage=snapshot.current_stage,
            completed_stages=snapshot.completed_stages,
            pending_action=None,
            approval_status=ApprovalStatus.APPROVED,
            iteration=snapshot.iteration,
            timeline=snapshot.timeline,
        )
        return validate_snapshot(self._state.save_snapshot(copy.deepcopy(updated)))

    def reject(
        self, action_id: str, decision: ApprovalDecision
    ) -> AutonomousLoopSnapshot:
        if self._approval_gate is None:
            raise ActionApprovalRequired()
        self._approval_gate.reject(copy.deepcopy(decision))
        raise ApprovalRejected()
