"""Typed digital-twin projection validation."""

from pydantic import ValidationError

from embedded_copilot.hardware_intelligence.exceptions import (
    HardwareIntelligenceRejected,
)
from embedded_copilot.hardware_intelligence.models import DigitalTwinProjection


def validate_digital_twin(value: object) -> DigitalTwinProjection:
    """Deep-copy and revalidate a caller-owned typed projection."""
    if type(value) is not DigitalTwinProjection:
        raise HardwareIntelligenceRejected("digital twin projection rejected")
    try:
        copied = value.model_copy(deep=True)
        return DigitalTwinProjection.model_validate(copied)
    except (TypeError, ValueError, ValidationError):
        raise HardwareIntelligenceRejected("digital twin projection rejected") from None
