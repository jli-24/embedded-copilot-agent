from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn, TypeVar

from pydantic import BaseModel

from embedded_copilot.telemetry_runtime.analysis import analyze_series
from embedded_copilot.telemetry_runtime.audit import emit_audit
from embedded_copilot.telemetry_runtime.exceptions import (
    TelemetryDataRejected,
    TelemetryObservationTimeout,
    TelemetrySourceUnavailable,
)
from embedded_copilot.telemetry_runtime.models import (
    TelemetryAnalysisRequest,
    TelemetryAnalysisResult,
    TelemetryAuditEventType,
    TelemetryRequest,
    TelemetrySample,
    TelemetrySeriesRequest,
    TelemetrySeriesSnapshot,
    TelemetrySourceType,
)
from embedded_copilot.telemetry_runtime.ports import (
    TelemetryAuditSink,
    TelemetryPort,
    TelemetrySourcePort,
)
from embedded_copilot.telemetry_runtime.series import (
    build_series,
    isolated_sample,
)

_RequestT = TypeVar("_RequestT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class _SourceAdapter:
    source_type: TelemetrySourceType
    source: TelemetrySourcePort

    def read_sample(self, target_id: str) -> TelemetrySample:
        return self.source.read_sample(target_id)


class TelemetryRuntime:
    __slots__ = ("_telemetry_port",)

    def __init__(self, telemetry_port: TelemetryPort) -> None:
        raise TypeError("TelemetryRuntime must be created by the composition factory")

    @classmethod
    def _compose(cls, telemetry_port: TelemetryPort) -> "TelemetryRuntime":
        if not isinstance(telemetry_port, TelemetryPort):
            raise TypeError("telemetry port is invalid")
        runtime = object.__new__(cls)
        object.__setattr__(runtime, "_telemetry_port", telemetry_port)
        return runtime

    def telemetry_port(self) -> TelemetryPort:
        return self._telemetry_port


class _TelemetryPort:
    __slots__ = ("_adapters", "_audit_sink")

    def __init__(
        self,
        adapters: tuple[_SourceAdapter, ...],
        audit_sink: TelemetryAuditSink,
    ) -> None:
        self._adapters = adapters
        self._audit_sink = audit_sink

    def collect_sample(self, request: TelemetryRequest) -> TelemetrySample:
        request = _validated_request(TelemetryRequest, request)
        try:
            source = self._source(request.source_type)
            sample = isolated_sample(source.read_sample(request.target_id))
            _validate_sample_binding(sample, request)
        except Exception as error:
            self._audit(
                TelemetryAuditEventType.SAMPLE_COLLECTION_FAILED,
                request,
            )
            _raise_source_error(error)
        self._audit(TelemetryAuditEventType.SAMPLE_COLLECTED, request)
        return sample

    def collect_series(
        self,
        request: TelemetrySeriesRequest,
    ) -> TelemetrySeriesSnapshot:
        request = _validated_request(TelemetrySeriesRequest, request)
        try:
            source = self._source(request.source_type)
            samples = tuple(
                isolated_sample(source.read_sample(request.target_id))
                for _ in range(request.sample_count)
            )
            for sample in samples:
                _validate_sample_binding(sample, request)
            series = build_series(
                series_id=request.series_id,
                target_id=request.target_id,
                source_type=request.source_type,
                metric_name=request.metric_name,
                samples=samples,
            )
        except Exception as error:
            self._audit(
                TelemetryAuditEventType.SERIES_CREATION_FAILED,
                request,
            )
            _raise_source_error(error)
        self._audit(TelemetryAuditEventType.SERIES_CREATED, request)
        return series

    def analyze_signal(
        self,
        request: TelemetryAnalysisRequest,
    ) -> TelemetryAnalysisResult:
        request = _validated_request(TelemetryAnalysisRequest, request)
        try:
            result = analyze_series(
                series=request.series,
                lower_bound=request.lower_bound,
                upper_bound=request.upper_bound,
            )
        except Exception:
            self._audit(
                TelemetryAuditEventType.ANALYSIS_FAILED,
                request.series,
                timestamp=request.observed_at,
            )
            raise TelemetryDataRejected from None
        self._audit(
            TelemetryAuditEventType.ANALYSIS_COMPLETED,
            request.series,
            timestamp=request.observed_at,
        )
        return result

    def _source(self, source_type: TelemetrySourceType) -> _SourceAdapter:
        for adapter in self._adapters:
            if adapter.source_type is source_type:
                return adapter
        raise TelemetrySourceUnavailable

    def _audit(
        self,
        event_type: TelemetryAuditEventType,
        subject: TelemetryRequest | TelemetrySeriesSnapshot,
        *,
        timestamp: datetime | None = None,
    ) -> None:
        emit_audit(
            self._audit_sink,
            event_type=event_type,
            target_id=subject.target_id,
            source_type=subject.source_type,
            timestamp=subject.observed_at if timestamp is None else timestamp,
        )


def _validated_request(
    model_type: type[_RequestT],
    value: BaseModel,
) -> _RequestT:
    try:
        return model_type.model_validate(copy.deepcopy(value.model_dump(mode="python")))
    except Exception:
        raise TelemetryDataRejected from None


def _validate_sample_binding(
    sample: TelemetrySample,
    request: TelemetryRequest,
) -> None:
    if (
        sample.target_id != request.target_id
        or sample.source_type is not request.source_type
    ):
        raise TelemetryDataRejected


def _raise_source_error(error: Exception) -> NoReturn:
    if isinstance(error, TelemetryDataRejected):
        raise TelemetryDataRejected from None
    if isinstance(error, TimeoutError):
        raise TelemetryObservationTimeout from None
    if isinstance(error, TelemetrySourceUnavailable):
        raise TelemetrySourceUnavailable from None
    raise TelemetrySourceUnavailable from None
