from __future__ import annotations

import importlib.util
import inspect
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

import embedded_copilot.debug_runtime as debug_runtime
from embedded_copilot.coding_runtime import (
    CodeFileInput,
    ProjectAnalysisRequest,
    create_coding_runtime,
)

UTC_TIME = datetime(2026, 7, 29, 2, 30, tzinfo=timezone.utc)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.events: list[debug_runtime.DebugAuditEvent] = []

    def record(self, event: debug_runtime.DebugAuditEvent) -> None:
        self.events.append(event)


class FakeDebugSource:
    def __init__(
        self,
        *,
        source_type: debug_runtime.DebugSourceType,
        capture: debug_runtime.DebugSourceCapture,
    ) -> None:
        self._source_type = source_type
        self.identity = capture.target_identity
        self.capture = capture
        self.telemetry = capture.telemetry
        self.calls: list[tuple[str, str]] = []

    @property
    def source_type(self) -> debug_runtime.DebugSourceType:
        return self._source_type

    def read_identity(self, target_id: str) -> debug_runtime.TargetIdentity:
        self.calls.append(("identity", target_id))
        return self.identity

    def read_snapshot(self, target_id: str) -> debug_runtime.DebugSourceCapture:
        self.calls.append(("snapshot", target_id))
        return self.capture

    def read_telemetry(
        self,
        target_id: str,
    ) -> tuple[debug_runtime.TelemetryMetric, ...]:
        self.calls.append(("telemetry", target_id))
        return self.telemetry


class FailingDebugSource(FakeDebugSource):
    def __init__(self, *, error: Exception) -> None:
        super().__init__(
            source_type=debug_runtime.DebugSourceType.JLINK,
            capture=debug_runtime.DebugSourceCapture(
                source_type=debug_runtime.DebugSourceType.JLINK,
                target_identity=_identity(),
                observations=(),
                telemetry=(),
            ),
        )
        self.error = error

    def read_identity(self, target_id: str) -> debug_runtime.TargetIdentity:
        self.calls.append(("identity", target_id))
        raise self.error

    def read_snapshot(self, target_id: str) -> debug_runtime.DebugSourceCapture:
        self.calls.append(("snapshot", target_id))
        raise self.error

    def read_telemetry(
        self,
        target_id: str,
    ) -> tuple[debug_runtime.TelemetryMetric, ...]:
        self.calls.append(("telemetry", target_id))
        raise self.error


class FailingAuditSink:
    def record(self, event: debug_runtime.DebugAuditEvent) -> None:
        raise RuntimeError("C:\\private\\audit\\device.log")


class FailingSourceType:
    @property
    def source_type(self) -> debug_runtime.DebugSourceType:
        raise RuntimeError("C:\\private\\probe\\configuration")

    def read_identity(self, target_id: str) -> debug_runtime.TargetIdentity:
        return _identity()

    def read_snapshot(self, target_id: str) -> debug_runtime.DebugSourceCapture:
        raise AssertionError("must not be called")

    def read_telemetry(
        self,
        target_id: str,
    ) -> tuple[debug_runtime.TelemetryMetric, ...]:
        raise AssertionError("must not be called")


def _identity() -> debug_runtime.TargetIdentity:
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
    unit: debug_runtime.TelemetryUnit = debug_runtime.TelemetryUnit.COUNT,
) -> debug_runtime.TelemetryMetric:
    return debug_runtime.TelemetryMetric(name=name, value=value, unit=unit)


def _source(
    source_type: debug_runtime.DebugSourceType,
    observations: tuple[
        debug_runtime.UARTLogRecord
        | debug_runtime.RegisterRecord
        | debug_runtime.StackFrameRecord,
        ...,
    ],
    *,
    telemetry: tuple[debug_runtime.TelemetryMetric, ...] = (),
) -> FakeDebugSource:
    return FakeDebugSource(
        source_type=source_type,
        capture=debug_runtime.DebugSourceCapture(
            source_type=source_type,
            target_identity=_identity(),
            observations=observations,
            telemetry=telemetry,
        ),
    )


def test_debug_runtime_package_exists() -> None:
    assert importlib.util.find_spec("embedded_copilot.debug_runtime") is not None


def test_public_contract_is_narrow_and_synchronous() -> None:
    assert set(debug_runtime.__all__) == {
        "DebugAuditEvent",
        "DebugAuditEventType",
        "DebugAuditSink",
        "DebugAuditUnavailable",
        "DebugInsight",
        "DebugObservationRejected",
        "DebugObservationTimeout",
        "DebugPort",
        "DebugReasoningContext",
        "DebugRuntime",
        "DebugSeverity",
        "DebugSnapshotRequest",
        "DebugSourceCapture",
        "DebugSourcePort",
        "DebugSourceType",
        "DebugSourceUnavailable",
        "FrozenDebugSnapshot",
        "RegisterObservation",
        "RegisterRecord",
        "StackFrameObservation",
        "StackFrameRecord",
        "TargetIdentificationRequest",
        "TargetIdentity",
        "TelemetryMetric",
        "TelemetryRequest",
        "TelemetrySnapshot",
        "TelemetryUnit",
        "UARTLogRecord",
        "UARTObservation",
        "create_debug_runtime",
    }
    assert tuple(debug_runtime.DebugSourceType) == (
        debug_runtime.DebugSourceType.UART,
        debug_runtime.DebugSourceType.JLINK,
        debug_runtime.DebugSourceType.STLINK,
        debug_runtime.DebugSourceType.GDB,
    )
    assert {
        name
        for name, value in debug_runtime.DebugRuntime.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"debug_port"}
    assert {
        name
        for name, value in debug_runtime.DebugPort.__dict__.items()
        if callable(value) and not name.startswith("_")
    } == {"identify_target", "collect_snapshot", "collect_telemetry"}
    for method_name in ("identify_target", "collect_snapshot", "collect_telemetry"):
        assert not inspect.iscoroutinefunction(
            getattr(debug_runtime.DebugPort, method_name)
        )


def test_debug_contracts_are_frozen_extra_forbid_and_normalize_utc() -> None:
    observed_at = datetime(
        2026,
        7,
        29,
        10,
        30,
        tzinfo=timezone(timedelta(hours=8)),
    )
    request = debug_runtime.DebugSnapshotRequest(
        snapshot_id="snapshot:1",
        target_id="target:stm32",
        source_type=debug_runtime.DebugSourceType.JLINK,
        observed_at=observed_at,
    )

    assert request.observed_at == datetime(
        2026,
        7,
        29,
        2,
        30,
        tzinfo=timezone.utc,
    )
    with pytest.raises(ValidationError):
        request.target_id = "target:other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        debug_runtime.DebugSnapshotRequest.model_validate(
            {
                **request.model_dump(mode="python"),
                "command": "reset",
            }
        )
    with pytest.raises(ValidationError):
        debug_runtime.TelemetryRequest(
            target_id="target:stm32",
            source_type="JLINK",
            observed_at=datetime(2026, 7, 29),
        )

    models = (
        value
        for value in vars(debug_runtime).values()
        if isinstance(value, type)
        and issubclass(value, BaseModel)
        and value.__module__.startswith("embedded_copilot.debug_runtime")
    )
    for model in models:
        assert model.model_config["extra"] == "forbid"
        assert model.model_config["frozen"] is True
        assert model.model_config["revalidate_instances"] == "always"


@pytest.mark.parametrize(
    "field,value",
    [
        ("vendor", "C:\\private\\vendor"),
        ("family", "password=private"),
        ("architecture", "ARM\nCortex-M4"),
        ("device", "device-serial-number"),
        ("core", "x" * 65),
    ],
)
def test_target_identity_rejects_sensitive_or_unsafe_values(
    field: str,
    value: str,
) -> None:
    payload = {
        "vendor": "STMicroelectronics",
        "family": "STM32",
        "architecture": "ARM",
        "device": "STM32F407",
        "core": "Cortex-M4",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        debug_runtime.TargetIdentity.model_validate(payload)


def test_factory_requires_non_empty_unique_source_tuple_and_audit_sink() -> None:
    sink = RecordingAuditSink()
    uart = _source(debug_runtime.DebugSourceType.UART, ())

    with pytest.raises(TypeError, match="sources"):
        debug_runtime.create_debug_runtime(  # type: ignore[arg-type]
            sources=[uart],
            audit_sink=sink,
        )
    with pytest.raises(ValueError, match="sources"):
        debug_runtime.create_debug_runtime(sources=(), audit_sink=sink)
    with pytest.raises(ValueError, match="unique"):
        debug_runtime.create_debug_runtime(
            sources=(uart, _source(debug_runtime.DebugSourceType.UART, ())),
            audit_sink=sink,
        )
    with pytest.raises(TypeError, match="audit"):
        debug_runtime.create_debug_runtime(sources=(uart,), audit_sink=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="source type") as raised:
        debug_runtime.create_debug_runtime(
            sources=(FailingSourceType(),),
            audit_sink=sink,
        )
    assert "private" not in str(raised.value).casefold()

    runtime = debug_runtime.create_debug_runtime(sources=(uart,), audit_sink=sink)

    assert set(runtime.__slots__) == {"_debug_port"}
    for name in (
        "sources",
        "adapters",
        "audit_sink",
        "router",
        "connection",
        "handle",
    ):
        assert not hasattr(runtime, name)
        assert not hasattr(runtime.debug_port(), name)


def test_identify_routes_exact_source_and_missing_source_does_not_fallback() -> None:
    sink = RecordingAuditSink()
    uart = _source(debug_runtime.DebugSourceType.UART, ())
    port = debug_runtime.create_debug_runtime(
        sources=(uart,),
        audit_sink=sink,
    ).debug_port()

    identity = port.identify_target(
        debug_runtime.TargetIdentificationRequest(
            target_id="target:stm32",
            source_type=debug_runtime.DebugSourceType.UART,
            observed_at=UTC_TIME,
        )
    )

    assert identity == _identity()
    assert uart.calls == [("identity", "target:stm32")]
    assert sink.events == [
        debug_runtime.DebugAuditEvent(
            event_type=debug_runtime.DebugAuditEventType.TARGET_IDENTIFIED,
            target_id="target:stm32",
            source_type=debug_runtime.DebugSourceType.UART,
            timestamp=UTC_TIME,
        )
    ]

    with pytest.raises(debug_runtime.DebugSourceUnavailable):
        port.identify_target(
            debug_runtime.TargetIdentificationRequest(
                target_id="target:stm32",
                source_type=debug_runtime.DebugSourceType.JLINK,
                observed_at=UTC_TIME,
            )
        )

    assert uart.calls == [("identity", "target:stm32")]
    assert sink.events[-1].event_type is (
        debug_runtime.DebugAuditEventType.TARGET_IDENTIFICATION_FAILED
    )
    assert sink.events[-1].source_type is debug_runtime.DebugSourceType.JLINK


def test_uart_snapshot_is_normalized_classified_and_fingerprinted() -> None:
    sink = RecordingAuditSink()
    uart = _source(
        debug_runtime.DebugSourceType.UART,
        (
            debug_runtime.UARTLogRecord(
                sequence=2,
                timestamp=UTC_TIME,
                log_line="Guru Meditation panic",
            ),
            debug_runtime.UARTLogRecord(
                sequence=0,
                timestamp=UTC_TIME,
                log_line="Boot complete",
            ),
            debug_runtime.UARTLogRecord(
                sequence=1,
                timestamp=UTC_TIME,
                log_line="UART timeout warning",
            ),
        ),
        telemetry=(
            _metric("log_count", 3),
            _metric("error_count", 1),
        ),
    )
    port = debug_runtime.create_debug_runtime(
        sources=(uart,),
        audit_sink=sink,
    ).debug_port()
    request = debug_runtime.DebugSnapshotRequest(
        snapshot_id="snapshot:uart",
        target_id="target:stm32",
        source_type=debug_runtime.DebugSourceType.UART,
        observed_at=UTC_TIME,
    )

    first = port.collect_snapshot(request)
    second = port.collect_snapshot(request)

    assert tuple(item.sequence for item in first.observations) == (0, 1, 2)
    assert tuple(item.severity for item in first.observations) == (
        debug_runtime.DebugSeverity.INFO,
        debug_runtime.DebugSeverity.WARNING,
        debug_runtime.DebugSeverity.CRITICAL,
    )
    assert tuple(item.name for item in first.telemetry.metrics) == (
        "error_count",
        "log_count",
    )
    assert first.fingerprint == second.fingerprint
    assert first.fingerprint.startswith("sha256:")
    assert uart.calls == [
        ("snapshot", "target:stm32"),
        ("snapshot", "target:stm32"),
    ]
    payload = first.model_dump(mode="python")
    payload["fingerprint"] = "sha256:" + ("0" * 64)
    with pytest.raises(ValidationError, match="fingerprint"):
        debug_runtime.FrozenDebugSnapshot.model_validate(payload)


@pytest.mark.parametrize(
    "source_type",
    [debug_runtime.DebugSourceType.JLINK, debug_runtime.DebugSourceType.STLINK],
)
def test_probe_snapshot_contains_only_sorted_register_summary(
    source_type: debug_runtime.DebugSourceType,
) -> None:
    source = _source(
        source_type,
        (
            debug_runtime.RegisterRecord(register="xpsr", value="0X21000000"),
            debug_runtime.RegisterRecord(register="pc", value="0x08000101"),
        ),
    )
    port = debug_runtime.create_debug_runtime(
        sources=(source,),
        audit_sink=RecordingAuditSink(),
    ).debug_port()

    snapshot = port.collect_snapshot(
        debug_runtime.DebugSnapshotRequest(
            snapshot_id=f"snapshot:{source_type.value.lower()}",
            target_id="target:stm32",
            source_type=source_type,
            observed_at=UTC_TIME,
        )
    )

    assert tuple(item.kind for item in snapshot.observations) == (
        "REGISTER",
        "REGISTER",
    )
    assert tuple(item.register for item in snapshot.observations) == ("PC", "XPSR")
    assert tuple(item.value for item in snapshot.observations) == (
        "0x08000101",
        "0x21000000",
    )


def test_gdb_snapshot_contains_register_and_bounded_stack_summary() -> None:
    source = _source(
        debug_runtime.DebugSourceType.GDB,
        (
            debug_runtime.StackFrameRecord(
                frame_index=1,
                function="scheduler_loop",
                address="0x08000200",
            ),
            debug_runtime.RegisterRecord(register="pc", value="0x08000100"),
            debug_runtime.StackFrameRecord(
                frame_index=0,
                function="HardFault_Handler",
                address="0x08000100",
            ),
        ),
    )
    port = debug_runtime.create_debug_runtime(
        sources=(source,),
        audit_sink=RecordingAuditSink(),
    ).debug_port()

    snapshot = port.collect_snapshot(
        debug_runtime.DebugSnapshotRequest(
            snapshot_id="snapshot:gdb",
            target_id="target:stm32",
            source_type=debug_runtime.DebugSourceType.GDB,
            observed_at=UTC_TIME,
        )
    )

    assert tuple(item.kind for item in snapshot.observations) == (
        "REGISTER",
        "STACK_FRAME",
        "STACK_FRAME",
    )
    assert snapshot.observations[1].frame_index == 0
    assert snapshot.observations[2].frame_index == 1


def test_source_capture_rejects_observation_kind_mismatch() -> None:
    uart = _source(
        debug_runtime.DebugSourceType.UART,
        (debug_runtime.RegisterRecord(register="pc", value="0x08000100"),),
    )
    port = debug_runtime.create_debug_runtime(
        sources=(uart,),
        audit_sink=RecordingAuditSink(),
    ).debug_port()

    with pytest.raises(debug_runtime.DebugObservationRejected):
        port.collect_snapshot(
            debug_runtime.DebugSnapshotRequest(
                snapshot_id="snapshot:mismatch",
                target_id="target:stm32",
                source_type=debug_runtime.DebugSourceType.UART,
                observed_at=UTC_TIME,
            )
        )


@pytest.mark.parametrize(
    ("source_type", "observations"),
    [
        (
            debug_runtime.DebugSourceType.UART,
            tuple(
                debug_runtime.UARTLogRecord(
                    sequence=index,
                    timestamp=UTC_TIME,
                    log_line=f"log {index}",
                )
                for index in range(257)
            ),
        ),
        (
            debug_runtime.DebugSourceType.JLINK,
            tuple(
                debug_runtime.RegisterRecord(
                    register=f"r{index}",
                    value=f"0x{index:x}",
                )
                for index in range(65)
            ),
        ),
    ],
)
def test_source_specific_snapshot_capacity_is_enforced(
    source_type: debug_runtime.DebugSourceType,
    observations: tuple[
        debug_runtime.UARTLogRecord | debug_runtime.RegisterRecord, ...
    ],
) -> None:
    port = debug_runtime.create_debug_runtime(
        sources=(_source(source_type, observations),),
        audit_sink=RecordingAuditSink(),
    ).debug_port()

    with pytest.raises(debug_runtime.DebugObservationRejected):
        port.collect_snapshot(
            debug_runtime.DebugSnapshotRequest(
                snapshot_id="snapshot:over-capacity",
                target_id="target:stm32",
                source_type=source_type,
                observed_at=UTC_TIME,
            )
        )


def test_collect_telemetry_sorts_metrics_and_emits_content_free_audit() -> None:
    sink = RecordingAuditSink()
    source = _source(
        debug_runtime.DebugSourceType.JLINK,
        (),
        telemetry=(
            _metric("temperature", 42.5, debug_runtime.TelemetryUnit.CELSIUS),
            _metric("cpu_usage", 12.0, debug_runtime.TelemetryUnit.PERCENT),
        ),
    )
    port = debug_runtime.create_debug_runtime(
        sources=(source,),
        audit_sink=sink,
    ).debug_port()

    telemetry = port.collect_telemetry(
        debug_runtime.TelemetryRequest(
            target_id="target:stm32",
            source_type=debug_runtime.DebugSourceType.JLINK,
            observed_at=UTC_TIME,
        )
    )

    assert tuple(item.name for item in telemetry.metrics) == (
        "cpu_usage",
        "temperature",
    )
    assert source.calls == [("telemetry", "target:stm32")]
    assert sink.events[-1].event_type is (
        debug_runtime.DebugAuditEventType.TELEMETRY_COLLECTED
    )
    serialized = sink.events[-1].model_dump(mode="json")
    assert set(serialized) == {"event_type", "target_id", "source_type", "timestamp"}
    assert "42.5" not in str(serialized)


def test_duplicate_telemetry_is_rejected_and_failure_is_audited() -> None:
    sink = RecordingAuditSink()
    source = _source(
        debug_runtime.DebugSourceType.JLINK,
        (),
        telemetry=(
            _metric("cpu_usage", 10, debug_runtime.TelemetryUnit.PERCENT),
            _metric("cpu_usage", 11, debug_runtime.TelemetryUnit.PERCENT),
        ),
    )
    port = debug_runtime.create_debug_runtime(
        sources=(source,),
        audit_sink=sink,
    ).debug_port()

    with pytest.raises(debug_runtime.DebugObservationRejected):
        port.collect_telemetry(
            debug_runtime.TelemetryRequest(
                target_id="target:stm32",
                source_type=debug_runtime.DebugSourceType.JLINK,
                observed_at=UTC_TIME,
            )
        )

    assert sink.events[-1].event_type is (
        debug_runtime.DebugAuditEventType.TELEMETRY_COLLECTION_FAILED
    )


def test_invalid_request_is_rejected_without_audit() -> None:
    sink = RecordingAuditSink()
    port = debug_runtime.create_debug_runtime(
        sources=(_source(debug_runtime.DebugSourceType.UART, ()),),
        audit_sink=sink,
    ).debug_port()
    untrusted = debug_runtime.TargetIdentificationRequest.model_construct(
        target_id="C:\\private\\target",
        source_type=debug_runtime.DebugSourceType.UART,
        observed_at=datetime(2026, 7, 29),
    )

    with pytest.raises(debug_runtime.DebugObservationRejected):
        port.identify_target(untrusted)

    assert sink.events == []


@pytest.mark.parametrize(
    "error,expected",
    [
        (TimeoutError("C:\\private\\probe"), debug_runtime.DebugObservationTimeout),
        (RuntimeError("C:\\private\\probe"), debug_runtime.DebugSourceUnavailable),
    ],
)
def test_source_failures_are_audited_and_sanitized(
    error: Exception,
    expected: type[Exception],
) -> None:
    sink = RecordingAuditSink()
    port = debug_runtime.create_debug_runtime(
        sources=(FailingDebugSource(error=error),),
        audit_sink=sink,
    ).debug_port()

    with pytest.raises(expected) as raised:
        port.collect_snapshot(
            debug_runtime.DebugSnapshotRequest(
                snapshot_id="snapshot:failure",
                target_id="target:stm32",
                source_type=debug_runtime.DebugSourceType.JLINK,
                observed_at=UTC_TIME,
            )
        )

    assert "private" not in str(raised.value).casefold()
    assert sink.events == [
        debug_runtime.DebugAuditEvent(
            event_type=debug_runtime.DebugAuditEventType.SNAPSHOT_COLLECTION_FAILED,
            target_id="target:stm32",
            source_type=debug_runtime.DebugSourceType.JLINK,
            timestamp=UTC_TIME,
        )
    ]


def test_audit_failure_has_precedence() -> None:
    successful = debug_runtime.create_debug_runtime(
        sources=(_source(debug_runtime.DebugSourceType.UART, ()),),
        audit_sink=FailingAuditSink(),
    ).debug_port()
    failing = debug_runtime.create_debug_runtime(
        sources=(FailingDebugSource(error=TimeoutError("private")),),
        audit_sink=FailingAuditSink(),
    ).debug_port()
    identify = debug_runtime.TargetIdentificationRequest(
        target_id="target:stm32",
        source_type=debug_runtime.DebugSourceType.UART,
        observed_at=UTC_TIME,
    )
    snapshot = debug_runtime.DebugSnapshotRequest(
        snapshot_id="snapshot:failure",
        target_id="target:stm32",
        source_type=debug_runtime.DebugSourceType.JLINK,
        observed_at=UTC_TIME,
    )

    with pytest.raises(debug_runtime.DebugAuditUnavailable):
        successful.identify_target(identify)
    with pytest.raises(debug_runtime.DebugAuditUnavailable):
        failing.collect_snapshot(snapshot)


def test_invalid_telemetry_and_memory_dump_content_are_rejected() -> None:
    with pytest.raises(ValidationError):
        debug_runtime.TelemetryMetric(
            name="cpu_usage",
            value=float("nan"),
            unit=debug_runtime.TelemetryUnit.PERCENT,
        )
    with pytest.raises(ValidationError):
        debug_runtime.TelemetryMetric(
            name="enabled",
            value=True,
            unit=debug_runtime.TelemetryUnit.COUNT,
        )
    with pytest.raises(ValidationError):
        debug_runtime.UARTLogRecord(
            sequence=0,
            timestamp=UTC_TIME,
            log_line="memory dump: 0x0011223344556677",
        )


def test_reasoning_bridge_binds_existing_code_context_and_stays_unverified() -> None:
    source = _source(debug_runtime.DebugSourceType.UART, ())
    snapshot = (
        debug_runtime.create_debug_runtime(
            sources=(source,),
            audit_sink=RecordingAuditSink(),
        )
        .debug_port()
        .collect_snapshot(
            debug_runtime.DebugSnapshotRequest(
                snapshot_id="snapshot:reasoning",
                target_id="target:stm32",
                source_type=debug_runtime.DebugSourceType.UART,
                observed_at=UTC_TIME,
            )
        )
    )
    context_id = "context:0123456789abcdef01234567"
    code_snapshot = (
        create_coding_runtime()
        .coding_port()
        .analyze_project(
            ProjectAnalysisRequest(
                context_id=context_id,
                files=(
                    CodeFileInput(
                        path="main.c", content="int main(void) { return 0; }\n"
                    ),
                ),
            )
        )
        .snapshot
    )

    bridge = debug_runtime.DebugReasoningContext(
        context_id=context_id,
        debug_snapshot=snapshot,
        code_snapshot=code_snapshot,
    )
    insight = debug_runtime.DebugInsight(
        evidence=("Observed a UART timeout marker.",),
        possible_causes=("UART framing mismatch remains a candidate.",),
        suggested_checks=("Verify baud rate and framing at both endpoints.",),
    )

    assert bridge.code_snapshot == code_snapshot
    assert insight.candidate_semantics == "unverified"
    assert insight.review_required is True
    assert not set(type(insight).model_fields) & {
        "root_cause",
        "confirmed",
        "conclusion",
        "control_action",
    }
    with pytest.raises(ValidationError):
        debug_runtime.DebugInsight.model_validate(
            {
                **insight.model_dump(mode="python"),
                "root_cause": "confirmed",
            }
        )
    with pytest.raises(ValidationError, match="context"):
        debug_runtime.DebugReasoningContext(
            context_id="context:ffffffffffffffffffffffff",
            debug_snapshot=snapshot,
            code_snapshot=code_snapshot,
        )
