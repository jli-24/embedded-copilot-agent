"""Public Protocol boundary for Hardware Engineering."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.engineering_hardware.integration.intelligence import (
    HardwareEngineeringRequest,
)
from embedded_copilot.engineering_hardware.models import HardwareEngineeringProposal


@runtime_checkable
class HardwareEngineeringPort(Protocol):
    def prepare_proposal(
        self,
        request: HardwareEngineeringRequest,
    ) -> HardwareEngineeringProposal: ...
