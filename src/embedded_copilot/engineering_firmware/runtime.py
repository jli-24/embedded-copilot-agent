"""Stateless Firmware Engineering agent orchestration."""

from __future__ import annotations

from pydantic import ValidationError

from embedded_copilot.engineering_firmware.exceptions import (
    FirmwareEngineeringRejected,
)
from embedded_copilot.engineering_firmware.integration.inputs import (
    FirmwareEngineeringRequest,
    project_firmware_input,
)
from embedded_copilot.engineering_firmware.models import FirmwareEngineeringProposal
from embedded_copilot.engineering_firmware.projection import build_firmware_proposal


class _FirmwareEngineeringAgent:
    def prepare_firmware_proposal(
        self,
        request: FirmwareEngineeringRequest,
    ) -> FirmwareEngineeringProposal:
        try:
            source = project_firmware_input(request)
            return build_firmware_proposal(source)
        except FirmwareEngineeringRejected:
            raise
        except (TypeError, ValueError, ValidationError):
            raise FirmwareEngineeringRejected(
                "firmware engineering request rejected"
            ) from None
