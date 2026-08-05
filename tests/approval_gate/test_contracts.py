from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.approval_gate.contracts import (
    ApprovalAction,
    ApprovalDecision,
    ApprovalStatus,
    approval_action_fingerprint,
)


def test_approval_action_binding_and_safe_decision() -> None:
    action = ApprovalAction.create(
        action_id="action-1",
        loop_id="loop-1",
        action_type="FLASH",
        action_fingerprint="sha256:" + "1" * 64,
        approval_status=ApprovalStatus.PENDING,
    )
    assert action.fingerprint == approval_action_fingerprint(action)
    decision = ApprovalDecision(
        action_id="action-1",
        action_fingerprint=action.fingerprint,
        reviewer="reviewer-1",
        decided_at="2026-08-01T00:00:00Z",
    )
    assert decision.action_id == action.action_id
    with pytest.raises(ValidationError):
        ApprovalAction.model_validate({**action.model_dump(), "path": "private"})
