from __future__ import annotations

import copy
from datetime import datetime

from pydantic import ValidationError

from embedded_copilot.debug_runtime.exceptions import DebugObservationRejected
from embedded_copilot.debug_runtime.models import (
    DebugSourceType,
    TelemetryMetric,
    TelemetrySnapshot,
)


def normalized_metrics(
    value: object,
) -> tuple[TelemetryMetric, ...]:
    if not isinstance(value, tuple):
        raise DebugObservationRejected
    try:
        metrics = tuple(
            TelemetryMetric.model_validate(
                copy.deepcopy(item.model_dump(mode="python"))
            )
            for item in value
        )
    except (AttributeError, TypeError, ValidationError):
        raise DebugObservationRejected from None
    if len(metrics) > 64:
        raise DebugObservationRejected
    names = tuple(item.name.casefold() for item in metrics)
    if len(names) != len(set(names)):
        raise DebugObservationRejected
    return tuple(sorted(metrics, key=lambda item: item.name.casefold()))


def build_telemetry(
    *,
    target_id: str,
    source_type: DebugSourceType,
    captured_at: datetime,
    metrics: object,
) -> TelemetrySnapshot:
    try:
        return TelemetrySnapshot(
            target_id=target_id,
            source_type=source_type,
            captured_at=captured_at,
            metrics=normalized_metrics(metrics),
        )
    except ValidationError:
        raise DebugObservationRejected from None
