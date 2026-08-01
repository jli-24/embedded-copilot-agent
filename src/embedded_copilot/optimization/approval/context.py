"""Fingerprint-bound human decision for an evaluated optimization proposal."""

from __future__ import annotations

from datetime import datetime

from pydantic import field_validator, model_validator

from embedded_copilot.optimization.models import (
    _OptimizationContract,
    OptimizationApprovalDecision,
    _checked_fingerprint,
    _fingerprint,
    _identifier,
    _utc,
)


def optimization_approval_fingerprint(
    *,
    optimization_id: str,
    evaluated_snapshot_fingerprint: str,
    proposal_fingerprint: str,
    evaluation_fingerprint: str,
    decision: OptimizationApprovalDecision,
    reviewer: str,
    timestamp: datetime,
) -> str:
    return _fingerprint(
        {
            "decision": decision.value,
            "evaluated_snapshot_fingerprint": evaluated_snapshot_fingerprint,
            "evaluation_fingerprint": evaluation_fingerprint,
            "optimization_id": optimization_id,
            "proposal_fingerprint": proposal_fingerprint,
            "reviewer": reviewer,
            "timestamp": timestamp.isoformat(),
        }
    )


class OptimizationApprovalContext(_OptimizationContract):
    optimization_id: str
    evaluated_snapshot_fingerprint: str
    proposal_fingerprint: str
    evaluation_fingerprint: str
    decision: OptimizationApprovalDecision
    reviewer: str
    timestamp: datetime
    fingerprint: str

    _optimization_id = field_validator("optimization_id")(
        lambda value: _identifier(value, field="optimization_id")
    )
    _evaluated_snapshot_fingerprint = field_validator("evaluated_snapshot_fingerprint")(
        _checked_fingerprint
    )
    _proposal_fingerprint = field_validator("proposal_fingerprint")(
        _checked_fingerprint
    )
    _evaluation_fingerprint = field_validator("evaluation_fingerprint")(
        _checked_fingerprint
    )
    _reviewer = field_validator("reviewer")(
        lambda value: _identifier(value, field="reviewer")
    )
    _timestamp = field_validator("timestamp")(_utc)
    _fingerprint_format = field_validator("fingerprint")(_checked_fingerprint)

    @model_validator(mode="after")
    def _fingerprint_matches(self) -> OptimizationApprovalContext:
        if self.fingerprint != optimization_approval_fingerprint(
            optimization_id=self.optimization_id,
            evaluated_snapshot_fingerprint=self.evaluated_snapshot_fingerprint,
            proposal_fingerprint=self.proposal_fingerprint,
            evaluation_fingerprint=self.evaluation_fingerprint,
            decision=self.decision,
            reviewer=self.reviewer,
            timestamp=self.timestamp,
        ):
            raise ValueError("approval fingerprint mismatch")
        return self
