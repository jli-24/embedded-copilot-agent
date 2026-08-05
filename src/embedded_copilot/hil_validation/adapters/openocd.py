from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts import HILValidationRequest, HILValidationResult
from ..exceptions import HILUnavailable


@runtime_checkable
class OpenOCDExecutor(Protocol):
    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult: ...


class OpenOCDHILAdapter:
    def __init__(self, executor: OpenOCDExecutor | None = None) -> None:
        self._executor = executor

    def validate_firmware(self, request: HILValidationRequest) -> HILValidationResult:
        if self._executor is None:
            raise HILUnavailable()
        try:
            return self._executor.validate_firmware(request)
        except Exception as error:
            raise HILUnavailable() from error


OpenOCDAdapter = OpenOCDHILAdapter

__all__ = ["OpenOCDAdapter", "OpenOCDExecutor", "OpenOCDHILAdapter"]
