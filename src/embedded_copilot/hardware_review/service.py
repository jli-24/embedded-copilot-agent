from __future__ import annotations

import copy

from embedded_copilot.hardware_design.contracts import validate_unified_hardware_model
from embedded_copilot.hardware_design.models import _v22_id

from .contracts import (
    HardwareReviewCategory,
    HardwareReviewPort,
    HardwareReviewProposal,
    HardwareReviewSeverity,
    HardwareReviewStatus,
    validate_review_proposals,
)
from .exceptions import ReviewRejected
from .models import review_id


class HardwareReviewService:
    __slots__ = ("_port",)

    def __init__(self, port: HardwareReviewPort) -> None:
        if not isinstance(port, HardwareReviewPort):
            raise TypeError("hardware review port is invalid")
        self._port = port

    def get_snapshot(
        self, project_id: str
    ) -> tuple[HardwareReviewProposal, ...] | None:
        try:
            project = _v22_id(project_id, field="project_id")
            result = self._port.get_snapshot(copy.deepcopy(project))
            if result is None:
                return None
            checked = validate_review_proposals(result)
            if any(item.project_id != project for item in checked):
                raise ValueError("review project binding mismatch")
            return checked
        except ReviewRejected:
            raise
        except Exception as error:
            raise ReviewRejected() from error

    @staticmethod
    def review(model: object) -> tuple[HardwareReviewProposal, ...]:
        checked = validate_unified_hardware_model(model)
        findings: list[HardwareReviewProposal] = []
        index = 1
        for component in checked.components:
            if (
                not component.manufacturer
                or not component.part_number
                or not component.footprint
            ):
                findings.append(
                    HardwareReviewProposal.create(
                        review_id=review_id(checked.project_id, "COMPONENT", index),
                        project_id=checked.project_id,
                        category=HardwareReviewCategory.COMPONENT,
                        severity=HardwareReviewSeverity.MEDIUM,
                        summary=f"Component {component.reference} lacks a complete identity projection.",
                        evidence_reference=checked.references[0]
                        if checked.references
                        else f"design:{checked.design_id}",
                        status=HardwareReviewStatus.PROJECTED,
                    )
                )
                index += 1
        for interface in checked.interfaces:
            if not interface.signals:
                findings.append(
                    HardwareReviewProposal.create(
                        review_id=review_id(checked.project_id, "SIGNAL", index),
                        project_id=checked.project_id,
                        category=HardwareReviewCategory.SIGNAL,
                        severity=HardwareReviewSeverity.HIGH,
                        summary=f"Interface {interface.name} has no projected signals.",
                        evidence_reference=checked.references[0]
                        if checked.references
                        else f"design:{checked.design_id}",
                        status=HardwareReviewStatus.UNVERIFIED,
                    )
                )
                index += 1
        if not checked.constraints:
            findings.append(
                HardwareReviewProposal.create(
                    review_id=review_id(checked.project_id, "LAYOUT", index),
                    project_id=checked.project_id,
                    category=HardwareReviewCategory.LAYOUT,
                    severity=HardwareReviewSeverity.LOW,
                    summary="No explicit design constraints were projected.",
                    evidence_reference=checked.references[0]
                    if checked.references
                    else f"design:{checked.design_id}",
                    status=HardwareReviewStatus.UNVERIFIED,
                )
            )
        return tuple(findings)
