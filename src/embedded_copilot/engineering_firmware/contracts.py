"""Public Protocol boundary for Firmware Engineering."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_firmware.integration.inputs import (
    FirmwareEngineeringRequest,
)
from embedded_copilot.engineering_firmware.models import FirmwareEngineeringProposal


@runtime_checkable
class FirmwareEngineeringPort(Protocol):
    def prepare_firmware_proposal(
        self,
        request: FirmwareEngineeringRequest,
    ) -> FirmwareEngineeringProposal: ...
