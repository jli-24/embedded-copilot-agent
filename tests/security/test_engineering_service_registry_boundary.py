from __future__ import annotations

from embedded_copilot.agents.debug import DebugAgent as CanonicalDebugAgent
from embedded_copilot.agents.firmware import FirmwareAgent as CanonicalFirmwareAgent
from embedded_copilot.agents.knowledge import KnowledgeAgent
from embedded_copilot.debug.agent import DebugAgent as FoundationDebugAgent
from embedded_copilot.firmware.agent import FirmwareAgent as FoundationFirmwareAgent
from embedded_copilot.hardware.agent import HardwareAgent
from embedded_copilot.pcb.agent import PCBAgent
from embedded_copilot.services.canonical_runtime import (
    CANONICAL_RUNTIME_AGENT_NAMES,
    CANONICAL_RUNTIME_AGENT_TYPES,
    CANONICAL_RUNTIME_ROUTER,
)
from embedded_copilot.services.legacy_runtime import LEGACY_RUNTIME_AGENT_TYPES
from embedded_copilot.supervisor.agent import SupervisorAgent


def test_canonical_registry_is_fixed() -> None:
    assert CANONICAL_RUNTIME_AGENT_NAMES == (
        "supervisor",
        "knowledge",
        "firmware",
        "debug",
    )
    assert CANONICAL_RUNTIME_AGENT_TYPES == (
        KnowledgeAgent,
        CanonicalFirmwareAgent,
        CanonicalDebugAgent,
    )
    assert CANONICAL_RUNTIME_ROUTER.__name__ == "supervisor_node"


def test_legacy_agents_and_services_are_not_canonical_agents() -> None:
    forbidden_legacy = {
        SupervisorAgent,
        FoundationFirmwareAgent,
        FoundationDebugAgent,
        HardwareAgent,
        PCBAgent,
    }
    forbidden_service_names = {
        "MemoryService",
        "MultimodalInputService",
        "ValidationLoopService",
        "OptimizationService",
        "FileKnowledgeWriter",
    }

    assert forbidden_legacy.isdisjoint(CANONICAL_RUNTIME_AGENT_TYPES)
    assert not forbidden_service_names.intersection(
        agent.__name__ for agent in CANONICAL_RUNTIME_AGENT_TYPES
    )


def test_legacy_registry_is_separate_and_complete() -> None:
    assert LEGACY_RUNTIME_AGENT_TYPES == (
        SupervisorAgent,
        FoundationFirmwareAgent,
        FoundationDebugAgent,
        HardwareAgent,
        PCBAgent,
    )
    assert set(LEGACY_RUNTIME_AGENT_TYPES).isdisjoint(
        {KnowledgeAgent, CanonicalFirmwareAgent, CanonicalDebugAgent}
    )
