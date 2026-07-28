from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone

from pydantic import ValidationError

from embedded_copilot.telemetry_runtime.exceptions import TelemetryDataRejected
from embedded_copilot.telemetry_runtime.models import (
    TelemetryMetric,
    TelemetrySample,
    TelemetrySeriesPoint,
    TelemetrySeriesSnapshot,
    TelemetrySourceType,
    TelemetryUnit,
)


def _digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def normalized_metrics(value: object) -> tuple[TelemetryMetric, ...]:
    if not isinstance(value, tuple):
        raise TelemetryDataRejected
    try:
        metrics = tuple(
            TelemetryMetric.model_validate(
                copy.deepcopy(item.model_dump(mode="python"))
            )
            for item in value
        )
    except (AttributeError, TypeError, ValidationError):
        raise TelemetryDataRejected from None
    names = tuple(item.name for item in metrics)
    if not 1 <= len(metrics) <= 64 or len(names) != len(set(names)):
        raise TelemetryDataRejected
    return tuple(sorted(metrics, key=lambda item: item.name))


def sample_fingerprint(
    *,
    schema_version: str,
    sample_id: str,
    target_id: str,
    source_type: TelemetrySourceType,
    captured_at: datetime,
    metrics: tuple[TelemetryMetric, ...],
) -> str:
    return _digest(
        {
            "captured_at": captured_at.isoformat(),
            "metrics": [item.model_dump(mode="json") for item in metrics],
            "sample_id": sample_id,
            "schema_version": schema_version,
            "source_type": source_type.value,
            "target_id": target_id,
        }
    )


def build_sample(
    *,
    sample_id: str,
    target_id: str,
    source_type: TelemetrySourceType,
    captured_at: datetime,
    metrics: object,
) -> TelemetrySample:
    normalized = normalized_metrics(metrics)
    try:
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError
        normalized_captured_at = captured_at.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise TelemetryDataRejected from None
    fingerprint = sample_fingerprint(
        schema_version="1.0",
        sample_id=sample_id,
        target_id=target_id,
        source_type=source_type,
        captured_at=normalized_captured_at,
        metrics=normalized,
    )
    try:
        return TelemetrySample(
            sample_id=sample_id,
            target_id=target_id,
            source_type=source_type,
            captured_at=normalized_captured_at,
            metrics=normalized,
            fingerprint=fingerprint,
        )
    except ValidationError:
        raise TelemetryDataRejected from None


def isolated_sample(value: object) -> TelemetrySample:
    try:
        return TelemetrySample.model_validate(
            copy.deepcopy(value.model_dump(mode="python"))
        )
    except (AttributeError, TypeError, ValidationError):
        raise TelemetryDataRejected from None


def series_fingerprint(
    *,
    schema_version: str,
    series_id: str,
    target_id: str,
    source_type: TelemetrySourceType,
    metric_name: str,
    unit: TelemetryUnit,
    samples: tuple[TelemetrySeriesPoint, ...],
) -> str:
    return _digest(
        {
            "metric_name": metric_name,
            "samples": [item.model_dump(mode="json") for item in samples],
            "schema_version": schema_version,
            "series_id": series_id,
            "source_type": source_type.value,
            "target_id": target_id,
            "unit": unit.value,
        }
    )


def build_series(
    *,
    series_id: str,
    target_id: str,
    source_type: TelemetrySourceType,
    metric_name: str,
    samples: tuple[TelemetrySample, ...],
) -> TelemetrySeriesSnapshot:
    points: list[TelemetrySeriesPoint] = []
    units: list[TelemetryUnit] = []
    sample_ids: list[str] = []
    for sample in samples:
        metric = next(
            (item for item in sample.metrics if item.name == metric_name),
            None,
        )
        if metric is None:
            raise TelemetryDataRejected
        sample_ids.append(sample.sample_id)
        units.append(metric.unit)
        points.append(
            TelemetrySeriesPoint(
                sample_id=sample.sample_id,
                captured_at=sample.captured_at,
                value=metric.value,
            )
        )
    if len(sample_ids) != len(set(sample_ids)) or len(set(units)) != 1:
        raise TelemetryDataRejected
    ordered = tuple(sorted(points, key=lambda item: (item.captured_at, item.sample_id)))
    fingerprint = series_fingerprint(
        schema_version="1.0",
        series_id=series_id,
        target_id=target_id,
        source_type=source_type,
        metric_name=metric_name,
        unit=units[0],
        samples=ordered,
    )
    try:
        return TelemetrySeriesSnapshot(
            series_id=series_id,
            target_id=target_id,
            source_type=source_type,
            metric_name=metric_name,
            unit=units[0],
            samples=ordered,
            fingerprint=fingerprint,
        )
    except ValidationError:
        raise TelemetryDataRejected from None
