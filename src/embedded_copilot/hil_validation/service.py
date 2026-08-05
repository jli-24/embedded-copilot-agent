from __future__ import annotations

import copy

from .contracts import (
    DeviceObservationSnapshot,
    HILAdapterPort,
    HILValidationPort,
    HILValidationRequest,
    HILValidationResult,
    HardwareCapabilitySnapshot,
    validate_capability_snapshot,
    validate_observation_snapshot,
    validate_request,
    validate_result,
)
from .exceptions import (
    HILApprovalRequired,
    HILError,
    HILRejected,
    HILUnavailable,
    ObservationUnavailable,
)


class HILValidationService:
    __slots__ = ("_adapter",)

    def __init__(self, adapter: HILAdapterPort | None = None) -> None:
        if adapter is not None and not isinstance(adapter, HILAdapterPort):
            raise TypeError("HIL adapter port is invalid")
        self._adapter = adapter

    def get_capability(self, project_id: str) -> HardwareCapabilitySnapshot:
        if self._adapter is None:
            raise HILUnavailable()
        try:
            result = validate_capability_snapshot(
                self._adapter.get_capability(copy.deepcopy(project_id))
            )
            if result.project_id != project_id:
                raise ValueError("capability identity mismatch")
            return result
        except HILError:
            raise
        except Exception as error:
            raise HILRejected() from error

    def observe_device(self, project_id: str) -> DeviceObservationSnapshot:
        if self._adapter is None:
            raise ObservationUnavailable()
        try:
            result = validate_observation_snapshot(
                self._adapter.observe_device(copy.deepcopy(project_id))
            )
            if result.project_id != project_id:
                raise ValueError("observation identity mismatch")
            return result
        except HILError:
            raise
        except Exception as error:
            raise HILRejected() from error

    def validate(self, request: HILValidationRequest) -> HILValidationResult:
        checked = validate_request(request)
        if checked.approval_reference is None:
            raise HILApprovalRequired()
        if self._adapter is None:
            raise HILUnavailable()
        try:
            result = validate_result(
                self._adapter.validate_firmware(copy.deepcopy(checked))
            )
            if (
                result.project_id != checked.project_id
                or result.device_reference != checked.device_reference
                or result.firmware_reference != checked.firmware_reference
            ):
                raise ValueError("HIL result identity mismatch")
            return result
        except (HILApprovalRequired, HILError):
            raise
        except Exception as error:
            raise HILRejected() from error

    def get_snapshot(self, project_id: str) -> HILValidationResult | None:
        if self._adapter is None:
            raise HILUnavailable()
        method = getattr(self._adapter, "get_snapshot", None)
        if not callable(method):
            raise HILUnavailable()
        try:
            value = method(copy.deepcopy(project_id))
            if value is None:
                return None
            result = validate_result(value)
            if result.project_id != project_id:
                raise ValueError("HIL snapshot identity mismatch")
            return result
        except HILError:
            raise
        except Exception as error:
            raise HILRejected() from error


__all__ = ["HILValidationService"]
