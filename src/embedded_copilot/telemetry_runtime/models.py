from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from embedded_copilot.debug_runtime import FrozenDebugSnapshot

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:#-]{0,159}$")
_METRIC = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")


class _TelemetryContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
    )


class TelemetrySourceType(StrEnum):
    DEBUG_RUNTIME = "DEBUG_RUNTIME"
    MOCK = "MOCK"


class TelemetryUnit(StrEnum):
    COUNT = "count"
    PERCENT = "percent"
    BYTES = "bytes"
    MILLISECONDS = "milliseconds"
    CELSIUS = "celsius"
    VOLTS = "volts"
    AMPERES = "amperes"
    HERTZ = "hertz"
    RPM = "rpm"
    METERS_PER_SECOND = "meters_per_second"


class TelemetryTrend(StrEnum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"


class TelemetryAnomalyDirection(StrEnum):
    BELOW_LOWER_BOUND = "BELOW_LOWER_BOUND"
    ABOVE_UPPER_BOUND = "ABOVE_UPPER_BOUND"


class TelemetryAuditEventType(StrEnum):
    SAMPLE_COLLECTED = "SAMPLE_COLLECTED"
    SAMPLE_COLLECTION_FAILED = "SAMPLE_COLLECTION_FAILED"
    SERIES_CREATED = "SERIES_CREATED"
    SERIES_CREATION_FAILED = "SERIES_CREATION_FAILED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} is invalid")
    candidate = unicodedata.normalize("NFC", value.strip())
    if not _IDENTIFIER.fullmatch(candidate):
        raise ValueError(f"{field} is invalid")
    return candidate


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone aware")
    return value.astimezone(timezone.utc)


def _number(value: object) -> int | float:
    if isinstance(value, bool):
        raise ValueError("numeric value is invalid")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("numeric value is invalid")


def _metric_number(value: object) -> int | float:
    candidate = _number(value)
    if isinstance(candidate, int):
        try:
            if math.isfinite(candidate):
                return candidate
        except OverflowError:
            pass
        raise ValueError("numeric value is invalid")
    return candidate


class TelemetryRequest(_TelemetryContract):
    target_id: str
    source_type: TelemetrySourceType
    observed_at: datetime

    @field_validator("target_id", mode="before")
    @classmethod
    def validate_target_id(cls, value: object) -> str:
        return _identifier(value, field="target_id")

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)


class TelemetrySeriesRequest(TelemetryRequest):
    series_id: str
    metric_name: str
    sample_count: int = Field(ge=2, le=256)

    @field_validator("series_id", mode="before")
    @classmethod
    def validate_series_id(cls, value: object) -> str:
        return _identifier(value, field="series_id")

    @field_validator("metric_name", mode="before")
    @classmethod
    def validate_metric_name(cls, value: object) -> str:
        if not isinstance(value, str) or not _METRIC.fullmatch(value.strip()):
            raise ValueError("metric_name is invalid")
        return value.strip()


class TelemetryMetric(_TelemetryContract):
    name: str
    value: int | float
    unit: TelemetryUnit

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return TelemetrySeriesRequest.validate_metric_name(value)

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> int | float:
        return _metric_number(value)


class TelemetrySample(_TelemetryContract):
    schema_version: Literal["1.0"] = "1.0"
    sample_id: str
    target_id: str
    source_type: TelemetrySourceType
    captured_at: datetime
    metrics: tuple[TelemetryMetric, ...] = Field(min_length=1, max_length=64)
    fingerprint: str

    @field_validator("sample_id", "target_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value.strip()):
            raise ValueError("fingerprint is invalid")
        return value.strip()

    @model_validator(mode="after")
    def validate_sample(self) -> "TelemetrySample":
        names = tuple(item.name for item in self.metrics)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("metrics must be sorted and unique")
        from embedded_copilot.telemetry_runtime.series import sample_fingerprint

        expected = sample_fingerprint(
            schema_version=self.schema_version,
            sample_id=self.sample_id,
            target_id=self.target_id,
            source_type=self.source_type,
            captured_at=self.captured_at,
            metrics=self.metrics,
        )
        if self.fingerprint != expected:
            raise ValueError("fingerprint does not match sample")
        return self


class DebugTelemetryContext(_TelemetryContract):
    sample_id: str
    debug_snapshot: FrozenDebugSnapshot

    @field_validator("sample_id", mode="before")
    @classmethod
    def validate_sample_id(cls, value: object) -> str:
        return _identifier(value, field="sample_id")

    def to_sample(self) -> TelemetrySample:
        from embedded_copilot.telemetry_runtime.series import build_sample

        return build_sample(
            sample_id=self.sample_id,
            target_id=self.debug_snapshot.telemetry.target_id,
            source_type=TelemetrySourceType.DEBUG_RUNTIME,
            captured_at=self.debug_snapshot.telemetry.captured_at,
            metrics=tuple(
                TelemetryMetric(
                    name=item.name,
                    value=item.value,
                    unit=TelemetryUnit(item.unit.value),
                )
                for item in self.debug_snapshot.telemetry.metrics
            ),
        )


class TelemetrySeriesPoint(_TelemetryContract):
    sample_id: str
    captured_at: datetime
    value: int | float

    @field_validator("sample_id", mode="before")
    @classmethod
    def validate_sample_id(cls, value: object) -> str:
        return _identifier(value, field="sample_id")

    @field_validator("captured_at")
    @classmethod
    def validate_captured_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> int | float:
        return _metric_number(value)


class TelemetrySeriesSnapshot(_TelemetryContract):
    schema_version: Literal["1.0"] = "1.0"
    series_id: str
    target_id: str
    source_type: TelemetrySourceType
    metric_name: str
    unit: TelemetryUnit
    samples: tuple[TelemetrySeriesPoint, ...] = Field(min_length=2, max_length=256)
    fingerprint: str

    @field_validator("series_id", "target_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value: object, info) -> str:
        return _identifier(value, field=info.field_name)

    @field_validator("metric_name", mode="before")
    @classmethod
    def validate_metric_name(cls, value: object) -> str:
        return TelemetrySeriesRequest.validate_metric_name(value)

    @field_validator("fingerprint", mode="before")
    @classmethod
    def validate_fingerprint(cls, value: object) -> str:
        return TelemetrySample.validate_fingerprint(value)

    @model_validator(mode="after")
    def validate_series(self) -> "TelemetrySeriesSnapshot":
        ordering = tuple((item.captured_at, item.sample_id) for item in self.samples)
        sample_ids = tuple(item.sample_id for item in self.samples)
        if ordering != tuple(sorted(ordering)) or len(sample_ids) != len(
            set(sample_ids)
        ):
            raise ValueError("series samples must be sorted and unique")
        from embedded_copilot.telemetry_runtime.series import series_fingerprint

        expected = series_fingerprint(
            schema_version=self.schema_version,
            series_id=self.series_id,
            target_id=self.target_id,
            source_type=self.source_type,
            metric_name=self.metric_name,
            unit=self.unit,
            samples=self.samples,
        )
        if self.fingerprint != expected:
            raise ValueError("fingerprint does not match series")
        return self


class TelemetryAnalysisRequest(_TelemetryContract):
    series: TelemetrySeriesSnapshot
    lower_bound: int | float | None = None
    upper_bound: int | float | None = None
    observed_at: datetime

    @field_validator("lower_bound", "upper_bound", mode="before")
    @classmethod
    def validate_bounds(cls, value: object) -> int | float | None:
        return None if value is None else _number(value)

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def validate_bound_order(self) -> "TelemetryAnalysisRequest":
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("lower_bound must not exceed upper_bound")
        return self


class TelemetryStatistics(_TelemetryContract):
    minimum: int | float
    maximum: int | float
    average: float
    delta: int | float
    sample_count: int = Field(ge=2, le=256)

    @field_validator("minimum", "maximum", "average", "delta", mode="before")
    @classmethod
    def validate_numbers(cls, value: object) -> int | float:
        return _number(value)


class TelemetryAnomalyCandidate(_TelemetryContract):
    candidate_semantics: Literal["unverified"] = "unverified"
    directions: tuple[TelemetryAnomalyDirection, ...] = Field(
        min_length=1,
        max_length=2,
    )
    lower_bound: int | float | None = None
    upper_bound: int | float | None = None
    observed_minimum: int | float
    observed_maximum: int | float
    review_required: Literal[True] = True

    @field_validator(
        "lower_bound",
        "upper_bound",
        "observed_minimum",
        "observed_maximum",
        mode="before",
    )
    @classmethod
    def validate_numbers(cls, value: object) -> int | float | None:
        return None if value is None else _number(value)

    @model_validator(mode="after")
    def validate_candidate(self) -> "TelemetryAnomalyCandidate":
        expected = tuple(
            direction
            for direction in (
                TelemetryAnomalyDirection.BELOW_LOWER_BOUND,
                TelemetryAnomalyDirection.ABOVE_UPPER_BOUND,
            )
            if direction in self.directions
        )
        if self.directions != expected or len(set(self.directions)) != len(
            self.directions
        ):
            raise ValueError("directions must use fixed unique order")
        return self


class TelemetryAnalysisResult(_TelemetryContract):
    statistics: TelemetryStatistics
    trend: TelemetryTrend
    anomaly_candidate: TelemetryAnomalyCandidate | None = None


class TelemetryAuditEvent(_TelemetryContract):
    event_type: TelemetryAuditEventType
    target_id: str
    source_type: TelemetrySourceType
    timestamp: datetime

    @field_validator("target_id", mode="before")
    @classmethod
    def validate_target_id(cls, value: object) -> str:
        return _identifier(value, field="target_id")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)
