"""Pure HIL reference projection; no hardware control is performed."""

from embedded_copilot.hardware_intelligence.models import (
    HILProjection,
    HILProjectionStatus,
    hil_projection_fingerprint,
)


def create_hil_projection(
    *, scenario_id: str, twin_fingerprint: str, observation_fingerprint: str
) -> HILProjection:
    return HILProjection(
        scenario_id=scenario_id,
        input_reference=twin_fingerprint,
        observation_reference=observation_fingerprint,
        status=HILProjectionStatus.OBSERVED,
        fingerprint=hil_projection_fingerprint(
            scenario_id=scenario_id,
            input_reference=twin_fingerprint,
            observation_reference=observation_fingerprint,
            status=HILProjectionStatus.OBSERVED,
        ),
    )
