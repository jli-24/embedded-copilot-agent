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
class SerialHILTransport(Protocol):
    def get_capability(self, device_reference: str) -> HardwareCapabilitySnapshot: ...

    def observe_device(self, device_reference: str) -> DeviceObservationSnapshot: ...

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult: ...


class SerialHILAdapter:
    def __init__(self, transport: SerialHILTransport | None = None) -> None:
        self._transport = transport

    def get_capability(self, device_reference: str) -> HardwareCapabilitySnapshot:
        if self._transport is None:
            raise DeviceUnavailable()
        try:
            return self._transport.get_capability(device_reference)
        except Exception as error:
            raise DeviceUnavailable() from error

    def observe_device(self, device_reference: str) -> DeviceObservationSnapshot:
        if self._transport is None:
            raise ObservationUnavailable()
        try:
            return self._transport.observe_device(device_reference)
        except Exception as error:
            raise ObservationUnavailable() from error

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult:
        if self._transport is None:
            raise HILUnavailable()
        try:
            return self._transport.validate_firmware(request)
        except Exception as error:
            raise HILUnavailable() from error


SerialAdapter = SerialHILAdapter

__all__ = ["SerialAdapter", "SerialHILAdapter", "SerialHILTransport"]
