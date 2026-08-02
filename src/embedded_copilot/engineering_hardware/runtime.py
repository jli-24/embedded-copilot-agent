"""Stateless Hardware Engineering agent orchestration."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_hardware.exceptions import (
    HardwareEngineeringRejected,
)
from embedded_copilot.engineering_hardware.integration.intelligence import (
    HardwareEngineeringRequest,
    project_intelligence_input,
)
from embedded_copilot.engineering_hardware.models import HardwareEngineeringProposal
from embedded_copilot.engineering_hardware.projection import build_hardware_proposal


class _HardwareEngineeringAgent:
    def prepare_proposal(
        self,
        request: HardwareEngineeringRequest,
    ) -> HardwareEngineeringProposal:
        try:
            source = project_intelligence_input(request)
            return build_hardware_proposal(source)
        except HardwareEngineeringRejected:
            raise
        except (TypeError, ValueError, ValidationError):
            raise HardwareEngineeringRejected(
                "hardware engineering request rejected"
            ) from None
