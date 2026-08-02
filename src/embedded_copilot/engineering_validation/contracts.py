"""Public Protocol boundaries for Hardware Validation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_validation.integration.inputs import (
    HardwareValidationRequest,
)
from embedded_copilot.engineering_validation.models import (
    DeviceEvidenceCollectionRequest,
    DeviceEvidenceCollectionResult,
    HardwareValidationReport,
)


@runtime_checkable
class DeviceEvidencePort(Protocol):
    def collect(
        self,
        request: DeviceEvidenceCollectionRequest,
    ) -> DeviceEvidenceCollectionResult: ...


@runtime_checkable
class HardwareValidationPort(Protocol):
    def validate(
        self, request: HardwareValidationRequest
    ) -> HardwareValidationReport: ...
