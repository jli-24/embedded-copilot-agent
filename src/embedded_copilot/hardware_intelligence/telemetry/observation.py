"""Structured observation normalization without transport access."""

from pydantic import ValidationError

from embedded_copilot.hardware_intelligence.exceptions import (
    HardwareObservationRejected,
)
from embedded_copilot.hardware_intelligence.models import HardwareObservation


def normalize_observations(value: object) -> tuple[HardwareObservation, ...]:
    """Return a deterministic, deeply revalidated observation tuple."""
    if type(value) is not tuple or not value or len(value) > 256:
        raise HardwareObservationRejected("hardware observations rejected")
    try:
        observations = tuple(
            (
                HardwareObservation.model_validate(item.model_copy(deep=True))
                if type(item) is HardwareObservation
                else _reject()
            )
            for item in value
        )
    except (TypeError, ValueError, ValidationError):
        raise HardwareObservationRejected("hardware observations rejected") from None
    normalized = tuple(
        sorted(
            observations,
            key=lambda item: (item.timestamp, item.sensor_id, item.metric_name),
        )
    )
    identities = tuple(
        (item.timestamp, item.sensor_id, item.metric_name) for item in normalized
    )
    if len(identities) != len(set(identities)):
        raise HardwareObservationRejected("hardware observations rejected")
    return normalized


def _reject() -> HardwareObservation:
    raise HardwareObservationRejected("hardware observations rejected")
