"""v0.49 project projection adapter."""

from embedded_copilot.engineering_interface import EngineeringProjectProjection

from embedded_copilot.engineering_intelligence.exceptions import (
    EngineeringIntelligenceRejected,
)
from embedded_copilot.engineering_intelligence.models import (
    EngineeringProjectContextProjection,
    project_context_fingerprint,
)


def project_engineering_project(value: object) -> EngineeringProjectContextProjection:
    try:
        if type(value) is not EngineeringProjectProjection:
            raise TypeError("typed project is required")
        copied = value.model_copy(deep=True)
        checked = EngineeringProjectProjection.model_validate(copied)
        values = dict(
            project_id=checked.project_id,
            name=checked.name,
            summary=checked.summary,
            reference_ids=checked.reference_ids,
            source_fingerprint=checked.fingerprint,
        )
        return EngineeringProjectContextProjection(
            **values,
            fingerprint=project_context_fingerprint(**values),
        )
    except Exception:
        raise EngineeringIntelligenceRejected("intelligence request rejected") from None
