"""Runtime lifecycle, provider isolation, and validation tests."""

from __future__ import annotations

import pytest

from embedded_copilot.hardware_intelligence import (
    HardwareFailureCode,
    HardwareIntelligenceRuntime,
    HardwareIntelligenceState,
    HardwareProgressUnavailable,
    HardwareValidationApproval,
    HardwareValidationDecision,
    HardwareValidationStatus,
    create_hardware_intelligence_runtime,
    hardware_validation_approval_fingerprint,
)

from .conftest import (
    FakeTelemetryProvider,
    FakeTwinProvider,
    FakeValidationPort,
    NOW,
    RecordingProgressSink,
)


def _runtime(*, twin=None, telemetry=None, validation=None, sink=None):
    twin = twin or FakeTwinProvider()
    telemetry = telemetry or FakeTelemetryProvider()
    validation = validation or FakeValidationPort()
    sink = sink or RecordingProgressSink()
    runtime = create_hardware_intelligence_runtime(
        twin_provider=twin,
        telemetry_provider=telemetry,
        validation_port=validation,
        progress_sink=sink,
    )
    return runtime, twin, telemetry, validation, sink


def _approval(snapshot, decision=HardwareValidationDecision.APPROVED):
    fingerprint = hardware_validation_approval_fingerprint(
        hardware_id=snapshot.request.hardware_id,
        snapshot_fingerprint=snapshot.fingerprint,
        decision=decision,
        reviewer="engineer-1",
        timestamp=NOW,
    )
    return HardwareValidationApproval(
        hardware_id=snapshot.request.hardware_id,
        snapshot_fingerprint=snapshot.fingerprint,
        decision=decision,
        reviewer="engineer-1",
        timestamp=NOW,
        fingerprint=fingerprint,
    )


def test_prepare_and_validate_hardware_lifecycle(hardware_request) -> None:
    before = hardware_request.model_dump_json()
    runtime, twin, telemetry, validation, sink = _runtime()
    observed = runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    assert observed.state is HardwareIntelligenceState.OBSERVATION_READY
    assert observed.digital_twin is not None
    assert observed.hil_projection is not None
    assert len(observed.observations) == 2
    terminal = runtime.hardware_port().validate_hardware(observed, _approval(observed))
    assert terminal.state is HardwareIntelligenceState.VALIDATED
    assert terminal.validation is not None
    assert terminal.validation.status is HardwareValidationStatus.VALID
    assert len(twin.calls) == len(telemetry.calls) == len(validation.calls) == 1
    assert [event.state for event in sink.events] == [
        HardwareIntelligenceState.CREATED,
        HardwareIntelligenceState.CONTEXT_READY,
        HardwareIntelligenceState.TWIN_READY,
        HardwareIntelligenceState.OBSERVATION_READY,
        HardwareIntelligenceState.VALIDATING,
        HardwareIntelligenceState.VALIDATED,
    ]
    assert hardware_request.model_dump_json() == before


def test_digital_twin_is_deterministic_for_same_request(hardware_request) -> None:
    first, _, _, _, _ = _runtime()
    second, _, _, _, _ = _runtime()
    first_snapshot = first.hardware_port().prepare_hardware_analysis(hardware_request)
    second_snapshot = second.hardware_port().prepare_hardware_analysis(hardware_request)
    assert first_snapshot.digital_twin == second_snapshot.digital_twin
    assert first_snapshot.fingerprint == second_snapshot.fingerprint


@pytest.mark.parametrize(
    ("provider", "failure"),
    [
        ("twin", HardwareFailureCode.TWIN_UNAVAILABLE),
        ("telemetry", HardwareFailureCode.TELEMETRY_UNAVAILABLE),
    ],
)
def test_provider_failure_returns_sanitized_terminal_snapshot(
    hardware_request, provider, failure
) -> None:
    twin = FakeTwinProvider(
        error=RuntimeError("private USB device path") if provider == "twin" else None
    )
    telemetry = FakeTelemetryProvider(
        error=RuntimeError("private UART log") if provider == "telemetry" else None
    )
    runtime, _, _, validation, _ = _runtime(twin=twin, telemetry=telemetry)
    snapshot = runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    assert snapshot.state is HardwareIntelligenceState.FAILED
    assert snapshot.failure_code is failure
    assert "private" not in snapshot.model_dump_json().lower()
    assert not validation.calls


def test_malformed_provider_projection_fails_closed(hardware_request) -> None:
    runtime, *_ = _runtime(twin=FakeTwinProvider(result={"model_id": "unsafe"}))
    snapshot = runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    assert snapshot.state is HardwareIntelligenceState.FAILED
    assert snapshot.failure_code is HardwareFailureCode.TWIN_REJECTED


def test_invalid_validation_returns_invalid_snapshot(hardware_request) -> None:
    validation = FakeValidationPort(HardwareValidationStatus.INVALID)
    runtime, _, _, validation, _ = _runtime(validation=validation)
    observed = runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    terminal = runtime.hardware_port().validate_hardware(observed, _approval(observed))
    assert terminal.state is HardwareIntelligenceState.INVALID
    assert terminal.failure_code is HardwareFailureCode.VALIDATION_INVALID
    assert len(validation.calls) == 1


def test_validation_failure_is_isolated(hardware_request) -> None:
    validation = FakeValidationPort(error=RuntimeError("database host secret"))
    runtime, _, _, _, _ = _runtime(validation=validation)
    observed = runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    terminal = runtime.hardware_port().validate_hardware(observed, _approval(observed))
    assert terminal.state is HardwareIntelligenceState.FAILED
    assert terminal.failure_code is HardwareFailureCode.VALIDATION_UNAVAILABLE
    assert "database" not in terminal.model_dump_json().lower()


def test_denied_validation_does_not_call_validation_port(hardware_request) -> None:
    runtime, _, _, validation, _ = _runtime()
    observed = runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    terminal = runtime.hardware_port().validate_hardware(
        observed, _approval(observed, HardwareValidationDecision.DENIED)
    )
    assert terminal.state is HardwareIntelligenceState.INVALID
    assert terminal.failure_code is HardwareFailureCode.APPROVAL_DENIED
    assert not validation.calls


def test_progress_failure_stops_downstream_calls(hardware_request) -> None:
    sink = RecordingProgressSink(fail_on_sequence=2)
    runtime, twin, telemetry, validation, _ = _runtime(sink=sink)
    with pytest.raises(
        HardwareProgressUnavailable, match="hardware progress unavailable"
    ):
        runtime.hardware_port().prepare_hardware_analysis(hardware_request)
    assert not twin.calls
    assert not telemetry.calls
    assert not validation.calls


def test_factory_and_facade_hide_internal_capabilities() -> None:
    runtime, *_ = _runtime()
    assert runtime.hardware_port() is runtime.hardware_port()
    for name in (
        "twin_provider",
        "telemetry_provider",
        "validation_port",
        "progress_sink",
        "device",
        "connection",
    ):
        assert not hasattr(runtime, name)
    with pytest.raises(TypeError, match="composition factory"):
        HardwareIntelligenceRuntime(runtime.hardware_port())
    with pytest.raises(TypeError):
        create_hardware_intelligence_runtime(
            twin_provider=object(),
            telemetry_provider=FakeTelemetryProvider(),
            validation_port=FakeValidationPort(),
            progress_sink=RecordingProgressSink(),
        )
