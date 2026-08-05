from __future__ import annotations

import copy

from ..contracts import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalGatePort,
    ApprovalStatus,
)
from ..exceptions import ApprovalExpired, ApprovalRejected


class FakeApprovalGate(ApprovalGatePort):
    def __init__(self, actions: tuple[ApprovalAction, ...] = ()) -> None:
        self._actions = {item.action_id: item for item in actions}

    def get_action(self, action_id: str) -> ApprovalAction | None:
        value = self._actions.get(action_id)
        return None if value is None else copy.deepcopy(value)

    def approve(self, decision: ApprovalDecision) -> ApprovalAction:
        action = self._actions[decision.action_id]
        if action.approval_status is not ApprovalStatus.PENDING:
            raise ApprovalRejected()
        checked = ApprovalAction.create(
            **{
                **action.model_dump(mode="python"),
                "approval_status": ApprovalStatus.APPROVED,
                "fingerprint": None,
            }
        )
        self._actions[action.action_id] = checked
        return copy.deepcopy(checked)

    def reject(self, decision: ApprovalDecision) -> ApprovalAction:
        action = self._actions[decision.action_id]
        if action.approval_status is not ApprovalStatus.PENDING:
            raise ApprovalRejected()
        updated = ApprovalAction.create(
            **{
                **action.model_dump(mode="python"),
                "approval_status": ApprovalStatus.REJECTED,
                "fingerprint": None,
            }
        )
        self._actions[action.action_id] = updated
        return copy.deepcopy(updated)

    def expire(self, action_id: str) -> ApprovalAction:
        action = self._actions[action_id]
        if action.approval_status is not ApprovalStatus.PENDING:
            raise ApprovalExpired()
        updated = ApprovalAction.create(
            **{
                **action.model_dump(mode="python"),
                "approval_status": ApprovalStatus.EXPIRED,
                "fingerprint": None,
            }
        )
        self._actions[action.action_id] = updated
        return copy.deepcopy(updated)
