from __future__ import annotations

import pytest
from pydantic import ValidationError

from embedded_copilot.hil_validation.adapters.fake import FakeHILAdapter
from embedded_copilot.hil_validation.contracts import (
    HILOverallStatus,
    HILValidationRequest,
    HardwareCapabilitySnapshot,
    ObservationStatus,
)


def test_fake_hil_capability_is_deterministic_and_safe() -> None:
    values = [FakeHILAdapter().get_capability("device:demo") for _ in range(100)]
    assert len({item.fingerprint for item in values}) == 1
    assert values[0].board_type == "ESP32-S3"
    assert "serial" not in values[0].model_dump_json().lower()


def test_dtos_are_frozen_strict_and_tuple_only() -> None:
    snapshot = FakeHILAdapter().get_capability("device:demo")
    with pytest.raises(ValidationError):
        snapshot.board_type = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        HardwareCapabilitySnapshot.model_validate(
            {**snapshot.model_dump(mode="python"), "interfaces": ["UART"]}
        )
    with pytest.raises(ValidationError):
        HILValidationRequest.model_validate(
            {
                "project_id": "demo",
                "device_reference": "device:demo",
                "firmware_reference": "firmware:demo",
                "approval_reference": "approval:demo",
                "unexpected": "reject",
            }
        )


def test_validation_result_binds_safe_statuses() -> None:
    result = FakeHILAdapter().validate_firmware(
        HILValidationRequest.create(
            project_id="demo",
            device_reference="device:demo",
            firmware_reference="firmware:demo",
            approval_reference="approval:demo",
        )
    )
    assert result.overall_status is HILOverallStatus.PASSED
    assert result.project_id == "demo"
    assert result.test_cases[0].fingerprint.startswith("sha256:")
    observation = FakeHILAdapter().observe_device("device:demo")
    assert observation.status is ObservationStatus.CONNECTED

