from __future__ import annotations

import importlib.util
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

import embedded_copilot.debug_runtime as debug_runtime
import embedded_copilot.telemetry_runtime as telemetry_runtime

UTC_TIME = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.events: list[telemetry_runtime.TelemetryAuditEvent] = []

    def record(self, event: telemetry_runtime.TelemetryAuditEvent) -> None:
        self.events.append(event)


class EmptySource:
    def __init__(self, source_type: telemetry_runtime.TelemetrySourceType) -> None:
        self._source_type = source_type

    @property
    def source_type(self) -> telemetry_runtime.TelemetrySourceType:
        return self._source_type

    def read_sample(self, target_id: str) -> telemetry_runtime.TelemetrySample:
        raise AssertionError("not used")


class SequenceSource:
    def __init__(
        self,
        source_type: telemetry_runtime.TelemetrySourceType,
        samples: tuple[telemetry_runtime.TelemetrySample, ...],
    ) -> None:
        self._source_type = source_type
        self.samples = list(samples)
        self.calls: list[str] = []

    @property
    def source_type(self) -> telemetry_runtime.TelemetrySourceType:
        return self._source_type

    def read_sample(self, target_id: str) -> telemetry_runtime.TelemetrySample:
        self.calls.append(target_id)
        return self.samples.pop(0)


class FailingSource:
    def __init__(
        self,
        exception: Exception,
        source_type: telemetry_runtime.TelemetrySourceType = (
            telemetry_runtime.TelemetrySourceType.MOCK
        ),
    ) -> None:
        self._exception = exception
        self._source_type = source_type

    @property
    def source_type(self) -> telemetry_runtime.TelemetrySourceType:
        return self._source_type

    def read_sample(self, target_id: str) -> telemetry_runtime.TelemetrySample:
        raise self._exception


class FailingAuditSink:
    def record(self, event: telemetry_runtime.TelemetryAuditEvent) -> None:
        raise RuntimeError(r"C:\private\audit.log")


class FailingSourceType:
    @property
    def source_type(self) -> telemetry_runtime.TelemetrySourceType:
        raise RuntimeError(r"C:\private\source.config")

    def read_sample(self, target_id: str) -> telemetry_runtime.TelemetrySample:
        raise AssertionError("must not be called")


class CoercibleSourceType:
    @property
    def source_type(self) -> str:
        return "MOCK"

    def read_sample(self, target_id: str) -> telemetry_runtime.TelemetrySample:
        raise AssertionError("must not be called")


class ExplodingRequest:
    def model_dump(self, *, mode: str) -> dict[str, object]:
        raise RuntimeError(r"C:\private\request.json")


class DebugAuditSink:
    def record(self, event: debug_runtime.DebugAuditEvent) -> None:
        pass


class DebugSource:
    @property
    def source_type(self) -> debug_runtime.DebugSourceType:
        return debug_runtime.DebugSourceType.JLINK

    def read_identity(self, target_id: str) -> debug_runtime.TargetIdentity:
        return _debug_identity()

    def read_snapshot(self, target_id: str) -> debug_runtime.DebugSourceCapture:
        return debug_runtime.DebugSourceCapture(
            source_type=debug_runtime.DebugSourceType.JLINK,
            target_identity=_debug_identity(),
            observations=(),
            telemetry=(
                debug_runtime.TelemetryMetric(
                    name="temperature",
                    value=42.5,
                    unit=debug_runtime.TelemetryUnit.CELSIUS,
                ),
                debug_runtime.TelemetryMetric(
                    name="cpu_usage",
                    value=12,
                    unit=debug_runtime.TelemetryUnit.PERCENT,
                ),
            ),
        )

    def read_telemetry(
        self,
        target_id: str,
    ) -> tuple[debug_runtime.TelemetryMetric, ...]:
        return self.read_snapshot(target_id).telemetry


def _debug_identity() -> debug_runtime.TargetIdentity:
    return debug_runtime.TargetIdentity(
        vendor="STMicroelectronics",
        family="STM32",
        architecture="ARM",
        device="STM32F407",
        core="Cortex-M4",
    )


def _metric(
    name: str,
    value: int | float,
    unit: telemetry_runtime.TelemetryUnit,
) -> telemetry_runtime.TelemetryMetric:
    return telemetry_runtime.TelemetryMetric(name=name, value=value, unit=unit)


def _sample(
    *,
    sample_id: str,
    captured_at: datetime,
    metrics: tuple[telemetry_runtime.TelemetryMetric, ...],
    target_id: str = "target:stm32",
    source_type: telemetry_runtime.TelemetrySourceType = (
        telemetry_runtime.TelemetrySourceType.MOCK
    ),
) -> telemetry_runtime.TelemetrySample:
    from embedded_copilot.telemetry_runtime.series import build_sample

    return build_sample(
        sample_id=sample_id,
        target_id=target_id,
        source_type=source_type,
        captured_at=captured_at,
        metrics=metrics,
    )


def _series(
    values: tuple[int | float, ...],
) -> telemetry_runtime.TelemetrySeriesSnapshot:
    from embedded_copilot.telemetry_runtime.series import build_series

    samples = tuple(
        _sample(
            sample_id=f"sample:{index}",
            captured_at=UTC_TIME + timedelta(seconds=index),
            metrics=(_metric("speed", value, telemetry_runtime.TelemetryUnit.RPM),),
        )
        for index, value in enumerate(values)
    )
    return build_series(
        series_id="series:speed",
        target_id="target:stm32",
        source_type=telemetry_runtime.TelemetrySourceType.MOCK,
        metric_name="speed",
        samples=samples,
    )


def test_telemetry_runtime_package_exists() -> None:
    assert importlib.util.find_spec("embedded_copilot.telemetry_runtime") is not None


def test_public_contract_is_narrow_and_synchronous() -> None:
    assert set(telemetry_runtime.__all__) == {
        "DebugTelemetryContext",
        "TelemetryAnalysisRequest",
        "TelemetryAnalysisResult",
        "TelemetryAnomalyCandidate",
        "TelemetryAnomalyDirection",
        "TelemetryAuditEvent",
        "TelemetryAuditEventType",
        "TelemetryAuditSink",
        "TelemetryAuditUnavailable",
        "TelemetryDataRejected",
        "TelemetryMetric",
        "TelemetryObservationTimeout",
        "TelemetryPort",
        "TelemetryRequest",
        "TelemetryRuntime",
        "TelemetrySample",
        "TelemetrySeriesPoint",
        "TelemetrySeriesRequest",
        "TelemetrySeriesSnapshot",
        "TelemetrySourcePort",
        "TelemetrySourceType",
        "TelemetrySourceUnavailable",
        "TelemetryStatistics",
        "TelemetryTrend",
        "TelemetryUnit",
        "create_telemetry_runtime",
    }
    assert tuple(telemetry_runtime.TelemetrySourceType) == (
        telemetry_runtime.TelemetrySourceType.DEBUG_RUNTIME,
        telemetry_runtime.TelemetrySourceType.MOCK,
    )
    assert {
        name
        for name, value in telemetry_runtime.TelemetryRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"telemetry_port"}
    assert {
        name
        for name, value in telemetry_runtime.TelemetryPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"collect_sample", "collect_series", "analyze_signal"}
    for method_name in ("collect_sample", "collect_series", "analyze_signal"):
        assert not inspect.iscoroutinefunction(
            getattr(telemetry_runtime.TelemetryPort, method_name)
        )


def test_contracts_are_frozen_strict_and_normalize_utc() -> None:
    observed_at = datetime(
        2026,
        7,
        30,
        11,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )
    request = telemetry_runtime.TelemetryRequest(
        target_id="target:stm32",
        source_type=telemetry_runtime.TelemetrySourceType.MOCK,
        observed_at=observed_at,
    )

    assert request.observed_at == UTC_TIME
    with pytest.raises(ValidationError):
        request.target_id = "target:other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        telemetry_runtime.TelemetryRequest.model_validate(
            {
                **request.model_dump(mode="python"),
                "control": "reset",
            }
        )
    with pytest.raises(ValidationError):
        telemetry_runtime.TelemetryRequest(
            target_id="target:stm32",
            source_type=telemetry_runtime.TelemetrySourceType.MOCK,
            observed_at=datetime(2026, 7, 30),
        )
    with pytest.raises(ValidationError):
        telemetry_runtime.TelemetryRequest.model_validate(
            {
                "target_id": "target:stm32",
                "source_type": "MOCK",
                "observed_at": UTC_TIME,
            }
        )
    with pytest.raises(ValidationError):
        telemetry_runtime.TelemetrySeriesRequest.model_validate(
            {
                "series_id": "series:speed",
                "target_id": "target:stm32",
                "source_type": telemetry_runtime.TelemetrySourceType.MOCK,
                "metric_name": "speed",
                "sample_count": "2",
                "observed_at": UTC_TIME,
            }
        )
    with pytest.raises(ValidationError):
        telemetry_runtime.TelemetryMetric.model_validate(
            {
                "name": "speed",
                "value": 1,
                "unit": "rpm",
            }
        )

    models = (
        value
        for value in vars(telemetry_runtime).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__.startswith("embedded_copilot.telemetry_runtime")
    )
    for model in models:
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["frozen"] is True
        assert model.model_config["revalidate_instances"] == "always"
        assert model.model_config["strict"] is True


def test_factory_requires_non_empty_unique_source_tuple_and_audit_sink() -> None:
    sink = RecordingAuditSink()
    mock = EmptySource(telemetry_runtime.TelemetrySourceType.MOCK)

    with pytest.raises(TypeError, match="sources"):
        telemetry_runtime.create_telemetry_runtime(  # type: ignore[arg-type]
            sources=[mock],
            audit_sink=sink,
        )
    with pytest.raises(ValueError, match="sources"):
        telemetry_runtime.create_telemetry_runtime(sources=(), audit_sink=sink)
    with pytest.raises(ValueError, match="unique"):
        telemetry_runtime.create_telemetry_runtime(
            sources=(
                mock,
                EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),
            ),
            audit_sink=sink,
        )
    with pytest.raises(TypeError, match="audit"):
        telemetry_runtime.create_telemetry_runtime(
            sources=(mock,),
            audit_sink=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="source type") as captured:
        telemetry_runtime.create_telemetry_runtime(
            sources=(FailingSourceType(),),
            audit_sink=sink,
        )
    assert "private" not in str(captured.value).casefold()
    with pytest.raises(TypeError, match="source type"):
        telemetry_runtime.create_telemetry_runtime(
            sources=(CoercibleSourceType(),),
            audit_sink=sink,
        )

    runtime = telemetry_runtime.create_telemetry_runtime(
        sources=(mock,),
        audit_sink=sink,
    )

    assert set(runtime.__slots__) == {"_telemetry_port"}
    for name in (
        "sources",
        "adapters",
        "audit_sink",
        "analyzer",
        "storage",
        "cache",
        "database",
    ):
        assert not hasattr(runtime, name)
        assert not hasattr(runtime.telemetry_port(), name)


def test_sample_fingerprint_is_stable_and_metrics_are_sorted() -> None:
    first = _sample(
        sample_id="sample:1",
        captured_at=UTC_TIME,
        metrics=(
            _metric("temperature", 42.5, telemetry_runtime.TelemetryUnit.CELSIUS),
            _metric("cpu_usage", 12, telemetry_runtime.TelemetryUnit.PERCENT),
        ),
    )
    second = _sample(
        sample_id="sample:1",
        captured_at=UTC_TIME,
        metrics=tuple(reversed(first.metrics)),
    )

    assert tuple(metric.name for metric in first.metrics) == (
        "cpu_usage",
        "temperature",
    )
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint.startswith("sha256:")

    payload = first.model_dump(mode="python")
    payload["metrics"] = (
        _metric("cpu_usage", 99, telemetry_runtime.TelemetryUnit.PERCENT),
        payload["metrics"][1],
    )
    with pytest.raises(ValidationError, match="fingerprint"):
        telemetry_runtime.TelemetrySample.model_validate(payload)


def test_sample_timestamp_is_normalized_before_fingerprinting() -> None:
    local_time = datetime(
        2026,
        7,
        30,
        11,
        0,
        tzinfo=timezone(timedelta(hours=8)),
    )

    sample = _sample(
        sample_id="sample:timezone",
        captured_at=local_time,
        metrics=(_metric("speed", 50, telemetry_runtime.TelemetryUnit.RPM),),
    )

    assert sample.captured_at == UTC_TIME
    assert sample == _sample(
        sample_id="sample:timezone",
        captured_at=UTC_TIME,
        metrics=sample.metrics,
    )


def test_metric_boundary_rejects_invalid_and_duplicate_values() -> None:
    for value in (
        True,
        float("nan"),
        float("inf"),
        float("-inf"),
        10**400,
    ):
        with pytest.raises(ValidationError):
            _metric("cpu_usage", value, telemetry_runtime.TelemetryUnit.PERCENT)

    with pytest.raises(telemetry_runtime.TelemetryDataRejected):
        _sample(
            sample_id="sample:duplicate",
            captured_at=UTC_TIME,
            metrics=(
                _metric("cpu_usage", 1, telemetry_runtime.TelemetryUnit.PERCENT),
                _metric("cpu_usage", 2, telemetry_runtime.TelemetryUnit.PERCENT),
            ),
        )


def test_debug_snapshot_bridge_projects_only_telemetry() -> None:
    snapshot = (
        debug_runtime.create_debug_runtime(
            sources=(DebugSource(),),
            audit_sink=DebugAuditSink(),
        )
        .debug_port()
        .collect_snapshot(
            debug_runtime.DebugSnapshotRequest(
                snapshot_id="snapshot:debug",
                target_id="target:stm32",
                source_type=debug_runtime.DebugSourceType.JLINK,
                observed_at=UTC_TIME,
            )
        )
    )

    sample = telemetry_runtime.DebugTelemetryContext(
        sample_id="sample:debug",
        debug_snapshot=snapshot,
    ).to_sample()
    serialized = sample.model_dump_json()

    assert sample.source_type is telemetry_runtime.TelemetrySourceType.DEBUG_RUNTIME
    assert sample.target_id == "target:stm32"
    assert sample.captured_at == UTC_TIME
    assert tuple(metric.name for metric in sample.metrics) == (
        "cpu_usage",
        "temperature",
    )
    for prohibited in (
        "target_identity",
        "STM32F407",
        "observations",
        "register",
        "stack",
        "snapshot:debug",
    ):
        assert prohibited not in serialized


def test_collect_sample_routes_exact_source_and_revalidates_binding() -> None:
    sink = RecordingAuditSink()
    sample = _sample(
        sample_id="sample:mock",
        captured_at=UTC_TIME,
        metrics=(_metric("speed", 50, telemetry_runtime.TelemetryUnit.RPM),),
    )
    source = SequenceSource(telemetry_runtime.TelemetrySourceType.MOCK, (sample,))
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(source,),
        audit_sink=sink,
    ).telemetry_port()

    result = port.collect_sample(
        telemetry_runtime.TelemetryRequest(
            target_id="target:stm32",
            source_type=telemetry_runtime.TelemetrySourceType.MOCK,
            observed_at=UTC_TIME,
        )
    )

    assert result == sample
    assert result is not sample
    assert source.calls == ["target:stm32"]

    with pytest.raises(telemetry_runtime.TelemetrySourceUnavailable):
        port.collect_sample(
            telemetry_runtime.TelemetryRequest(
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.DEBUG_RUNTIME,
                observed_at=UTC_TIME,
            )
        )


@pytest.mark.parametrize(
    "sample",
    [
        _sample(
            sample_id="sample:wrong-target",
            captured_at=UTC_TIME,
            metrics=(_metric("speed", 1, telemetry_runtime.TelemetryUnit.RPM),),
            target_id="target:other",
        ),
        _sample(
            sample_id="sample:wrong-source",
            captured_at=UTC_TIME,
            metrics=(_metric("speed", 1, telemetry_runtime.TelemetryUnit.RPM),),
            source_type=telemetry_runtime.TelemetrySourceType.DEBUG_RUNTIME,
        ),
    ],
)
def test_collect_sample_rejects_target_or_source_mismatch(
    sample: telemetry_runtime.TelemetrySample,
) -> None:
    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(
            SequenceSource(
                telemetry_runtime.TelemetrySourceType.MOCK,
                (sample,),
            ),
        ),
        audit_sink=sink,
    ).telemetry_port()

    with pytest.raises(telemetry_runtime.TelemetryDataRejected):
        port.collect_sample(
            telemetry_runtime.TelemetryRequest(
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.MOCK,
                observed_at=UTC_TIME,
            )
        )

    assert sink.events[0].event_type is (
        telemetry_runtime.TelemetryAuditEventType.SAMPLE_COLLECTION_FAILED
    )


def test_collect_series_pulls_bounded_samples_and_sorts_points() -> None:
    samples = (
        _sample(
            sample_id="sample:2",
            captured_at=UTC_TIME + timedelta(seconds=2),
            metrics=(_metric("speed", 20, telemetry_runtime.TelemetryUnit.RPM),),
        ),
        _sample(
            sample_id="sample:0",
            captured_at=UTC_TIME,
            metrics=(_metric("speed", 10, telemetry_runtime.TelemetryUnit.RPM),),
        ),
        _sample(
            sample_id="sample:1",
            captured_at=UTC_TIME + timedelta(seconds=1),
            metrics=(_metric("speed", 15, telemetry_runtime.TelemetryUnit.RPM),),
        ),
    )
    source = SequenceSource(telemetry_runtime.TelemetrySourceType.MOCK, samples)
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(source,),
        audit_sink=RecordingAuditSink(),
    ).telemetry_port()

    series = port.collect_series(
        telemetry_runtime.TelemetrySeriesRequest(
            series_id="series:speed",
            target_id="target:stm32",
            source_type=telemetry_runtime.TelemetrySourceType.MOCK,
            metric_name="speed",
            sample_count=3,
            observed_at=UTC_TIME,
        )
    )

    assert source.calls == ["target:stm32"] * 3
    assert tuple(point.sample_id for point in series.samples) == (
        "sample:0",
        "sample:1",
        "sample:2",
    )
    assert tuple(point.value for point in series.samples) == (10, 15, 20)
    assert series.unit is telemetry_runtime.TelemetryUnit.RPM
    assert series.source_type is telemetry_runtime.TelemetrySourceType.MOCK
    assert series.fingerprint.startswith("sha256:")

    payload = series.model_dump(mode="python")
    payload["metric_name"] = "temperature"
    with pytest.raises(ValidationError, match="fingerprint"):
        telemetry_runtime.TelemetrySeriesSnapshot.model_validate(payload)


@pytest.mark.parametrize("failure", ["missing_metric", "unit_mismatch", "duplicate_id"])
def test_collect_series_rejects_inconsistent_samples(failure: str) -> None:
    first = _sample(
        sample_id="sample:1",
        captured_at=UTC_TIME,
        metrics=(_metric("speed", 10, telemetry_runtime.TelemetryUnit.RPM),),
    )
    if failure == "missing_metric":
        second = _sample(
            sample_id="sample:2",
            captured_at=UTC_TIME + timedelta(seconds=1),
            metrics=(
                _metric(
                    "temperature",
                    40,
                    telemetry_runtime.TelemetryUnit.CELSIUS,
                ),
            ),
        )
    elif failure == "unit_mismatch":
        second = _sample(
            sample_id="sample:2",
            captured_at=UTC_TIME + timedelta(seconds=1),
            metrics=(_metric("speed", 11, telemetry_runtime.TelemetryUnit.HERTZ),),
        )
    else:
        second = _sample(
            sample_id="sample:1",
            captured_at=UTC_TIME + timedelta(seconds=1),
            metrics=(_metric("speed", 11, telemetry_runtime.TelemetryUnit.RPM),),
        )
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(
            SequenceSource(
                telemetry_runtime.TelemetrySourceType.MOCK,
                (first, second),
            ),
        ),
        audit_sink=RecordingAuditSink(),
    ).telemetry_port()

    with pytest.raises(telemetry_runtime.TelemetryDataRejected):
        port.collect_series(
            telemetry_runtime.TelemetrySeriesRequest(
                series_id=f"series:{failure}",
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.MOCK,
                metric_name="speed",
                sample_count=2,
                observed_at=UTC_TIME,
            )
        )


@pytest.mark.parametrize(
    ("values", "trend", "delta"),
    [
        ((10, 15, 20), telemetry_runtime.TelemetryTrend.INCREASING, 10),
        ((20, 15, 10), telemetry_runtime.TelemetryTrend.DECREASING, -10),
        ((10, 99, 10), telemetry_runtime.TelemetryTrend.STABLE, 0.0),
    ],
)
def test_analyze_signal_is_deterministic_endpoint_analysis(
    values: tuple[int | float, ...],
    trend: telemetry_runtime.TelemetryTrend,
    delta: int | float,
) -> None:
    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=sink,
    ).telemetry_port()

    result = port.analyze_signal(
        telemetry_runtime.TelemetryAnalysisRequest(
            series=_series(values),
            observed_at=UTC_TIME,
        )
    )

    assert set(type(result).model_fields) == {
        "statistics",
        "trend",
        "anomaly_candidate",
    }
    assert result.statistics.minimum == min(values)
    assert result.statistics.maximum == max(values)
    assert result.statistics.average == pytest.approx(sum(values) / len(values))
    assert result.statistics.delta == delta
    assert result.statistics.sample_count == len(values)
    assert result.trend is trend
    assert result.anomaly_candidate is None
    assert sink.events == [
        telemetry_runtime.TelemetryAuditEvent(
            event_type=telemetry_runtime.TelemetryAuditEventType.ANALYSIS_COMPLETED,
            target_id="target:stm32",
            source_type=telemetry_runtime.TelemetrySourceType.MOCK,
            timestamp=UTC_TIME,
        )
    ]


def test_anomaly_candidate_is_unverified_and_uses_fixed_direction_order() -> None:
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=RecordingAuditSink(),
    ).telemetry_port()

    result = port.analyze_signal(
        telemetry_runtime.TelemetryAnalysisRequest(
            series=_series((-1, 5, 11)),
            lower_bound=0,
            upper_bound=10,
            observed_at=UTC_TIME,
        )
    )

    candidate = result.anomaly_candidate
    assert candidate is not None
    assert candidate.candidate_semantics == "unverified"
    assert candidate.directions == (
        telemetry_runtime.TelemetryAnomalyDirection.BELOW_LOWER_BOUND,
        telemetry_runtime.TelemetryAnomalyDirection.ABOVE_UPPER_BOUND,
    )
    assert candidate.lower_bound == 0
    assert candidate.upper_bound == 10
    assert candidate.observed_minimum == -1
    assert candidate.observed_maximum == 11
    assert candidate.review_required is True
    for prohibited in ("root_cause", "confirmed_fault", "control_action", "fix"):
        assert prohibited not in type(candidate).model_fields


def test_average_uses_fsum_in_sample_order() -> None:
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=RecordingAuditSink(),
    ).telemetry_port()

    result = port.analyze_signal(
        telemetry_runtime.TelemetryAnalysisRequest(
            series=_series((1e16, 1, -1e16)),
            observed_at=UTC_TIME,
        )
    )

    assert result.statistics.average == pytest.approx(1 / 3)


def test_average_of_large_finite_values_remains_finite() -> None:
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=RecordingAuditSink(),
    ).telemetry_port()

    result = port.analyze_signal(
        telemetry_runtime.TelemetryAnalysisRequest(
            series=_series((1e308, 1e308)),
            observed_at=UTC_TIME,
        )
    )

    assert result.statistics.average == 1e308
    assert result.statistics.delta == 0.0


def test_large_finite_endpoint_delta_uses_exact_integer_when_needed() -> None:
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=RecordingAuditSink(),
    ).telemetry_port()

    result = port.analyze_signal(
        telemetry_runtime.TelemetryAnalysisRequest(
            series=_series((-1e308, 1e308)),
            observed_at=UTC_TIME,
        )
    )

    assert result.statistics.average == 0.0
    assert isinstance(result.statistics.delta, int)
    assert result.statistics.delta > 10**308
    assert result.trend is telemetry_runtime.TelemetryTrend.INCREASING


def test_bounds_reject_bool_non_finite_and_invalid_order() -> None:
    series = _series((1, 2))
    for value in (True, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            telemetry_runtime.TelemetryAnalysisRequest(
                series=series,
                lower_bound=value,
                observed_at=UTC_TIME,
            )
    with pytest.raises(ValidationError):
        telemetry_runtime.TelemetryAnalysisRequest(
            series=series,
            lower_bound=3,
            upper_bound=2,
            observed_at=UTC_TIME,
        )


def test_public_operations_emit_one_content_free_audit_event_each() -> None:
    sink = RecordingAuditSink()
    samples = (
        _sample(
            sample_id="sample:one",
            captured_at=UTC_TIME,
            metrics=(_metric("speed", 1, telemetry_runtime.TelemetryUnit.RPM),),
        ),
        _sample(
            sample_id="sample:two",
            captured_at=UTC_TIME + timedelta(seconds=1),
            metrics=(_metric("speed", 2, telemetry_runtime.TelemetryUnit.RPM),),
        ),
        _sample(
            sample_id="sample:three",
            captured_at=UTC_TIME + timedelta(seconds=2),
            metrics=(_metric("speed", 3, telemetry_runtime.TelemetryUnit.RPM),),
        ),
    )
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(
            SequenceSource(
                telemetry_runtime.TelemetrySourceType.MOCK,
                samples,
            ),
        ),
        audit_sink=sink,
    ).telemetry_port()

    port.collect_sample(
        telemetry_runtime.TelemetryRequest(
            target_id="target:stm32",
            source_type=telemetry_runtime.TelemetrySourceType.MOCK,
            observed_at=UTC_TIME,
        )
    )
    series = port.collect_series(
        telemetry_runtime.TelemetrySeriesRequest(
            series_id="series:audit",
            target_id="target:stm32",
            source_type=telemetry_runtime.TelemetrySourceType.MOCK,
            metric_name="speed",
            sample_count=2,
            observed_at=UTC_TIME,
        )
    )
    port.analyze_signal(
        telemetry_runtime.TelemetryAnalysisRequest(
            series=series,
            observed_at=UTC_TIME,
        )
    )

    assert tuple(event.event_type for event in sink.events) == (
        telemetry_runtime.TelemetryAuditEventType.SAMPLE_COLLECTED,
        telemetry_runtime.TelemetryAuditEventType.SERIES_CREATED,
        telemetry_runtime.TelemetryAuditEventType.ANALYSIS_COMPLETED,
    )
    for event in sink.events:
        assert set(type(event).model_fields) == {
            "event_type",
            "target_id",
            "source_type",
            "timestamp",
        }
        serialized = event.model_dump_json()
        assert "speed" not in serialized
        assert "sample:" not in serialized


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (
            TimeoutError(r"C:\private\probe.exe timed out"),
            telemetry_runtime.TelemetryObservationTimeout,
        ),
        (
            RuntimeError(r"C:\private\probe.exe failed"),
            telemetry_runtime.TelemetrySourceUnavailable,
        ),
    ],
)
def test_source_failures_are_sanitized_and_audited(
    exception: Exception,
    expected: type[Exception],
) -> None:
    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(FailingSource(exception),),
        audit_sink=sink,
    ).telemetry_port()

    with pytest.raises(expected) as captured:
        port.collect_sample(
            telemetry_runtime.TelemetryRequest(
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.MOCK,
                observed_at=UTC_TIME,
            )
        )

    assert "private" not in str(captured.value)
    assert sink.events[0].event_type is (
        telemetry_runtime.TelemetryAuditEventType.SAMPLE_COLLECTION_FAILED
    )


def test_audit_failure_takes_precedence_over_source_failure() -> None:
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(FailingSource(RuntimeError("provider detail")),),
        audit_sink=FailingAuditSink(),
    ).telemetry_port()

    with pytest.raises(telemetry_runtime.TelemetryAuditUnavailable) as captured:
        port.collect_sample(
            telemetry_runtime.TelemetryRequest(
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.MOCK,
                observed_at=UTC_TIME,
            )
        )

    assert "private" not in str(captured.value)
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is not None


def test_audit_failure_prevents_returning_a_successful_observation() -> None:
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(
            SequenceSource(
                telemetry_runtime.TelemetrySourceType.MOCK,
                (
                    _sample(
                        sample_id="sample:audit-failure",
                        captured_at=UTC_TIME,
                        metrics=(
                            _metric(
                                "speed",
                                1,
                                telemetry_runtime.TelemetryUnit.RPM,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        audit_sink=FailingAuditSink(),
    ).telemetry_port()

    with pytest.raises(telemetry_runtime.TelemetryAuditUnavailable):
        port.collect_sample(
            telemetry_runtime.TelemetryRequest(
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.MOCK,
                observed_at=UTC_TIME,
            )
        )


def test_invalid_request_is_rejected_without_audit() -> None:
    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=sink,
    ).telemetry_port()
    untrusted = telemetry_runtime.TelemetryRequest.model_construct(
        target_id=r"C:\private\target",
        source_type=telemetry_runtime.TelemetrySourceType.MOCK,
        observed_at=datetime(2026, 7, 30),
    )

    with pytest.raises(telemetry_runtime.TelemetryDataRejected):
        port.collect_sample(untrusted)

    assert sink.events == []


def test_request_validation_failure_is_sanitized_without_audit() -> None:
    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=sink,
    ).telemetry_port()

    with pytest.raises(telemetry_runtime.TelemetryDataRejected) as captured:
        port.collect_sample(ExplodingRequest())  # type: ignore[arg-type]

    assert "private" not in str(captured.value).casefold()
    assert captured.value.__cause__ is None
    assert sink.events == []


def test_series_failure_uses_series_failure_audit_event() -> None:
    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(FailingSource(TimeoutError("provider detail")),),
        audit_sink=sink,
    ).telemetry_port()

    with pytest.raises(telemetry_runtime.TelemetryObservationTimeout):
        port.collect_series(
            telemetry_runtime.TelemetrySeriesRequest(
                series_id="series:failure",
                target_id="target:stm32",
                source_type=telemetry_runtime.TelemetrySourceType.MOCK,
                metric_name="speed",
                sample_count=2,
                observed_at=UTC_TIME,
            )
        )

    assert tuple(event.event_type for event in sink.events) == (
        telemetry_runtime.TelemetryAuditEventType.SERIES_CREATION_FAILED,
    )


def test_analysis_failure_is_sanitized_and_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import embedded_copilot.telemetry_runtime.runtime as runtime_module

    sink = RecordingAuditSink()
    port = telemetry_runtime.create_telemetry_runtime(
        sources=(EmptySource(telemetry_runtime.TelemetrySourceType.MOCK),),
        audit_sink=sink,
    ).telemetry_port()

    def fail_analysis(**kwargs: object) -> telemetry_runtime.TelemetryAnalysisResult:
        raise RuntimeError(r"C:\private\analysis")

    monkeypatch.setattr(runtime_module, "analyze_series", fail_analysis)
    with pytest.raises(telemetry_runtime.TelemetryDataRejected) as captured:
        port.analyze_signal(
            telemetry_runtime.TelemetryAnalysisRequest(
                series=_series((1, 2)),
                observed_at=UTC_TIME,
            )
        )

    assert "private" not in str(captured.value).casefold()
    assert tuple(event.event_type for event in sink.events) == (
        telemetry_runtime.TelemetryAuditEventType.ANALYSIS_FAILED,
    )
