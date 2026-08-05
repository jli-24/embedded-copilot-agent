from __future__ import annotations

import pytest

from embedded_copilot.hil_validation.adapters.jlink import JLinkHILAdapter
from embedded_copilot.hil_validation.adapters.openocd import OpenOCDHILAdapter
from embedded_copilot.hil_validation.adapters.serial import SerialHILAdapter
from embedded_copilot.hil_validation.contracts import HILValidationRequest
from embedded_copilot.hil_validation.exceptions import (
    DeviceUnavailable,
    HILUnavailable,
    ObservationUnavailable,
)


def test_unconfigured_adapters_fail_closed() -> None:
    request = HILValidationRequest.create(
        project_id="demo",
        device_reference="device:demo",
        firmware_reference="firmware:demo",
        approval_reference="approval:demo",
    )
    with pytest.raises(ObservationUnavailable):
        SerialHILAdapter().observe_device("device:demo")
    with pytest.raises(DeviceUnavailable):
        JLinkHILAdapter().get_capability("device:demo")
    with pytest.raises(HILUnavailable):
        OpenOCDHILAdapter().validate_firmware(request)

