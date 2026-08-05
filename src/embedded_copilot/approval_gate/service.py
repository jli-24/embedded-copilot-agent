from __future__ import annotations

import copy

from .contracts import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalGatePort,
    validate_approval_action,
)
from .exceptions import ActionApprovalRequired
from .models import identifier


class ApprovalGateService:
    __slots__ = ("_port",)

    def __init__(self, port: ApprovalGatePort) -> None:
        if not isinstance(port, ApprovalGatePort):
            raise TypeError("approval gate port is invalid")
        self._port = port

    def get_action(self, action_id: str) -> ApprovalAction | None:
        action = self._port.get_action(identifier(action_id, field="action_id"))
        return None if action is None else validate_approval_action(action)

    def approve(self, decision: ApprovalDecision) -> ApprovalAction:
        checked = ApprovalDecision.model_validate(
            copy.deepcopy(decision.model_dump(mode="python"))
        )
        action = self.get_action(checked.action_id)
        if action is None:
            raise ActionApprovalRequired()
        if action.fingerprint != checked.action_fingerprint:
            raise ActionApprovalRequired()
        return validate_approval_action(self._port.approve(checked))

    def reject(self, decision: ApprovalDecision) -> ApprovalAction:
        checked = ApprovalDecision.model_validate(
            copy.deepcopy(decision.model_dump(mode="python"))
        )
        action = self.get_action(checked.action_id)
        if action is None or action.fingerprint != checked.action_fingerprint:
            raise ActionApprovalRequired()
        return validate_approval_action(self._port.reject(checked))
