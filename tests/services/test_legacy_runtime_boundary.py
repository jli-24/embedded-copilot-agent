from __future__ import annotations

from embedded_copilot.agents.debug import DebugAgent as CanonicalDebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent as CanonicalFirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.debug.agent import DebugAgent as FoundationDebugAgent
from embedded_copilot.firmware.agent import FirmwareAgent as FoundationFirmwareAgent
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.services.legacy_runtime import LEGACY_RUNTIME_AGENT_TYPES
from embedded_copilot.supervisor.agent import SupervisorAgent


def test_legacy_runtime_whitelist_matches_legacy_composition() -> None:
    assert LEGACY_RUNTIME_AGENT_TYPES == (
        SupervisorAgent,
        FoundationFirmwareAgent,
        FoundationDebugAgent,
        HardwareAgent,
        PCBAgent,
    )


def test_legacy_runtime_does_not_register_canonical_specialists() -> None:
    canonical_types = {
        KnowledgeAgent,
        CanonicalFirmwareAgent,
        CanonicalDebugAgent,
    }

    assert canonical_types.isdisjoint(LEGACY_RUNTIME_AGENT_TYPES)
