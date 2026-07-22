from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.firmware.agent import FirmwareAgent


@runtime_checkable
class FirmwareCapability(Protocol):
    name: str
    description: str
    agent_name: str
    supported_platforms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FirmwareCapabilityDescriptor:
    name: str = "firmware"
    description: str = "Deterministic platform checks and mock code generation."
    agent_name: str = "FirmwareAgent"
    supported_platforms: tuple[str, ...] = ("ESP32", "STM32")


def register_firmware_foundation(
    agent_registry: AgentRegistry,
    capability_registry: CapabilityRegistry,
    *,
    agent: FirmwareAgent | None = None,
    capability: FirmwareCapability | None = None,
) -> FirmwareAgent:
    active_agent = agent or FirmwareAgent()
    active_capability = capability or FirmwareCapabilityDescriptor()
    agent_name = active_agent.name.strip()
    capability_name = active_capability.name.strip()
    if not agent_name:
        raise ValueError("agent name must not be empty")
    if not capability_name:
        raise ValueError("capability name must not be empty")
    if agent_name in agent_registry.list_agents():
        raise ValueError(f"agent already registered: {agent_name}")
    if capability_name in capability_registry.list_capabilities():
        raise ValueError(f"capability already registered: {capability_name}")
    agent_registry.register_agent(active_agent)
    capability_registry.register(capability_name, active_capability)
    return active_agent
