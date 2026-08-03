"""Firmware Agent public Port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from embedded_copilot.firmware_agent.models import (
    FirmwareGenerationRequest,
    FirmwareProposal,
)


@runtime_checkable
class FirmwareAgentPort(Protocol):
    async def generate(self, request: FirmwareGenerationRequest) -> FirmwareProposal: ...
