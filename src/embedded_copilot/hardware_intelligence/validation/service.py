"""Typed validation-result binding checks."""

from pydantic import ValidationError

from embedded_copilot.hardware_intelligence.exceptions import (
    HardwareIntelligenceRejected,
)
from embedded_copilot.hardware_intelligence.models import (
    HardwareValidationProjection,
    HardwareValidationRequest,
)


def validate_projection(
    value: object, *, request: HardwareValidationRequest
) -> HardwareValidationProjection:
    if type(value) is not HardwareValidationProjection:
        raise HardwareIntelligenceRejected("hardware validation rejected")
    try:
        projection = HardwareValidationProjection.model_validate(
            value.model_copy(deep=True)
        )
    except (TypeError, ValueError, ValidationError):
        raise HardwareIntelligenceRejected("hardware validation rejected") from None
    if (
        projection.hardware_id != request.context.hardware_id
        or projection.twin_fingerprint != request.digital_twin.fingerprint
        or projection.observation_fingerprint != request.observation_fingerprint
    ):
        raise HardwareIntelligenceRejected("hardware validation rejected")
    return projection
