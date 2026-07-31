from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.workflow_runtime.exceptions import WorkflowRiskRejected
from embedded_copilot.workflow_runtime.models import (
    WorkflowContextProjection,
    WorkflowRiskItem,
    WorkflowRiskProjection,
    workflow_risk_fingerprint,
)


def project_workflow_risks(
    context: WorkflowContextProjection,
) -> WorkflowRiskProjection:
    source_by_key = {
        (source.source_type, source.source_id, source.reference): source
        for source in context.verified_source_references
    }
    checked: list[WorkflowRiskItem] = []
    for risk in context.projected_risks:
        source = source_by_key.get((risk.source_type, risk.source_id, risk.reference))
        if source is None or risk.confidence > source.confidence:
            raise WorkflowRiskRejected("workflow risk projection was rejected")
        checked.append(risk.model_copy(deep=True))
    ordered = tuple(
        sorted(
            checked,
            key=lambda item: (
                item.risk_type,
                item.source_type.value,
                item.source_id,
                item.reference,
            ),
        )
    )
    try:
        return WorkflowRiskProjection(
            risks=ordered,
            fingerprint=workflow_risk_fingerprint(ordered),
        )
    except (TypeError, ValueError, ValidationError):
        raise WorkflowRiskRejected("workflow risk projection was rejected") from None
