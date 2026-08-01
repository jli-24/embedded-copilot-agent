"""Deterministic provider fakes for Hardware Intelligence tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from embedded_copilot.hardware_intelligence import (
    DigitalTwinMetric,
    DigitalTwinProjection,
    DigitalTwinRequest,
    HardwareAnalysisRequest,
    HardwareContextProjection,
    HardwareMetadata,
    HardwareMetricUnit,
    HardwareObservation,
    HardwareProgressEvent,
    HardwareTelemetryRequest,
    HardwareValidationProjection,
    HardwareValidationRequest,
    HardwareValidationStatus,
    HardwareValidationType,
    digital_twin_fingerprint,
    hardware_context_fingerprint,
    hardware_validation_fingerprint,
)

NOW = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)


class FakeTwinProvider:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[DigitalTwinRequest] = []

    def simulate(self, request: DigitalTwinRequest) -> DigitalTwinProjection:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        metrics = (
            DigitalTwinMetric(
                metric_name="temperature",
                value=24.5,
                unit=HardwareMetricUnit.CELSIUS,
            ),
            DigitalTwinMetric(
                metric_name="voltage",
                value=3.3,
                unit=HardwareMetricUnit.VOLTS,
            ),
        )
        return DigitalTwinProjection(
            model_id="twin-model-1",
            state_summary="Simulation projection completed.",
            simulated_metrics=metrics,
            fingerprint=digital_twin_fingerprint(
                model_id="twin-model-1",
                state_summary="Simulation projection completed.",
                simulated_metrics=metrics,
            ),
        )


class FakeTelemetryProvider:
    def __init__(self, *, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[HardwareTelemetryRequest] = []

    def observe(
        self, request: HardwareTelemetryRequest
    ) -> tuple[HardwareObservation, ...]:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return (
            HardwareObservation(
                sensor_id="current-sensor-1",
                metric_name="current",
                value=0.14,
                unit=HardwareMetricUnit.AMPERES,
                timestamp=request.timestamp,
            ),
            HardwareObservation(
                sensor_id="temperature-sensor-1",
                metric_name="temperature",
                value=25.0,
                unit=HardwareMetricUnit.CELSIUS,
                timestamp=request.timestamp,
            ),
        )


class FakeValidationPort:
    def __init__(
        self,
        status: HardwareValidationStatus = HardwareValidationStatus.VALID,
        *,
        error: Exception | None = None,
        result=None,
    ) -> None:
        self.status = status
        self.error = error
        self.result = result
        self.calls: list[HardwareValidationRequest] = []

    def validate(
        self, request: HardwareValidationRequest
    ) -> HardwareValidationProjection:
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        validation_types = (
            HardwareValidationType.CONTRACT,
            HardwareValidationType.SIMULATION,
            HardwareValidationType.THRESHOLD,
        )
        return HardwareValidationProjection(
            hardware_id=request.context.hardware_id,
            twin_fingerprint=request.digital_twin.fingerprint,
            observation_fingerprint=request.observation_fingerprint,
            status=self.status,
            validation_types=validation_types,
            fingerprint=hardware_validation_fingerprint(
                hardware_id=request.context.hardware_id,
                twin_fingerprint=request.digital_twin.fingerprint,
                observation_fingerprint=request.observation_fingerprint,
                status=self.status,
                validation_types=validation_types,
            ),
        )


class RecordingProgressSink:
    def __init__(self, *, fail_on_sequence: int | None = None) -> None:
        self.fail_on_sequence = fail_on_sequence
        self.events: list[HardwareProgressEvent] = []

    def emit(self, event: HardwareProgressEvent) -> None:
        if event.sequence == self.fail_on_sequence:
            raise RuntimeError("private device backend failure")
        self.events.append(event)


@pytest.fixture
def hardware_request() -> HardwareAnalysisRequest:
    metadata = (
        HardwareMetadata(key="execution_id", value="controlled-execution-1"),
        HardwareMetadata(key="source_reference", value="artifact-reference-1"),
    )
    context = HardwareContextProjection(
        hardware_id="hardware-analysis-1",
        device_type="ESP32_S3",
        board_reference="board-reference-1",
        safe_metadata=metadata,
        fingerprint=hardware_context_fingerprint(
            hardware_id="hardware-analysis-1",
            device_type="ESP32_S3",
            board_reference="board-reference-1",
            safe_metadata=metadata,
        ),
    )
    return HardwareAnalysisRequest(
        hardware_id="hardware-analysis-1",
        scenario_id="scenario-1",
        context=context,
        timestamp=NOW,
    )


@pytest.fixture
def providers():
    return (
        FakeTwinProvider(),
        FakeTelemetryProvider(),
        FakeValidationPort(),
        RecordingProgressSink(),
    )
