"""Composition root for deterministic Hardware Validation."""

from embedded_copilot.engineering_validation.contracts import DeviceEvidencePort
from embedded_copilot.engineering_validation.facade import HardwareValidationRuntime
from embedded_copilot.engineering_validation.runtime import _HardwareValidationAgent


def create_hardware_validation_runtime(
    *, evidence_port: DeviceEvidencePort
) -> HardwareValidationRuntime:
    if not isinstance(evidence_port, DeviceEvidencePort):
        raise TypeError("evidence_port must implement DeviceEvidencePort")
    return HardwareValidationRuntime._compose(_HardwareValidationAgent(evidence_port))
