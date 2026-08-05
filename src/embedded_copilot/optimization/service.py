from __future__ import annotations

import copy

from embedded_copilot.debug_analysis.contracts import DebugFinding

from .contracts import (
    OptimizationConfidence,
    OptimizationProposal,
    OptimizationReasoningPort,
    OptimizationStatus,
    OptimizationTargetArea,
    validate_optimization_proposal,
)
from .exceptions import OptimizationRejected
from .models import proposal_id


class OptimizationService:
    __slots__ = ("_reasoning",)

    def __init__(self, reasoning: OptimizationReasoningPort | None = None) -> None:
        if reasoning is not None and not isinstance(reasoning, OptimizationReasoningPort):
            raise TypeError("optimization reasoning port is invalid")
        self._reasoning = reasoning

    def propose(self, finding: DebugFinding) -> OptimizationProposal:
        try:
            checked = DebugFinding.model_validate(copy.deepcopy(finding))
            projection = (
                self._reasoning.project(copy.deepcopy(checked))
                if self._reasoning is not None
                else None
            )
            if projection is None:
                values = {
                    "target_area": OptimizationTargetArea.TEST,
                    "suggested_change": "Add a targeted verification step for the observed failure.",
                    "reason": checked.summary,
                    "evidence_reference": checked.evidence_reference,
                    "risk": "Requires human review before any engineering change.",
                    "confidence": OptimizationConfidence.PROJECTED,
                }
            else:
                values = projection.model_dump(mode="python")
            return OptimizationProposal.create(
                proposal_id=proposal_id(checked.project_id, checked.evidence_reference),
                project_id=checked.project_id,
                status=OptimizationStatus.PROPOSED,
                **values,
            )
        except Exception as error:
            raise OptimizationRejected() from error


__all__ = ["OptimizationService"]
