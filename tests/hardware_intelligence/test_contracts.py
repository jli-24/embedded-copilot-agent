"""Contract tests for hardware context, simulation, HIL, and telemetry."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from embedded_copilot.hardware_intelligence import (
    DigitalTwinMetric,
    HILProjection,
    HILProjectionStatus,
    HardwareContextProjection,
    HardwareMetadata,
    HardwareMetricUnit,
    HardwareObservation,
    HardwareValidationApproval,
    HardwareValidationDecision,
    hardware_context_fingerprint,
    hardware_validation_approval_fingerprint,
    hil_projection_fingerprint,
)

from .conftest import NOW


def test_contracts_are_frozen_strict_and_extra_forbidden(hardware_request) -> None:
    with pytest.raises(ValidationError):
        hardware_request.hardware_id = "changed"
    with pytest.raises(ValidationError):
        type(hardware_request).model_validate(
            {**hardware_request.model_dump(mode="python"), "serial_port": "COM3"}
        )
    with pytest.raises(ValidationError):
        HardwareContextProjection(
            hardware_id="hardware-1",
            device_type="ESP32_S3",
            board_reference="board-1",
            safe_metadata=[HardwareMetadata(key="key", value="value")],
            fingerprint="sha256:" + "0" * 64,
        )


def test_context_fingerprint_is_deterministic_and_tamper_evident() -> None:
    metadata = (HardwareMetadata(key="source", value="reference-1"),)
    fingerprint = hardware_context_fingerprint(
        hardware_id="hardware-1",
        device_type="STM32_FAMILY",
        board_reference="board-1",
        safe_metadata=metadata,
    )
    context = HardwareContextProjection(
        hardware_id="hardware-1",
        device_type="STM32_FAMILY",
        board_reference="board-1",
        safe_metadata=metadata,
        fingerprint=fingerprint,
    )
    assert (
        HardwareContextProjection.model_validate(context.model_copy(deep=True))
        == context
    )
    with pytest.raises(ValidationError):
        HardwareContextProjection.model_validate(
            context.model_copy(update={"board_reference": "board-2"})
        )


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_simulated_metric_rejects_boolean_and_non_finite_values(value) -> None:
    with pytest.raises(ValidationError):
        DigitalTwinMetric(
            metric_name="voltage",
            value=value,
            unit=HardwareMetricUnit.VOLTS,
        )


def test_observation_is_structured_utc_only_and_content_free() -> None:
    observation = HardwareObservation(
        sensor_id="temperature-sensor-1",
        metric_name="temperature",
        value=25.0,
        unit=HardwareMetricUnit.CELSIUS,
        timestamp=NOW,
    )
    serialized = observation.model_dump_json().lower()
    assert "raw" not in serialized
    assert "stdout" not in serialized
    assert "stderr" not in serialized
    with pytest.raises(ValidationError):
        HardwareObservation(
            sensor_id="temperature-sensor-1",
            metric_name="temperature",
            value=25.0,
            unit=HardwareMetricUnit.CELSIUS,
            timestamp=datetime(2026, 8, 1, 8, 0),
        )


def test_hil_is_projection_only_and_fingerprinted() -> None:
    fingerprint = hil_projection_fingerprint(
        scenario_id="scenario-1",
        input_reference="sha256:" + "a" * 64,
        observation_reference="sha256:" + "b" * 64,
        status=HILProjectionStatus.OBSERVED,
    )
    projection = HILProjection(
        scenario_id="scenario-1",
        input_reference="sha256:" + "a" * 64,
        observation_reference="sha256:" + "b" * 64,
        status=HILProjectionStatus.OBSERVED,
        fingerprint=fingerprint,
    )
    assert set(type(projection).model_fields) == {
        "scenario_id",
        "input_reference",
        "observation_reference",
        "status",
        "fingerprint",
    }
    for forbidden in ("execute", "control", "command", "device_handle"):
        assert not hasattr(projection, forbidden)


def test_validation_approval_is_bound_and_tamper_evident() -> None:
    fingerprint = hardware_validation_approval_fingerprint(
        hardware_id="hardware-1",
        snapshot_fingerprint="sha256:" + "a" * 64,
        decision=HardwareValidationDecision.APPROVED,
        reviewer="engineer-1",
        timestamp=NOW,
    )
    approval = HardwareValidationApproval(
        hardware_id="hardware-1",
        snapshot_fingerprint="sha256:" + "a" * 64,
        decision=HardwareValidationDecision.APPROVED,
        reviewer="engineer-1",
        timestamp=NOW,
        fingerprint=fingerprint,
    )
    with pytest.raises(ValidationError):
        type(approval).model_validate(
            approval.model_copy(update={"reviewer": "engineer-2"})
        )
