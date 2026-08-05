from __future__ import annotations

from ..contracts import (
    DeviceObservationSnapshot,
    HILOverallStatus,
    HILValidationPort,
    HILValidationRequest,
    HILValidationResult,
    HILAdapterPort,
    HILTestStatus,
    HardwareCapabilitySnapshot,
    MetricProjection,
    ObservationStatus,
    TestCaseProjection,
)


def _project_id(reference: str) -> str:
    return reference.split(":", 1)[-1]


class FakeHILAdapter(HILAdapterPort, HILValidationPort):
    def get_capability(self, device_reference: str) -> HardwareCapabilitySnapshot:
        project_id = _project_id(device_reference)
        return HardwareCapabilitySnapshot.create(
            project_id=project_id,
            device_reference=device_reference,
            board_type="ESP32-S3",
            chip_family="ESP32",
            interfaces=("UART", "JTAG", "USB"),
            capabilities=("WIFI", "BLUETOOTH", "JTAG"),
        )

    def observe_device(self, device_reference: str) -> DeviceObservationSnapshot:
        project_id = _project_id(device_reference)
        return DeviceObservationSnapshot.create(
            project_id=project_id,
            device_reference=device_reference,
            observation_type="BOOT_HEALTH",
            status=ObservationStatus.CONNECTED,
            metrics=(MetricProjection(name="boot_count", value="1"),),
            evidence_reference=f"evidence:{project_id}",
        )

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult:
        case = TestCaseProjection.create(
            name="device_boot",
            status=HILTestStatus.PASSED,
            summary="Device boot observation is available.",
        )
        return HILValidationResult.create(
            project_id=request.project_id,
            test_reference=f"test:{request.project_id}",
            device_reference=request.device_reference,
            firmware_reference=request.firmware_reference,
            test_cases=(case,),
            overall_status=HILOverallStatus.PASSED,
            evidence_reference=f"evidence:{request.project_id}",
        )

    def validate(self, request: HILValidationRequest) -> HILValidationResult:
        return self.validate_firmware(request)

    def get_snapshot(self, project_id: str) -> HILValidationResult:
        return self.validate_firmware(
            HILValidationRequest.create(
                project_id=project_id,
                device_reference=f"device:{project_id}",
                firmware_reference=f"firmware:{project_id}",
                approval_reference=f"approval:{project_id}",
            )
        )


class FakeHardwareCapabilityPort:
    def __init__(self, adapter: FakeHILAdapter | None = None) -> None:
        self._adapter = adapter or FakeHILAdapter()

    def get_snapshot(self, project_id: str) -> HardwareCapabilitySnapshot:
        return self._adapter.get_capability(f"device:{project_id}")


class FakeDeviceObservationPort:
    def __init__(self, adapter: FakeHILAdapter | None = None) -> None:
        self._adapter = adapter or FakeHILAdapter()

    def get_snapshot(self, project_id: str) -> DeviceObservationSnapshot:
        return self._adapter.observe_device(f"device:{project_id}")


class FakeHILValidationPort:
    def __init__(self, adapter: FakeHILAdapter | None = None) -> None:
        self._adapter = adapter or FakeHILAdapter()

    def validate(self, request: HILValidationRequest) -> HILValidationResult:
        return self._adapter.validate(request)

    def get_snapshot(self, project_id: str) -> HILValidationResult:
        return self._adapter.get_snapshot(project_id)


__all__ = [
    "FakeDeviceObservationPort",
    "FakeHILAdapter",
    "FakeHILValidationPort",
    "FakeHardwareCapabilityPort",
]
