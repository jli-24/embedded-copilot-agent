from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from embedded_copilot.agents.registry import AgentRegistry
from embedded_copilot.core.capability import CapabilityRegistry
from embedded_copilot.supervisor.agent import SupervisorAgent


@runtime_checkable
class SupervisorCapability(Protocol):
    name: str
    description: str
    agent_name: str
    supported_agents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SupervisorCapabilityDescriptor:
    name: str = "supervisor"
    description: str = "Deterministic sequential multi-Agent orchestration."
    agent_name: str = "SupervisorAgent"
    supported_agents: tuple[str, ...] = (
        "FirmwareAgent",
        "HardwareAgent",
        "PCBAgent",
        "DebugAgent",
    )


def register_supervisor_foundation(
    agent_registry: AgentRegistry,
    capability_registry: CapabilityRegistry,
    *,
    agent: SupervisorAgent | None = None,
    capability: SupervisorCapability | None = None,
) -> SupervisorAgent:
    active_agent = agent if agent is not None else SupervisorAgent()
    active_capability = (
        capability if capability is not None else SupervisorCapabilityDescriptor()
    )
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
    capability_registry.register(capability_name, active_capability)
    try:
        agent_registry.register_agent(active_agent)
    except Exception:
        capability_registry.unregister(capability_name)
        raise
    return active_agent
