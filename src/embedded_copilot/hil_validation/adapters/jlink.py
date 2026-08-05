from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts import (
    DeviceObservationSnapshot,
    HILValidationRequest,
    HILValidationResult,
    HardwareCapabilitySnapshot,
)
from ..exceptions import DeviceUnavailable, HILUnavailable, ObservationUnavailable


@runtime_checkable
class JLinkExecutor(Protocol):
    def get_capability(self, device_reference: str) -> HardwareCapabilitySnapshot: ...

    def observe_device(self, device_reference: str) -> DeviceObservationSnapshot: ...

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult: ...


class JLinkHILAdapter:
    def __init__(self, executor: JLinkExecutor | None = None) -> None:
        self._executor = executor

    def get_capability(self, device_reference: str) -> HardwareCapabilitySnapshot:
        if self._executor is None:
            raise DeviceUnavailable()
        try:
            return self._executor.get_capability(device_reference)
        except Exception as error:
            raise DeviceUnavailable() from error

    def observe_device(self, device_reference: str) -> DeviceObservationSnapshot:
        if self._executor is None:
            raise ObservationUnavailable()
        try:
            return self._executor.observe_device(device_reference)
        except Exception as error:
            raise ObservationUnavailable() from error

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult:
        if self._executor is None:
            raise HILUnavailable()
        try:
            return self._executor.validate_firmware(request)
        except Exception as error:
            raise HILUnavailable() from error


JLinkAdapter = JLinkHILAdapter

__all__ = ["JLinkAdapter", "JLinkExecutor", "JLinkHILAdapter"]
